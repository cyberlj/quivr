import importlib
import logging
import types
from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import List, Type, TypeAlias

from quivr_core.files.file import FileExtension

from .processor_base import ProcessorBase

logger = logging.getLogger("quivr_core")

_LOWEST_PRIORITY = 100

_registry: dict[str, Type[ProcessorBase]] = {}

# external, read only. Contains the actual processors that we are imported and ready to use
# registry 是 _registry 字典的“仅读”视图（不可修改），
# 用 MappingProxyType 创建后，外部只能读取，不能直接插入或删除项。
# 这样可以防止外部代码无意中更改注册表，保证注册的 processors 只允许框架自身统一管理。
# 想要修改 _registry（如注册或移除某个 processor），
# 必须通过专门暴露的注册函数（如 register_processor）间接操作，
# 外部模块无法直接对 _registry 做 +=, del, assignment 等写操作，只能通过官方接口改动。
registry = types.MappingProxyType(_registry)


@dataclass(order=True)
class ProcEntry:
    priority: int
    # cls_mod 表示处理器的“类+模块”路径，格式通常为 "模块路径.类名"，
    # 如 "quivr_core.processor.implementations.simple_txt_processor.SimpleTxtProcessor"。
    # 这样设计方便动态 import 和构造实例，通过 importlib 导入后，用于定位分析/解析实现。
    cls_mod: str = field(compare=False)
    err: str | None = field(compare=False)


# ProcMapping 是一个类型别名，指定了“文件扩展名”映射到“处理器条目列表”的字典结构。
# 键（FileExtension | str）：可以是 FileExtension 枚举成员（如 FileExtension.txt）、也可以直接用字符串扩展名（如 ".txt"）。
# 值（list[ProcEntry]）：每个扩展名对应一组可用的解析器实现（ProcEntry），支持按优先级排序（如首选某个解析器，降级用其他的）。
# 这样定义后，ProcMapping 可用于静态类型检查，并提示哪些地方应该采用“{文件扩展名: [处理器条目]}”的结构，便于 processor 注册、查询与优先队列操作。
ProcMapping: TypeAlias = dict[FileExtension | str, list[ProcEntry]]

# Register based on mimetypes
#
# 为什么 txt 和 pdf 都设为低优先级（_LOWEST_PRIORITY）？
# 1. Quivr 默认提供了简单兜底的 txt/pdf 解析器（如 SimpleTxtProcessor、TikaProcessor）。这些是保障所有常规格式都能被处理的最基本实现。
# 2. 把它们放低优先级，是为了让“更强”或者“用户扩展的 processor”有机会通过更高优先级覆盖默认行为——即便用户注册了自己的 processor，也不会被默认实现抢掉路由。
# 3. 现实应用里，如果有第三方插件或自定义高级解析器（如专用的 OCR/pdf AI 拆块 processor），它们注册时会设更高优先级，然后替换这里的低优先级默认实现。
# 4. 当前（2024/06）Quivr 开源主线只在 base_processors 里定义了这些低优先级 parser。如果你没额外注册，系统只会用这些内置的。只有写插件或手动注册高优先级 processor，才会产生“高优先级的处理器”。
base_processors: ProcMapping = {
    FileExtension.txt: [
        ProcEntry(
            cls_mod="quivr_core.processor.implementations.simple_txt_processor.SimpleTxtProcessor",
            err=None,
            priority=_LOWEST_PRIORITY,
        )
    ],
    FileExtension.pdf: [
        ProcEntry(
            cls_mod="quivr_core.processor.implementations.tika_processor.TikaProcessor",
            err=None,
            priority=_LOWEST_PRIORITY,
        )
    ],
}


