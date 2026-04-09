import asyncio
import logging
import os
from pathlib import Path
from pprint import PrettyPrinter
from typing import Any, AsyncGenerator, Callable, Dict, Self, Type, Union
from uuid import UUID, uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from rich.console import Console
from rich.panel import Panel

from quivr_core.brain.info import BrainInfo, ChatHistoryInfo
from quivr_core.brain.serialization import (
    BrainSerialized,
    EmbedderConfig,
    FAISSConfig,
    LocalStorageConfig,
    TransparentStorageConfig,
)
from quivr_core.files.file import load_qfile
from quivr_core.llm import LLMEndpoint
from quivr_core.processor.registry import get_processor_class
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import RetrievalConfig
from quivr_core.rag.entities.models import (
    LangchainMetadata,
    ParsedRAGChunkResponse,
    ParsedRAGResponse,
    QuivrKnowledge,
    SearchResult,
)
from quivr_core.rag.quivr_rag import QuivrQARAG
from quivr_core.rag.quivr_rag_langgraph import QuivrQARAGLangGraph
from quivr_core.storage.local_storage import LocalStorage, TransparentStorage
from quivr_core.storage.storage_base import StorageBase

from .brain_defaults import build_default_vectordb, default_embedder, default_llm

logger = logging.getLogger("quivr_core")


async def process_files(
    storage: StorageBase, skip_file_error: bool, **processor_kwargs: dict[str, Any]
) -> list[Document]:
    """
    Process files in storage.
    This function takes a StorageBase and return a list of langchain documents.
    Args:
        storage (StorageBase): The storage containing the files to process.
        skip_file_error (bool): Whether to skip files that cannot be processed.
        processor_kwargs (dict[str, Any]): Additional arguments for the processor.
    Returns:
        list[Document]: List of processed documents in the Langchain Document format.
    Raises:
        ValueError: If a file cannot be processed and skip_file_error is False.
        Exception: If no processor is found for a file of a specific type and skip_file_error is False.
    """

    # =========================
    # 这段函数的教学视角
    # =========================
    # 输入:
    # - storage: 前面已经登记过用户文件的存储层
    # - skip_file_error: 某个文件解析失败时，是继续还是直接报错
    # - processor_kwargs: 要传给具体 parser / splitter 的额外参数
    #
    # 输出:
    # - list[Document]
    #
    # 在 RAG 系统里的角色:
    # - 这是“文档标准化层”
    # - 它把 storage 中的“文件对象”统一变成后续检索可以使用的“文档块对象”
    #
    # 关键理解:
    # - RAG 后面的 embedding、向量检索、rerank 都不想直接处理 PDF/TXT
    # - 所以必须先把不同格式文件统一转换成 LangChain Document
    #
    # 状态变化:
    # - 输入: QuivrFile
    # - 输出: Document / chunk
    knowledge = []
    for file in await storage.get_files():
        try:
            if file.file_extension:
                # 这一步在做“parser 路由”。
                # 系统不会写死“所有文件都用同一个处理器”，
                # 而是根据扩展名动态找到对应 processor。
                #
                # 例如:
                # - .pdf -> PDF processor
                # - .txt -> TXT processor
                # - .md  -> Markdown processor
                #
                # 这也是 Quivr 文件处理可扩展的关键：新增格式时，不需要改 `Brain`。
                processor_cls = get_processor_class(file.file_extension)
                logger.debug(f"processing {file} using class {processor_cls.__name__}")
                # 这里实例化具体 processor。
                # 从这一刻开始，后续处理逻辑由对应文件类型的 processor 接管。
                processor = processor_cls(**processor_kwargs)
                # 这一句是“真正解析文件”的地方。
                #
                # processor.process_file(file) 通常会做这些事:
                # 1. 读取文件内容
                # 2. 提取文本
                # 3. 按 splitter 规则切块
                # 4. 把每个块包装成 LangChain Document
                #
                # 所以 docs 往往不是“一个文件对应一个对象”，
                # 而是“一个文件对应多个 chunk 文档”。
                docs = await processor.process_file(file)
                # 这里把某个文件解析出来的所有文档块，追加到总知识列表 knowledge 里。
                # knowledge 最终会成为后续建向量库的输入。
                knowledge.extend(docs.chunks)
            else:
                logger.error(f"can't find processor for {file}")
                if skip_file_error:
                    continue
                else:
                    raise ValueError(f"can't parse {file}. can't find file extension")
        except KeyError as e:
            if skip_file_error:
                continue
            else:
                raise Exception(f"Can't parse {file}. No available processor") from e

    return knowledge


