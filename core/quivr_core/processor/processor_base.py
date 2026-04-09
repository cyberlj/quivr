import logging
from abc import ABC, abstractmethod
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Generic, List, TypeVar

from attr import dataclass
from langchain_core.documents import Document

from quivr_core.files.file import FileExtension, QuivrFile
from quivr_core.language.utils import detect_language

logger = logging.getLogger("quivr_core")


R = TypeVar("R", covariant=True)


@dataclass
class ProcessedDocument(Generic[R]):
    chunks: List[Document]
    processor_cls: str
    # 这里没有直接用 Any，而是用 R 这个类型变量（TypeVar），是为了让 ProcessedDocument 能“泛型”——即支持不同的处理结果类型（比如 str、dict、或者别的结构体），由模块实例化或子类化时灵活指定。这样类型检查工具能更精确推断每次用到的 processor_response 的真实类型，代码更安全、可维护、提示更智能。如果用 Any，就永远没法知道 processor_response 具体是什么类型，类型检查和 IDE 支持都会变弱。
    processor_response: R

# TODO: processors should be cached somewhere ?
# The processor should be cached by processor type
# The cache should use a single
# TODO: 未来需要实现处理器（processor）缓存机制
# 建议按处理器类型缓存，可以使用单例或全局缓存以提升文件处理性能。
# 原因说明：有些处理器的初始化过程可能涉及较重的资源创建（如加载大模型、初始化分词器、导入外部依赖），每次实例化都会带来多余的开销。
# 通过缓存同类型的 processor 实例，避免重复初始化，能减少内存消耗、提升文件处理速度，整体优化系统资源利用率。
class ProcessorBase(ABC, Generic[R]):
    supported_extensions: list[FileExtension | str]

    def check_supported(self, file: QuivrFile) -> None:
        if file.file_extension not in self.supported_extensions:
            raise ValueError(f"can't process a file of type {file.file_extension}")

    @property
    @abstractmethod
    def processor_metadata(self) -> dict[str, Any]:
        raise NotImplementedError

    async def process_file(self, file: QuivrFile) -> ProcessedDocument[R]:
        logger.debug(f"Processing file {file}")
        self.check_supported(file)
        docs = await self.process_file_inner(file)
        try:
            # 这一行可能会报错进入 except，因为 version("quivr-core") 会尝试获取 quivr-core 包的安装版本号。
            # 如果当前运行环境没有通过 pip/poetry 等标准方式安装过 quivr-core，或者包的元数据没有被正确写入（比如开发模式下直接改源码跑，没有装 dist-info），
            # importlib.metadata.version 查不到包名时就会抛出 PackageNotFoundError。
            qvr_version = version("quivr-core")
        except PackageNotFoundError:
            qvr_version = "dev"

        # 这里遍历 docs.chunks 得到每个切块文档（doc），并且同时用 enumerate 给每个 chunk 分配一个递增的编号 idx（从1开始）。
        # 这个编号后面对 metadata["chunk_index"] 很重要，方便追踪和定位每个块（分片）。
        # doc 是 langchain_core.documents.Document 的实例，metadata 是它的元数据字典，具体内容根据实际解析出来的数据决定，
        # 包含了如文件名、页面、分块索引、quivr_core 版本等字段。
        # 你可以把 metadata 看作类似 schema 的动态补充结构——每次循环都动态增加或覆盖一些元信息，最后存入每个 doc 实例，便于后续检索排序。
        for idx, doc in enumerate(docs.chunks, start=1):
            if "original_file_name" in doc.metadata:
                doc.page_content = f"Filename: {doc.metadata['original_file_name']} Content: {doc.page_content}"
            # 为什么要这么做：
            # 某些 PDF 或其它文件解码为文本的时候，可能会残留 NUL 字符（\u0000），
            # 这种字符在很多文本处理库、下游检索代码、存储层都会导致异常错误或隐藏 Bug。
            # 为了保证 page_content 的每一块都是“干净的纯文本”，这里要主动把所有 \u0000 清理掉。
            doc.page_content = doc.page_content.replace("\u0000", "")
            # 这一行代码的逻辑是：把 doc.page_content 里的内容强制转成 utf-8 合规的纯文本，遇到无法正常用 utf-8 表示的字符时用特殊符号“�”替换，保证内容不会报错。
            # 举例：假如 doc.page_content 原本是 "hello世界\uDCFFabc"
            # 其中 \uDCFF 是一个非法的 Unicode 代理符，不能直接编码成 utf-8。
            # 执行 encode("utf-8", "replace") 后，会把 \uDCFF 变成"�"，全流程如下：
            # 原始: "hello世界\uDCFFabc"
            # encode: b'hello\xe4\xb8\x96\xe7\x95\x8c�abc'
            # decode: "hello世界�abc"
            # 这样就不会因为内容有非法字符而导致后续处理报错，并且所有“异常”内容都统一用可见的替换符表示出来，方便定位和兼容存储、检索。
            doc.page_content = doc.page_content.encode("utf-8", "replace").decode("utf-8")
            doc.metadata = {
                "chunk_index": idx,
                "quivr_core_version": qvr_version,
                "language": detect_language(
                    text=doc.page_content.replace("\\n", " ").replace("\n", " "),
                    low_memory=True,
                ).value,
                # file.metadata 表示源文件（QuivrFile）级别的元数据，比如：{"original_file_name": "abc.pdf", "uploaded_by": "user1"}
                # doc.metadata 通常是每个 chunk（分片）的原始元数据，比如 PDF 切第3页时：{"page": 3, "source": "extracted from page 3"}
                # 使用 ** 解包是让两个字典的所有键值对直接展开合并到新的 metadata 里，不会多层嵌套。
                # 顺序上，**doc.metadata 放在后面，可以让 chunk 层的信息覆盖文件的同名字段（比如针对每一分块更新 page、source）。
                # 举例说明：
                #   file.metadata = {"original_file_name": "abc.pdf", "author": "张三"}
                #   doc.metadata  = {"page": 2, "source": "extracted from page 2"}
                #   合并后效果：
                #   metadata = {
                #       "chunk_index": idx,
                #       "quivr_core_version": qvr_version,
                #       "language": detect_language(...),
                #       "original_file_name": "abc.pdf",
                #       "author": "张三",
                #       "page": 2,
                #       "source": "extracted from page 2",
                #       ...其它字段
                #   }
                **file.metadata,    # 文件全局属性，先展开
                **doc.metadata,     # chunk 独有属性，紧跟其后，支持覆盖同名字段
                # processor_metadata 典型字段有哪些？在 RAG/agent 框架里，processor_metadata 常见字段有：
                # - "processor_name"：当前解析器名称（如 "SimpleTxtProcessor"、"TikaProcessor"）
                # - "processor_type"：解析器类别（如 "pdf"，"txt"，"image"）
                # - "processor_version"：解析器实现/插件版本号，便于溯源和升级
                # - "processed_at"：本次处理的时间戳（ISO 格式）
                # - "processing_time_ms"：解析和切块所耗时长（毫秒）
                # - "parser_backend"：底层用的是哪个解析库/引擎，比如 "PyPDF2"、"Tika"
                # - ...其它定制扩展字段（如由插件、企业自定义注入）
                # 这些字段主要用于：
                # - 让每个 chunk 记录解析具体由谁、如何产生，增强可溯源性与 debug 能力；
                # - 便于下游展示、统计“哪些处理器贡献了多少文档”或自动选择不同解析策略；
                # - 支持注册更多元的 processor 拓展，meta 字段不会破坏主 schema 可灵活兼容。
                **self.processor_metadata,
            }
        return docs

    @abstractmethod
    async def process_file_inner(self, file: QuivrFile) -> ProcessedDocument[R]:
        raise NotImplementedError