def _append_proc_mapping(
    mapping: ProcMapping,
    file_exts: List[FileExtension] | List[str],
    cls_mod: str,
    errtxt: str,
    priority: int | None,
):
    for file_ext in file_exts:
        if file_ext in mapping:
            try:
                # 这一句的作用是：从 mapping[file_ext] 这个处理器优先队列里，弹出（移除）一个优先级最高的 ProcEntry 条目，赋值给 prev_proc。
                # heappop 用的是 heapq 标准库，保证每次弹出的是优先级（priority 字段）数值最小、也就是“优先度最高”的 parser 条目。
                # 这样做的原因是：我们要插入新处理器时，
                # 如果没有指定 priority，就把新处理器的优先级设为“比当前最高的再高一等”（即比 prev_proc 小 1），实现“只要先注册就自动优先”。
                # 逻辑说明：
                # 1. 先从 mapping[file_ext] 这个优先队列（最小堆）里弹出（heappop）当前优先级最高的处理器 prev_proc。
                # 2. 新建一个 proc_entry。如果用户指定了 priority，就用之；否则自动赋值为“prev_proc.priority - 1”，让新处理器优先级略高（数值更小）。
                # 3. 把原本弹出的 prev_proc 再推回堆中（heappush），保证它还在队列，只是优先级没变。
                # 4. 把新建的 proc_entry 放进去，队列中顺序自动按 priority 重新调整。
                #
                # 举例：假如扩展名 .pdf 当前优先队列只有 TikaProcessor，priority 是 10000。现在新注册 PDF_OCR_Processor，没有指定 priority。
                #   - heappop 弹出 TikaProcessor（priority=10000）
                #   - 新 proc_entry 设 priority = 9999
                #   - 把 TikaProcessor 再 heappush 回堆
                #   - 把新 processor heappush 进堆
                #   此时队列里：
                #    [
                #      ProcEntry(priority=9999, ...)      # 新注册的 PDF_OCR_Processor，优先级最高
                #      ProcEntry(priority=10000, ...)     # TikaProcessor，兜底
                #    ]
                prev_proc = heappop(mapping[file_ext])
                proc_entry = ProcEntry(
                    priority=priority
                    if priority is not None
                    else prev_proc.priority - 1,
                    cls_mod=cls_mod,
                    err=errtxt,
                )
                # Push the previous processor back
                heappush(mapping[file_ext], prev_proc)
                heappush(mapping[file_ext], proc_entry)
            except IndexError:
                proc_entry = ProcEntry(
                    priority=priority if priority is not None else _LOWEST_PRIORITY,
                    cls_mod=cls_mod,
                    err=errtxt,
                )
                heappush(mapping[file_ext], proc_entry)

        # 如果 mapping 里没有 file_ext 这个 key，就会进入 else 分支。
        # 举例：如果 base_processors 只登记了 .txt 和 .pdf，
        #      但现在尝试注册 ".ocr" 这种 file_ext，
        #      就不会匹配到前面的 if file_ext in mapping（返回 False），
        #      于是执行 else 逻辑。
        # 这时候会新建一个 ProcEntry，并把它作为列表存进 mapping[file_ext]，
        # 即 mapping[".ocr"] = [proc_entry]
        # 这样 .ocr 就第一次被登记进处理器映射表（proc mapping）。
        # 下次如果有同扩展名，则进入 if 分支，实现多优先级注册。
        else:
            proc_entry = ProcEntry(
                priority=priority if priority is not None else _LOWEST_PRIORITY,
                cls_mod=cls_mod,
                err=errtxt,
            )

            # 这里不需要 heappush，是因为 mapping[file_ext] 之前不存在（没有这个 key），
            # 目前登记的 processor 是第一个，所以直接新建一个只包含 proc_entry 的列表即可。
            # 只有当已存在一个堆时，才需要用 heappush 保证堆属性，这里直接初始赋值效率更高。
            mapping[file_ext] = [proc_entry]