class Brain:
    """
    A class representing a Brain.
    This class allows for the creation of a Brain, which is a collection of knowledge one wants to retrieve information from.
    A Brain is set to:
    * Store files in the storage of your choice (local, S3, etc.)
    * Process the files in the storage to extract text and metadata in a wide range of format.
    * Store the processed files in the vector store of your choice (FAISS, PGVector, etc.) - default to FAISS.
    * Create an index of the processed files.
    * Use the *Quivr* workflow for the retrieval augmented generation.
    A Brain is able to:
    * Search for information in the vector store.
    * Answer questions about the knowledges in the Brain.
    * Stream the answer to the question.
    Attributes:
        name (str): The name of the brain.
        id (UUID): The unique identifier of the brain.
        storage (StorageBase): The storage used to store the files.
        llm (LLMEndpoint): The language model used to generate the answer.
        vector_db (VectorStore): The vector store used to store the processed files.
        embedder (Embeddings): The embeddings used to create the index of the processed files.
    """

    def __init__(
        self,
        *,
        name: str,
        llm: LLMEndpoint,
        id: UUID | None = None,
        vector_db: VectorStore | None = None,
        embedder: Embeddings | None = None,
        storage: StorageBase | None = None,
        workspace_id: UUID | None = None,
        chat_id: UUID | None = None,
    ):
        self.id = id
        self.name = name
        self.storage = storage
        self.workspace_id = workspace_id
        self.chat_id = chat_id
        # `Brain` 是顶层门面对象：
        # 它把 storage、vector_db、embedder、llm 和 chat history 收敛到一个入口。
        # 外部只和 `Brain` 交互，不直接拼装底层 RAG 组件。
        # Chat history
        self._chats = self._init_chats()
        self.default_chat = list(self._chats.values())[0]

        # RAG dependencies:
        self.llm = llm
        self.vector_db = vector_db
        self.embedder = embedder

    def __repr__(self) -> str:
        # `__repr__` 不参与 RAG 主流程。
        # 它的作用是“调试展示层”：
        # 当你在控制台直接打印 Brain 对象时，会把 `info()` 结果格式化输出。
        pp = PrettyPrinter(width=80, depth=None, compact=False, sort_dicts=False)
        return pp.pformat(self.info())

    def print_info(self):
        # 这也是“调试展示层”函数。
        # 它不会改变 Brain 内部状态，只负责把 `info()` 的结构化信息
        # 用 Rich 面板格式打印出来，方便人类查看当前知识库概况。
        console = Console()
        tree = self.info().to_tree()
        panel = Panel(tree, title="Brain Info", expand=False, border_style="bold")
        console.print(panel)

    @classmethod
    def load(cls, folder_path: str | Path) -> Self:
        """
        Load a brain from a folder path.
        Args:
            folder_path (str | Path): The path to the folder containing the brain.
        Returns:
            Brain: The brain loaded from the folder path.
        Example:
        ```python
        brain_loaded = Brain.load("path/to/brain")
        brain_loaded.print_info()
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - folder_path: 一个之前 `save(...)` 过的 brain 目录
        #
        # 输出:
        # - 一个从磁盘反序列化恢复出来的 Brain
        #
        # 在 RAG 系统里的角色:
        # - 这是“知识库恢复层”
        # - 它把之前保存到磁盘的配置、文件信息、向量库重新组装回可运行的 Brain
        #
        # 核心理解:
        # - `afrom_files(...)` 是“从原始文件创建知识库”
        # - `load(...)` 是“从已保存快照恢复知识库”
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)
        if not folder_path.exists():
            raise ValueError(f"path {folder_path} doesn't exist")

        # 第 1 阶段：读取 Brain 的序列化配置。
        # `config.json` 里保存的是这个 Brain 的元信息、storage 配置、embedding 配置、向量库配置等。
        with open(os.path.join(folder_path, "config.json"), "r") as f:
            # 是的，这行代码会把 config.json 文件中的 JSON 字符串“反序列化”为一个 BrainSerialized 对象实例（即 Pydantic 数据模型）。
            # 再具体点：它会把磁盘文件里保存的配置信息（原本是 dict/JSON 结构）还原成可以属性访问和类型检查的对象（bserialized），
            # 方便后面直接用 bserialized.xxx 读字段，而不是手动解析 json/dict。
            bserialized = BrainSerialized.model_validate_json(f.read())

        storage: StorageBase | None = None
        # 第 2 阶段：恢复 storage。
        # 这里不是重新上传用户文件，而是根据保存时记录的 storage_config 重建 storage 对象。
        if bserialized.storage_config.storage_type == "transparent_storage":
            storage = TransparentStorage.load(bserialized.storage_config)
        elif bserialized.storage_config.storage_type == "local_storage":
            storage = LocalStorage.load(bserialized.storage_config)
        else:
            raise ValueError("unknown storage")

        # 第 3 阶段：恢复 embedder。
        # 注意这里并不是重新做 embedding，而是恢复“以后查询时需要用的 embedding 工具”。
        # 第 3 阶段：恢复 embedder
        # 作用说明：
        # - load 这里根据序列化数据还原出用于“文本转向量”的嵌入器（embedder）
        # - 决定后续 RAG 检索时向量的生成方式，和原始语料无关，只影响未来“用户问题转向量”；保持和建库时 embedding 保持一致
        # - 在RAG系统里，这层相当于“向量化标准层”，整个知识库的可检索性、可兼容性依赖于这里的实现
        # 
        # 关于可选项：
        # - 当前代码只实现了 openai_embedding，因此只能用 OpenAIEmbeddings
        # - 但设计上 embedder_type 字段用于后续支持更多 embedding 工具，如本地 Huggingface、国产模型、自研向量器等
        # - 只需后续加 elif 分支即可支持更多 embedding 类
        if bserialized.embedding_config.embedder_type == "openai_embedding":
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(**bserialized.embedding_config.config)
        # elif bserialized.embedding_config.embedder_type == "xxx":
        #     # 支持更多本地/自研 embedding
        #     from your_lib import YourEmbedding
        #     embedder = YourEmbedding(**bserialized.embedding_config.config)
        else:
            raise ValueError("unknown embedder: 当前仅支持 openai_embedding，可扩展更多 embedding 实现")

        # ================== 教学补充 ==================
        # OpenAIEmbeddings优缺点对比：
        # 优点：
        #   - 性能好：API 官方部署，速度快，可靠性高
        #   - 质量高：覆盖大部分主流语种，对英语检索效果优异，有多模型可选
        #   - 无需本地部署：直接调用云 API，节省机器、维护、人力成本
        #   - 生态好：主流 vector DB、RAG 框架都有原生集成
        # 缺点：
        #   - 成本高：API 计费（按 token/调用量），大规模接入费用可观
        #   - 受限于外网/合规：出海和敏感业务可能不适用，数据出云有泄露风险
        #   - 定制性弱：无法针对私域语料做微调/custom embedding
        #   - QPS有限制：API易受限速、网络波动影响高并发可用性
        #   - 隐私顾虑：有些行业（金融、医疗等）不愿明文调云端 embedding
        #
        # 实际生产使用哪种？
        # - 创业/原型期、海外业务、小团队常选第三方 OpenAI/百度/阿里等 Embedder 成品，省心无维护压力
        # - 数据合规/隐私、海量大库、特定领域效果追求、高吞吐等场景，大中型公司更倾向于自研或本地化 embedding（Huggingface模型、国产模型等），
        #   可以微调/自控数据，且成本可控、适配业务需要
        # - 典型解决方案是：小量快速用第三方 embedding，大规模/私有化时换本地 embedding，两者用统一接口封装

        # 第 4 阶段：恢复向量库。
        # 这里真正恢复的是“已经建好的知识库索引”，
        # 所以 load 后的 Brain 不需要重新走文件解析和建库流程。
        if bserialized.vectordb_config.vectordb_type == "faiss":
            from langchain_community.vectorstores import FAISS

            vector_db = FAISS.load_local(
                folder_path=bserialized.vectordb_config.vectordb_folder_path,
                embeddings=embedder,
                # allow_dangerous_deserialization=True 表示允许在加载 FAISS 本地 vectorstore 时，使用 pickle 反序列化（强制解包内部对象）
                # 这样做会提升兼容性，但带来一定安全风险——只建议加载可信来源的索引
                # 如果设为 False，则更安全，但一旦保存的 faiss 索引对象中包含复杂自定义对象（如自定义嵌入器等）会导致加载失败
                allow_dangerous_deserialization=True,
            )
        else:
            raise ValueError("Unsupported vectordb")

        return cls(
            id=bserialized.id,
            name=bserialized.name,
            embedder=embedder,
            llm=LLMEndpoint.from_config(bserialized.llm_config),
            storage=storage,
            vector_db=vector_db,
        )

    async def save(self, folder_path: str | Path):
        """
        Save the brain to a folder path.
        Args:
            folder_path (str | Path): The path to the folder where the brain will be saved.
        Returns:
            str: The path to the folder where the brain was saved.
        Example:
        ```python
        await brain.save("path/to/brain")
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 一个已经建好的 Brain
        # - 目标保存目录 folder_path
        #
        # 输出:
        # - 保存后的 brain 目录路径
        #
        # 在 RAG 系统里的角色:
        # - 这是“知识库持久化层”
        # - 它把当前 Brain 的运行状态转换成磁盘可恢复格式
        #
        # 保存的核心对象包括:
        # - 向量库
        # - embedder 配置
        # - llm 配置
        # - storage 中文件信息
        # - chat history 元数据
        if isinstance(folder_path, str):
            folder_path = Path(folder_path)

        # 第 1 阶段：创建这个 Brain 对应的保存目录。
        brain_path = os.path.join(folder_path, f"brain_{self.id}")
        os.makedirs(brain_path, exist_ok=True)

        from langchain_community.vectorstores import FAISS

        # 第 2 阶段：保存向量库。
        # 这里保存的是真正的检索索引，是知识库最核心的部分。
        if isinstance(self.vector_db, FAISS):
            vectordb_path = os.path.join(brain_path, "vector_store")
            os.makedirs(vectordb_path, exist_ok=True)
            self.vector_db.save_local(folder_path=vectordb_path)
            vector_store = FAISSConfig(vectordb_folder_path=vectordb_path)
        else:
            raise Exception("can't serialize other vector stores for now")

        # 第 3 阶段：保存 embedder 配置。
        # 注意保存的是“配置”，不是所有向量重新计算结果。
        if isinstance(self.embedder, OpenAIEmbeddings):
            embedder_config = EmbedderConfig(
                config=self.embedder.dict(exclude={"openai_api_key"})
            )
        else:
            raise Exception("can't serialize embedder other than openai for now")

        storage_config: Union[LocalStorageConfig, TransparentStorageConfig]
        # 第 4 阶段：保存 storage 中文件信息。
        # 这里会把 storage 当前登记的文件逐个 serialize，方便 load(...) 时恢复。
        # TODO : each instance should know how to serialize/deserialize itself
        if isinstance(self.storage, LocalStorage):
            serialized_files = {
                f.id: f.serialize() for f in await self.storage.get_files()
            }
            storage_config = LocalStorageConfig(
                storage_path=self.storage.dir_path, files=serialized_files
            )
        elif isinstance(self.storage, TransparentStorage):
            serialized_files = {
                f.id: f.serialize() for f in await self.storage.get_files()
            }
            storage_config = TransparentStorageConfig(files=serialized_files)
        else:
            raise Exception("can't serialize storage. not supported for now")

        # 第 5 阶段：汇总成 BrainSerialized，并写入 config.json。
        bserialized = BrainSerialized(
            id=self.id,
            name=self.name,
            chat_history=self.chat_history.get_chat_history(),
            llm_config=self.llm.get_config(),
            vectordb_config=vector_store,
            embedding_config=embedder_config,
            storage_config=storage_config,
        )

        with open(os.path.join(brain_path, "config.json"), "w") as f:
            f.write(bserialized.model_dump_json())
        return brain_path

    def info(self) -> BrainInfo:
        # `info()` 是“结构化状态查看层”。
        # 它不参与检索或生成，而是把当前 Brain 的关键状态整理成统一对象，
        # 给 `print_info()`、`__repr__()` 等展示函数使用。
        # TODO: dim of embedding
        # "embedder": {},
        chats_info = ChatHistoryInfo(
            nb_chats=len(self._chats),
            current_default_chat=self.default_chat.id,
            current_chat_history_length=len(self.default_chat),
        )

        return BrainInfo(
            brain_id=self.id,
            brain_name=self.name,
            files_info=self.storage.info() if self.storage else None,
            chats_info=chats_info,
            llm_info=self.llm.info(),
        )

    @property
    def chat_history(self) -> ChatHistory:
        # 这个属性是默认 chat 的只读访问入口。
        # 在多轮问答场景里，外部通常不直接读 `_chats`，
        # 而是通过 `chat_history` 获取当前默认会话。
        return self.default_chat

    def _init_chats(self) -> Dict[UUID, ChatHistory]:
        # 这是“会话初始化层”。
        # 每个 Brain 创建时都会自动带一个默认 chat。
        #
        # 在 RAG 里，它的角色是：
        # - 为多轮问答提供初始上下文容器
        # - 后续 ask/ask_streaming 会把问答结果追加进这里
        chat_id = uuid4()
        default_chat = ChatHistory(chat_id=chat_id, brain_id=self.id)
        return {chat_id: default_chat}

    @classmethod
    async def afrom_files(
        cls,
        *,
        name: str,
        file_paths: list[str | Path],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
        skip_file_error: bool = False,
        processor_kwargs: dict[str, Any] | None = None,
    ):
        """
        Create a brain from a list of file paths.
        Args:
            name (str): The name of the brain.
            file_paths (list[str | Path]): The list of file paths to add to the brain.
            vector_db (VectorStore | None): The vector store used to store the processed files.
            storage (StorageBase): The storage used to store the files.
            llm (LLMEndpoint | None): The language model used to generate the answer.
            embedder (Embeddings | None): The embeddings used to create the index of the processed files.
            skip_file_error (bool): Whether to skip files that cannot be processed.
            processor_kwargs (dict[str, Any] | None): Additional arguments for the processor.
        Returns:
            Brain: The brain created from the file paths.
        Example:
        ```python
        brain = await Brain.afrom_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        brain.print_info()
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - name: 这次知识库的显示名称
        # - file_paths: 用户提供的原始文件路径，例如 ["docs/a.pdf", "notes/b.txt"]
        # - storage/vector_db/llm/embedder: 可选底层依赖；不传就走框架默认实现
        #
        # 输出:
        # - 一个可直接 `ask(...)` 的 Brain
        #
        # 在 RAG 系统里的角色:
        # - 这是“建库入口”
        # - 它负责把“原始文件”逐步加工成“可检索知识库”
        #
        # 你可以把这个函数看成 6 个阶段:
        # 1. 准备默认模型依赖
        # 2. 生成本次知识库的唯一身份
        # 3. 把用户文件登记进 storage
        # 4. 把文件解析成标准化文档 docs
        # 5. 把 docs 建成向量索引
        # 6. 把这些依赖封装成 Brain 返回
        if llm is None:
            # 第 1 阶段：准备生成侧依赖。
            # 这里检查用户是否手动传入了 llm。
            # 如果没有，就分配一个默认 LLM。
            #
            # 这一步在 RAG 中负责“生成层”：
            # 后面检索出上下文后，最终由这个模型负责回答。
            llm = default_llm()

        if embedder is None:
            # 第 1 阶段的另一半：准备检索侧依赖。
            # embedder 负责把文本块转换成向量。
            #
            # 注意:
            # - 现在还没有真的做 embedding
            # - 这里只是把“以后要用来做 embedding 的工具”准备好
            #
            # 它在 RAG 中负责“索引构建层”和“召回层”的基础能力。
            embedder = default_embedder()

        # 如果调用方没传额外 processor 参数，就用空字典。
        # 这会在后面传给具体 parser / splitter。
        processor_kwargs = processor_kwargs or {}

        # 第 2 阶段：给这次知识库生成唯一 ID。
        # 这个 brain_id 的作用是“归属标识”。
        #
        # 后面这些资源都会和它关联起来:
        # - 上传的文件
        # - 解析后的文档块
        # - chat history
        # - 最终生成的 Brain
        brain_id = uuid4()

        # TODO: run in parallel using tasks

        # 第 3 阶段：把用户文件登记到 storage。
        #
        # 例子:
        # 用户传入 "/tmp/a.pdf"
        # -> load_qfile(...) 读这个路径，生成一个 QuivrFile
        # -> QuivrFile 附带 brain_id、sha1、扩展名、原文件名
        # -> storage.upload_file(...) 把这个文件对象放进 storage
        #
        # 这一阶段在 RAG 中属于“文件登记层”。
        # 它完成的是“让系统知道有哪些源文件”。
        #
        # 很重要的一点:
        # - 这里还没有切块
        # - 这里还没有向量化
        # - 这里还没有形成知识库
        #
        # 也就是说，此时文件只是进入了 Quivr 的内部管理体系。
        for path in file_paths:
            # `path` 是用户传进来的原始路径字符串或 Path。
            # 这一句把“外部文件路径”转成“Quivr 内部统一文件对象”。
            file = await load_qfile(brain_id, path)
            # 这一句才是真正的“存入 storage”。
            # 默认 TransparentStorage 会把文件对象登记在内存里；
            # LocalStorage 则会复制/链接文件到本地目录并记录文件对象。
            await storage.upload_file(file)

        logger.debug(f"uploaded all files to {storage}")

        # 第 4 阶段：把已登记文件解析成标准文档 docs。
        #
        # 这里发生的是整个建库过程里的第一次“数据形态变化”:
        # - 输入: QuivrFile 列表（文件对象）
        # - 输出: LangChain Document 列表（文本块对象）
        #
        # 这一阶段在 RAG 中属于“文档标准化层”。
        # 它要解决的问题是:
        # - PDF、TXT、Markdown 这些原始格式彼此差异很大
        # - 后面的检索和 embedding 逻辑不想关心这些差异
        # - 所以必须先统一变成 Document
        #
        # 一个直观例子:
        # - 20 页 PDF 不会直接进入向量库
        # - 它会先被 parser 解析，再被 splitter 切成多个 chunk
        # - 最终变成多个 Document，例如 chunk1、chunk2、chunk3
        #
        # 从这一刻开始，系统不再主要关心“文件”，而是关心“文档块 docs”。
        # 从 storage 取回文件，按扩展名选择 processor，解析并切成 docs/chunks。
        docs = await process_files(
            storage=storage,
            skip_file_error=skip_file_error,
            **processor_kwargs,
        )

        # 第 5 阶段：把 docs 变成真正的检索知识库。
        #
        # 这是整个函数里“最接近知识库成型”的一步。
        # 真正的知识库不是原始文件，也不是 QuivrFile，而是:
        # - 文本 chunk
        # - 这些 chunk 的向量表示
        # - 存放这些向量的向量库
        #
        # 默认分支会做两件事:
        # 1. 用 embedder 给每个 doc 计算 embedding
        # 2. 用这些 embedding 构建默认向量库（当前默认是 FAISS）
        #
        # 如果用户手动传了 vector_db，这里不会重建，而是把 docs 追加进去。
        #
        # 所以你可以明确区分:
        # - upload_file(...)：只是文件登记
        # - process_files(...)：只是文件解析和切块
        # - build_default_vectordb(...) / aadd_documents(...)：这里才是知识库真正成型
        # 如果用户没有传入现成的向量库，就根据 docs + embedder 创建默认向量库。
        # 到这里，原始文件已经变成了可检索的知识库。
        if vector_db is None:
            vector_db = await build_default_vectordb(docs, embedder)
        else:
            await vector_db.aadd_documents(docs)

        logger.debug(f"added {len(docs)} chunks to vectordb")

        # 第 6 阶段：把这些底层能力封装成一个顶层 Brain。
        #
        # 这里的返回动作在架构上属于“门面封装层”。
        # 从用户视角看，前面的复杂步骤会被压缩成一个结果:
        # - 拿到一个 Brain
        #
        # 返回后的 Brain 已经具备两类核心能力:
        # - `asearch(...)`：只检索，适合看召回结果
        # - `ask(...)` / `ask_streaming(...)`：检索 + 生成答案
        #
        # 所以这个函数的最终产物，不只是“向量库”，而是“可直接问答的知识库对象”。
        return cls(
            id=brain_id,
            name=name,
            storage=storage,
            llm=llm,
            embedder=embedder,
            vector_db=vector_db,
        )

    @classmethod
    def from_files(
        cls,
        *,
        name: str,
        file_paths: list[str | Path],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
        skip_file_error: bool = False,
        processor_kwargs: dict[str, Any] | None = None,
    ) -> Self:
        # 这是 `afrom_files(...)` 的同步包装层。
        #
        # 在架构上它不增加新的 RAG 逻辑，只是把异步建库入口包装成同步接口，
        # 方便脚本、Notebook 或简单示例直接调用。
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            cls.afrom_files(
                name=name,
                file_paths=file_paths,
                vector_db=vector_db,
                storage=storage,
                llm=llm,
                embedder=embedder,
                skip_file_error=skip_file_error,
                processor_kwargs=processor_kwargs,
            )
        )

    @classmethod
    async def afrom_langchain_documents(
        cls,
        *,
        name: str,
        langchain_documents: list[Document],
        vector_db: VectorStore | None = None,
        storage: StorageBase = TransparentStorage(),
        llm: LLMEndpoint | None = None,
        embedder: Embeddings | None = None,
    ) -> Self:
        """
        Create a brain from a list of langchain documents.
        Args:
            name (str): The name of the brain.
            langchain_documents (list[Document]): The list of langchain documents to add to the brain.
            vector_db (VectorStore | None): The vector store used to store the processed files.
            storage (StorageBase): The storage used to store the files.
            llm (LLMEndpoint | None): The language model used to generate the answer.
            embedder (Embeddings | None): The embeddings used to create the index of the processed files.
        Returns:
            Brain: The brain created from the langchain documents.
        Example:
        ```python
        from langchain_core.documents import Document
        documents = [Document(page_content="Hello, world!")]
        brain = await Brain.afrom_langchain_documents(name="My Brain", langchain_documents=documents)
        brain.print_info()
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 现成的 LangChain Document 列表
        #
        # 输出:
        # - 一个直接基于 docs 建好的 Brain
        #
        # 在 RAG 系统里的角色:
        # - 这是“跳过文件处理层的建库入口”
        #
        # 适用场景:
        # - 数据已经在外部被清洗和切块
        # - 你不需要 Quivr 再去读文件、解析文件
        # - 你只想把现成 docs 直接放进向量库
        if llm is None:
            llm = default_llm()

        if embedder is None:
            embedder = default_embedder()

        brain_id = uuid4()

        # 这条入口跳过“文件登记层”和“文档标准化层”，
        # 直接从现成的 Document 列表进入“向量建库层”。
        if vector_db is None:
            vector_db = await build_default_vectordb(langchain_documents, embedder)
        else:
            await vector_db.aadd_documents(langchain_documents)

        return cls(
            id=brain_id,
            name=name,
            storage=storage,
            llm=llm,
            embedder=embedder,
            vector_db=vector_db,
        )

    async def asearch(
        self,
        query: str | Document,
        n_results: int = 5,
        filter: Callable | Dict[str, Any] | None = None,
        fetch_n_neighbors: int = 20,
    ) -> list[SearchResult]:
        """
        Search for relevant documents in the brain based on a query.
        Args:
            query (str | Document): The query to search for.
            n_results (int): The number of results to return.
            filter (Callable | Dict[str, Any] | None): The filter to apply to the search.
            fetch_n_neighbors (int): The number of neighbors to fetch.
        Returns:
            list[SearchResult]: The list of retrieved chunks.
        Example:
        ```python
        brain = Brain.from_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        results = await brain.asearch("Why everybody loves Quivr?")
        for result in results:
            print(result.chunk.page_content)
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - query: 查询文本
        # - n_results/filter/fetch_n_neighbors: 召回参数
        #
        # 输出:
        # - SearchResult 列表
        #
        # 在 RAG 系统里的角色:
        # - 这是“只检索、不生成”的入口
        #
        # 适合什么场景:
        # - 单独验证召回效果
        # - 调试向量库是否命中对的 chunk
        # - 在生成前先观察原始检索结果
        if not self.vector_db:
            raise ValueError("No vector db configured for this brain")

        # 这一句真正调用向量库执行相似度检索。
        # 状态变化:
        # - 输入: query 文本
        # - 输出: [(Document, score), ...]
        #
        # 它在 RAG 中属于“召回层”。
        result = await self.vector_db.asimilarity_search_with_score(
            query, k=n_results, filter=filter, fetch_k=fetch_n_neighbors
        )

        # 这里把底层返回值包装成 SearchResult，统一对外结构。
        return [SearchResult(chunk=d, distance=s) for d, s in result]

    def get_chat_history(self, chat_id: UUID):
        # 这是多会话访问入口。
        # 当前 Brain 内部可能维护多个 chat，这里允许按 chat_id 取回指定会话。
        return self._chats[chat_id]

    # TODO(@aminediro)
    def add_file(self) -> None:
        # 这是预留扩展点。
        # 未来如果要支持“Brain 建好后继续增量加文件”，
        # 这里需要同时更新 storage 和 vectorstore。
        # add it to storage
        # add it to vectorstore
        raise NotImplementedError

    async def ask_streaming(
        self,
        question: str,
        run_id: UUID,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
        **input_kwargs,
    ) -> AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]:
    # 为什么要设置 rag_pipeline:
        # 外部可以通过 rag_pipeline 显式指定本次问答要用哪种 RAG 工作流管道——
        # 常见的是 QuivrQARAG（经典链路版），和 QuivrQARAGLangGraph（LangGraph 场景增强版）。
        # 这样做的意义：
        # - 便于开发和测试时灵活切换工作流内核，支持 A/B、对比实验、不同推理编排
        # - 支持未来扩展更多 RAG Engine，只需实现接口即可插拔
        #
        # 两者区别与优缺点示例：
        # - QuivrQARAG: 传统“顺序检索-生成”管道，实现简单、调试方便、适合线性问答与基础文件知识库
        #   优点：弹性强，接口直观，上手快
        #   缺点：无法描述复杂多分支流程/多轮流转
        # - QuivrQARAGLangGraph: 基于 langgraph，可描述多分支、条件节点、复杂控制流，更适合流程自定义、异步多阶段、甚至流程内嵌插件
        #   优点：支持复杂编排、扩展性极强、适合企业自定义流程和插件嵌套
        #   缺点：学习曲线较高、设计成本略大
        """
        Ask a question to the brain and get a streamed generated answer.
        Args:
            question (str): The question to ask.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
        rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
        list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]: The streamed generated answer.
        Example:
        ```python
        brain = Brain.from_files(name="My Brain", file_paths=["file1.pdf", "file2.pdf"])
        async for chunk in brain.ask_streaming("What is the meaning of life?"):
            print(chunk.answer)
        ```
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - question: 用户当前问题
        # - retrieval_config: 本次问答的检索/工作流配置
        # - chat_history: 多轮对话上下文
        # - list_files: 文件列表元信息
        #
        # 输出:
        # - 一个异步流，每次 yield 一个回答片段 ParsedRAGChunkResponse
        #
        # 在 RAG 系统里的角色:
        # - 这是“问答入口 + 工作流接线层”
        # - 它自己不做检索细节，也不自己做 prompt 编排
        # - 它负责把 question、history、config 交给真正的 RAG 引擎去跑
        #
        # 你可以把它看成 5 个阶段:
        # 1. 确定本次请求用哪个 LLM
        # 2. 创建 RAG 工作流引擎
        # 3. 准备 chat history / files / tracing metadata
        # 4. 流式消费工作流输出
        # 5. 把本轮问答写回 chat history
        llm = self.llm

        # 第 1 阶段：确定本次请求实际使用的 LLM。
        #
        # 默认情况下直接沿用 Brain 持有的 self.llm。
        # 但如果调用方在 retrieval_config 里指定了另一个 llm_config，
        # 那本次请求会临时覆盖默认模型。
        #
        # 这一步在 RAG 中属于“生成层入口配置”。
        # If you passed a different llm model we'll override the brain  one
        if retrieval_config:
            if retrieval_config.llm_config != self.llm.get_config():
                llm = LLMEndpoint.from_config(config=retrieval_config.llm_config)
        else:
            # 如果调用方没有传 retrieval_config，就自动生成一个默认配置，
            # 并把当前 Brain 的 llm 配置写进去。
            retrieval_config = RetrievalConfig(llm_config=self.llm.get_config())

        # 第 2 阶段：创建本次问答使用的 RAG 引擎。
        #
        # 真正负责执行“历史过滤、问题改写、检索、工具路由、生成答案”的，
        # 不是 Brain 本身，而是 QuivrQARAGLangGraph。
        #
        # 所以这里的角色很像“接线员”：
        # Brain 负责把依赖和输入拼好，真正干活的是下游工作流引擎。
        # 注意：这里直接指定使用 QuivrQARAGLangGraph 作为 RAG 工作流引擎。
        # 虽然 quivr_core/rag/pipeline.py 里定义了 QuivrQARAG（基础经典 RAG 工作流）和 QuivrQARAGLangGraph（支持多 Agent/多工具的 LangGraph 扩展版本）两种选择，
        # 但当前 Brain 默认只启动更强大的 QuivrQARAGLangGraph（表征“多智能体+工具流编排”），属于“下一代 RAG Pipline”。
        # 如果后续需要兼容经典纯 RAG 工作流或做老版本 fallback，可以加条件动态选择。
        rag_instance = QuivrQARAGLangGraph(
            retrieval_config=retrieval_config, llm=llm, vector_store=self.vector_db
        )

        # 第 3 阶段：准备上下文与观测信息。
        #
        # chat_history:
        # - 如果调用方没传，就用当前 Brain 默认对话
        # - 这保证了 Brain 天然支持多轮问答
        #
        # list_files:
        # - 如果调用方没传，就给空列表
        # - 这些通常是文件展示层或来源展示层会用到的元信息
        chat_history = self.default_chat if chat_history is None else chat_history
        list_files = [] if list_files is None else list_files

        # full_answer 用来把流式 chunk 拼成完整答案。
        # 它的作用不是驱动 RAG，而是为后续写回 chat history 做准备。
        full_answer = ""

        # 这些 metadata 会随着工作流进入 Langfuse。
        # 它们在 RAG 中承担“可观测性层”的角色：
        # 方便你回头看这一轮问答的 trace、session、user。
        metadata = LangchainMetadata(
            langfuse_trace_id=str(run_id),
            langfuse_user_id=str(self.workspace_id),
            langfuse_session_id=str(self.chat_id),
        )

        # 第 4 阶段：真正启动 RAG 工作流，并流式消费输出。
        #
        # 这里调用的是下游引擎的 `answer_astream(...)`。
        # 它内部才会继续执行：
        # - filter_history
        # - rewrite
        # - retrieve / dynamic_retrieve
        # - tool_routing / run_tool
        # - generate_rag
        #
        # 所以这行代码是 Brain 和底层 RAG 工作流之间的真正分界点。
        async for response in rag_instance.answer_astream(
            run_id=run_id,
            question=question,
            system_prompt=system_prompt or None,
            history=chat_history,
            list_files=list_files,
            metadata=metadata,
            **input_kwargs,
        ):
            # 每次循环拿到一个 chunk 响应。
            #
            # 对外行为:
            # - 不是等完整答案生成后一次性返回
            # - 而是边生成边 yield 给上层调用方
            #
            # 在产品体验里，这就是流式输出能力的来源。
            if not response.last_chunk:
                yield response
            # 不管是不是最后一个 chunk，都把文本内容累积起来。
            # 这样结束后才能得到整轮完整答案。
            full_answer += response.answer

        # 第 5 阶段：把这轮问答写回 chat history。
        #
        # 这是多轮对话成立的关键一步。
        # 如果不把本轮问题和答案写回去，下一轮就读不到这一轮上下文。
        #
        # 所以 chat history 在 RAG 中承担的是“会话记忆层”的角色。
        chat_history.append(HumanMessage(content=question))
        chat_history.append(AIMessage(content=full_answer))
        # 最后把收尾的 response 再 yield 一次，通常包含最终 metadata。
        yield response

    async def aask(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
        **input_kwargs,
    ) -> ParsedRAGResponse:
        """
        Synchronous version that asks a question to the brain and gets a generated answer.
        Args:
            question (str): The question to ask.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
            rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
            list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            ParsedRAGResponse: The generated answer.
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 和 ask_streaming(...) 相同
        #
        # 输出:
        # - 一个完整的 ParsedRAGResponse
        #
        # 在 RAG 系统里的角色:
        # - 这是“流式结果聚合层”
        # - 它不改变底层工作流，只把多个 chunk 聚合成一个完整答案对象
        #
        # `aask` 是“拿完整答案”的异步接口，本质上是对 ask_streaming 的聚合包装。
        # question_language = detect_language(question) -- Commented until we use it
        full_answer = ""
        metadata = None

        # 这里仍然复用 ask_streaming(...)，
        # 只是在上层把每个 chunk 收集起来，最后组装成完整响应。
        async for response in self.ask_streaming(
            run_id=run_id,
            question=question,
            system_prompt=system_prompt,
            retrieval_config=retrieval_config,
            rag_pipeline=rag_pipeline,
            list_files=list_files,
            chat_history=chat_history,
            **input_kwargs,
        ):
            full_answer += response.answer
            if response.metadata:
                metadata = response.metadata

        # 最终把聚合后的文本和 metadata 封装成统一响应对象。
        return ParsedRAGResponse(answer=full_answer, metadata=metadata)

    def ask(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None = None,
        retrieval_config: RetrievalConfig | None = None,
        rag_pipeline: Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None = None,
        list_files: list[QuivrKnowledge] | None = None,
        chat_history: ChatHistory | None = None,
    ) -> ParsedRAGResponse:
        """
        Fully synchronous version that asks a question to the brain and gets a generated answer.
        Args:
            question (str): The question to ask.
            system_prompt (str | None): The system prompt to use.
            retrieval_config (RetrievalConfig | None): The retrieval configuration (see RetrievalConfig docs).
            rag_pipeline (Type[Union[QuivrQARAG, QuivrQARAGLangGraph]] | None): The RAG pipeline to use.
            list_files (list[QuivrKnowledge] | None): The list of files to include in the RAG pipeline.
            chat_history (ChatHistory | None): The chat history to use.
        Returns:
            ParsedRAGResponse: The generated answer.
        """
        # 这是最外层的同步问答入口。
        #
        # 在架构上它属于“API 兼容层”：
        # - 真正工作的是 ask_streaming(...) 和 aask(...)
        # - 这个函数只负责给不想处理 async 的调用方提供同步接口
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.aask(
                run_id=run_id,
                question=question,
                system_prompt=system_prompt,
                retrieval_config=retrieval_config,
                rag_pipeline=rag_pipeline,
                list_files=list_files,
                chat_history=chat_history,
            )
        )
