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
            qvr_version = version("quivr-core")
        except PackageNotFoundError:
            qvr_version = "dev"

        for idx, doc in enumerate(docs.chunks, start=1):
            if "original_file_name" in doc.metadata:
                doc.page_content = f"Filename: {doc.metadata['original_file_name']} Content: {doc.page_content}"
            doc.page_content = doc.page_content.replace("\u0000", "")
            doc.page_content = doc.page_content.encode("utf-8", "replace").decode(
                "utf-8"
            )
            doc.metadata = {
                "chunk_index": idx,
                "quivr_core_version": qvr_version,
                "language": detect_language(
                    text=doc.page_content.replace("\\n", " ").replace("\n", " "),
                    low_memory=True,
                ).value,
                **file.metadata,
                **doc.metadata,
                **self.processor_metadata,
            }
        return docs

    @abstractmethod
    async def process_file_inner(self, file: QuivrFile) -> ProcessedDocument[R]:
        raise NotImplementedError