def defaults_to_proc_entries(
    base_processors: ProcMapping,
) -> ProcMapping:
    # TODO(@aminediro) : how can a user change the order of the processor ?
    
    # NOTE: order of this list is important as resolution of `get_processor_class` depends on it
    # We should have a way to automatically add these at 'import' time
    # 注意：下面 processor 映射表中的顺序很重要，
    # 因为 get_processor_class 函数解析文件处理器时会依赖这个顺序进行优先级判断（谁先谁被选中）。
    # 理想设计是：未来应该让这些 processor 能在包引入时自动注册到映射表，而不用手动维护列表顺序。
    for supported_extensions, processor_name in [
        ([FileExtension.csv], "CSVProcessor"),
        ([FileExtension.txt], "TikTokenTxtProcessor"),
        ([FileExtension.docx, FileExtension.doc], "DOCXProcessor"),
        ([FileExtension.xls, FileExtension.xlsx], "XLSXProcessor"),
        ([FileExtension.pptx], "PPTProcessor"),
        (
            [FileExtension.markdown, FileExtension.md, FileExtension.mdx],
            "MarkdownProcessor",
        ),
        ([FileExtension.epub], "EpubProcessor"),
        ([FileExtension.bib], "BibTexProcessor"),
        ([FileExtension.odt], "ODTProcessor"),
        ([FileExtension.html], "HTMLProcessor"),
        ([FileExtension.py], "PythonProcessor"),
        ([FileExtension.ipynb], "NotebookProcessor"),
    ]:
        for ext in supported_extensions:
            # isinstance 是 Python 的内置函数，用于判断一个变量是不是某个类或类型的实例。
            # 这里的作用是：如果 ext 是 FileExtension 枚举，比如 FileExtension.txt，
            # 那就取它的 value（如 ".txt"）；如果 ext 本来就是字符串（如 ".txt"），就直接用。
            # 这样 ext_str 最终就是标准的扩展名字符串，方便后面拼提示语句。
            # FileExtension虽然底层定义方式是继承自str和Enum（参见files/file.py定义），
            # 实例行为等价于其str值，例如FileExtension.txt的值就是".txt"。
            # 但访问.value时其实仍然是Enum的标准写法：.value 会取到它的枚举值（即".txt"）。
            # 所以这里写 ext.value 是可以的，
            # 如果ext是FileExtension，ext.value得到".txt"，
            # 如果本身就是字符串则直接用ext。
            ext_str = ext.value if isinstance(ext, FileExtension) else ext
            _append_proc_mapping(
                # 用最直白的话说：这里是整体的“处理器总表”，要登记所有类型的处理器映射关系，
                # 而不是单独只针对某个特殊处理器（比如NotebookProcessor）。
                # 只有把所有处理器都统一登记到 base_processors 这个总表里，后面系统才能根据不同文件类型自动找到对应的处理器。
                # 这里传入的是 base_processors 这个总映射表，无论前面 base_processors 里有哪些初始条目（如 txt, pdf），
                # 每次循环都会把当前 processor（比如 NotebookProcessor、MarkdownProcessor 等）追加登记到 base_processors，
                # 并用其支持的文件扩展名（如 ".ipynb"）作为 key。
                # 这样最终 base_processors 里既包含了默认的 txt/pdf，也包含了所有特殊文件格式（如 ipynb、md、csv、docx等）和它们对应的处理器，
                # 保证系统能根据不同的文件类型找到合适的 processor。
                mapping=base_processors,
                file_exts=[ext],
                cls_mod=f"quivr_core.processor.implementations.default.{processor_name}",
                # 为什么要加这个参数，有什么作用
                # errtxt 这个参数用于定义当导入指定处理器失败时报出的错误提示信息。
                # 它的作用是：让用户清楚知道缺哪个依赖、应该怎么安装（比如提示要用 quivr-core[.txt]）。
                # 这样当用户处理某类文件时缺依赖包，不会莫名其妙报 ImportError，而是看到有针对性的人类可读信息。
                # 设计上，这有助于提升可维护性、易用性和后期自定义扩展处理器时的开发体验。
                errtxt=f"can't import {processor_name}. Please install quivr-core[{ext_str}] to access {processor_name}",
                priority=None,
            )

    # TODO(@aminediro): Megaparse should register itself
    # 如何理解这句话
    # “Megaparse should register itself” 的意思是：
    # - 目前 MegaparseProcessor 是在这里手动写死追加到 processor 映射表里的（类似“兜底备用项”）。
    # - 理想状态下，MegaparseProcessor 能在它自己的模块 import 时自动把自己注册到处理器列表，
    #   即“自注册”，而不是这里每次都要写一遍。
    # - 这样未来加新 processor 也能各自负责注册自身，不依赖手工维护大表，更灵活也更好解耦。
    # 为什么要 append Megaparse？
    # Megaparse 是一个“通用兜底处理器”，用于最大兼容市面上的主流文件类型（txt, pdf, docx, pptx等）。
    # 设计目的：
    # - 1. 保证即使前面所有专属处理器都找不到/导入失败时，用户依然能解析主流文件，不至于 RAG 整链断裂。
    # - 2. 降低对单一文件类型 processor 的过度依赖，尤其是系统扩展到新格式时提升容错率。
    # - 3. 支持插件机制或自动注册时，在没有精细 processor 的情况下保证解析流程兜底能走通。
    # 通用做法是：先注册“具体格式专用 processor”（如 PDFProcessor），
    # 最后追加一个“大覆盖范围 Megaparse 兜底”——只有前面都不匹配才用它。
    _append_proc_mapping(
        mapping=base_processors,
        file_exts=[
            FileExtension.txt,
            FileExtension.pdf,
            FileExtension.docx,
            FileExtension.doc,
            FileExtension.pptx,
            FileExtension.xls,
            FileExtension.xlsx,
            FileExtension.csv,
            FileExtension.epub,
            FileExtension.bib,
            FileExtension.odt,
            FileExtension.html,
            FileExtension.markdown,
            FileExtension.md,
            FileExtension.mdx,
        ],
        cls_mod="quivr_core.processor.implementations.megaparse_processor.MegaparseProcessor",
        errtxt=f"can't import MegaparseProcessor. Please install quivr-core[{ext_str}] to access MegaparseProcessor",
        priority=None,
    )
    return base_processors


known_processors = defaults_to_proc_entries(base_processors)


def get_processor_class(file_extension: FileExtension | str) -> Type[ProcessorBase]:
    """Fetch processor class from registry

    The dict ``known_processors`` maps file extensions to the locations
    of processors that could process them.
    Loading of these classes is *Lazy*. Appropriate import will happen
    the first time we try to process some file type.

    Some processors need additional dependencies. If the import fails
    we return the "err" field of the ProcEntry in  ``known_processors``.
    """

    # registry 和 known_processors 的区别：
    # - registry 是当前已经“动态导入并注册”到系统里的 processor 类，只能读不能直接写（MappingProxyType），代表“已加载的处理器”。
    # - known_processors 是所有“已知可用 processor”及其路径的静态映射（通常基于配置或预埋表），记录所有支持的文件类型能有哪些候选处理器（即便没真实 import 过）。
    #
    # 两层 if 判断原因：
    # 1. 先判 registry：优先用当前 registry 中现成的 processor（也可能是用户在运行时自定义注册的），无需重复动态导入和 heappop，从而提升性能。
    # 2. 如果 registry（已加载）里没有，才进入 known_processors——
    #    这一步根据静态已知的 processor 路径/优先级表，尝试依次加载并 register 到 registry 里（惰性 import 加 lazy register），直到有一个能 import 成功为止
    # 3. 如果 known_processors 里都导入失败/没有映射，再报错
    #
    # 这样的分层保证了：
    # - 已注册 processor 直接查找、性能好
    # - 支持大量“未主动导入”的候选 processor，只有用到时才动态 import & register，兼容插件、扩展、动态分发
    # - 依赖静态表供自动 fallback，不会因未注册而直接断链
    
    # registry: dict[str, Type[ProcessorBase]] 仅可读
    if file_extension not in registry:
        # Step 1: 如果连静态 known_processors 都没有映射，说明完全不支持该扩展名，直接报错
        if file_extension not in known_processors:
            raise ValueError(f"Extension not known: {file_extension}")
        # Step 2: 依据优先级从 known_processors 里取候选 processor 尝试动态导入和注册
        entries = known_processors[file_extension]
        while entries:
            proc_entry = heappop(entries)
            try:
                # 动态 import processor 类并注册到 registry
                register_processor(file_extension, _import_class(proc_entry.cls_mod))
                break
            except ImportError:
                logger.warn(
                    f"{proc_entry.err}. Falling to the next available processor for {file_extension}"
                )
        # Step 3: 全部导入失败 或 刚刚无新注册的情况下最终兜底报错
        if len(entries) == 0 and file_extension not in registry:
            raise ImportError(f"can't find any processor for {file_extension}")

    cls = registry[file_extension]
    return cls


    """
    注册（或追加）一个新的文件处理器（processor）。

    这个方法实现了 processor 的动态注册表管理，允许在运行期为指定文件扩展名增加或覆盖处理器逻辑。
    它支持两种类型的 proc_cls：
      - 字符串（processor 的 import 路径），用于延迟加载/异常处理
      - 直接传入的 ProcessorBase 的子类类型
    主要用于支持插件、扩展自定义，或在 known_processors 静态表基础上追加新实现。
    
    参数说明:
    - file_ext: 需要注册的文件扩展名（如 ".pdf"），可为 FileExtension 枚举或 str
    - proc_cls: 处理器类本身（类型对象），或其 import 路径（字符串）
    - append: 针对字符串模式，是否允许追加新候选项到 known_processors
    - override: 针对类型对象模式，是否允许覆盖已存在的 processor（否则如已注册则报错）
    - errtxt: 字符串模式指定 import 失败时的错误提示文本
    - priority: 字符串模式注册时的新候选项优先级，越小越高，允许自定义 fallback 顺序

    主要逻辑分为两种分支：
    1. 如果 proc_cls 是字符串（懒导入模式）:
        - 检查 file_ext 是否已经存在于 known_processors
            - 如果 append=False 并且已存在同样路径，则报错，避免重复注册
            - 否则，如果该路径没有出现在已有候选项中，则追加进映射表
        - 有相同路径则 log 提示；否则真正追加。

    2. 如果 proc_cls 是已导入的处理器类型（动态覆盖模式）:
        - 要求必须是 ProcessorBase 子类
        - 若已在 registry 存在且 override=False，且类型不同，则报错，防止误覆盖
        - 否则直接在 registry 映射（可用于强制覆盖内置或热插拔第三方 processor）
    
    设计意义：
    - 动态分层抽象，支持静态声明和运行期注入两类 processor 管理模式
    - 用 append/override 控制注册覆盖、fallback 追加等多种典型插件场景
    - 保证系统既能稳定 fallback 到静态表，也能灵活扩展

    执行顺序：
    - 输入一个文件扩展名和处理器（路径或类型）
    - 按类型决定是 known_processors（静态候选表）还是 registry（实际可用类对象）的注册
    - 保证 idempotency（不会重复注册相同 processor），出错时合理提示
    """
def register_processor(
    file_ext: FileExtension | str,
    proc_cls: str | Type[ProcessorBase],
    append: bool = True,
    override: bool = False,
    errtxt: str | None = None,
    priority: int | None = None,
):  
    # 不在register而在known_processor, 则pop一个processor
    if isinstance(proc_cls, str):
        if file_ext in known_processors and append is False:
            if all(proc_cls != proc.cls_mod for proc in known_processors[file_ext]):
                raise ValueError(
                    f"Processor for ({file_ext}) already in the registry and append is False"
                )
        else:
            # 这里只操作 known_processors，不直接注册到 _registry（不会 import/加载类），
            # 设计目的：字符串路径模式允许延迟加载处理器，
            # - 先补进 known_processors，实际用到时才 import/初始化进 _registry。
            # - 这样可以支持动态导入、依赖可选、插件懒加载等场景，
            # - 避免未用到的第三方依赖、实验性处理器污染主进程或引入额外依赖错误。
            # - 对应“静态候选表”这层；只有确定用到的扩展名才实际注册到 _registry。
            if all(proc_cls != proc.cls_mod for proc in known_processors[file_ext]):
                _append_proc_mapping(
                    known_processors,
                    file_exts=[file_ext],
                    cls_mod=proc_cls,
                    errtxt=errtxt
                    or f"{proc_cls} import failed for processor of {file_ext}",
                    priority=priority,
                )
            else:
                logger.info(f"{proc_cls} already in registry...")

    else:
        assert issubclass(
            proc_cls, ProcessorBase
        ), f"{proc_cls} should be a subclass of quivr_core.processor.ProcessorBase"
        if file_ext in registry and override is False:
            if _registry[file_ext] is not proc_cls:
                raise ValueError(
                    f"Processor for ({file_ext}) already in the registry and append is False"
                )
        else:
            # 这里只更新到 registry，而不是 known_processors，原因如下：
            # - registry 存放的是“已实际 import 过、可直接实例化的类对象”，
            #   用于文件解析主流程里直接 new processor（即 import 加载好的实现）。
            # - known_processors 是“字符串路径”静态候选表，负责收集所有声明支持的处理器条目，
            #   但它只存元信息（如待 import 路径/可能依赖），并不等价于已可用——
            #   只有 registry 表里登记的，才真正能在主链路实例化执行。
            # - 这样设计是为了分层管理：
            #   - known_processors 更像一个全局声明/插件注册信息，按需延迟加载。
            #   - registry 是最终 runtime 里生效的路由表，是“可直接 new 实例”的活跃 processor 列表。
            #   - 不直接改 known_processors，防止 import 失败/动态依赖时破坏声明与实现的分离。
            # - 总结：只有真正 import 成功的 processor 类，才应加入 registry，确保主链路可稳定实例化与类型检查。
            _registry[file_ext] = proc_cls


def _import_class(full_mod_path: str):
    if ":" in full_mod_path:
        mod_name, name = full_mod_path.rsplit(":", 1)
    else:
        mod_name, name = full_mod_path.rsplit(".", 1)

    mod = importlib.import_module(mod_name)

    for cls in name.split("."):
        mod = getattr(mod, cls)

    if not isinstance(mod, type):
        raise TypeError(f"{full_mod_path} is not a class")

    if not issubclass(mod, ProcessorBase):
        raise TypeError(f"{full_mod_path} is not a subclass of ProcessorBase ")

    return mod


def available_processors():
    """Return a list of the known processors."""
    return list(known_processors)
