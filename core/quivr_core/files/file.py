import hashlib
import mimetypes
import os
import warnings
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, Self
from uuid import UUID, uuid4

import aiofiles
from openai import BaseModel


class QuivrFileSerialized(BaseModel):
    id: UUID
    brain_id: UUID
    path: Path
    original_filename: str
    file_size: int | None
    file_extension: str
    file_sha1: str
    additional_metadata: dict[str, Any]


class FileExtension(str, Enum):
    txt = ".txt"
    pdf = ".pdf"
    csv = ".csv"
    doc = ".doc"
    docx = ".docx"
    pptx = ".pptx"
    xls = ".xls"
    xlsx = ".xlsx"
    md = ".md"
    mdx = ".mdx"
    markdown = ".markdown"
    bib = ".bib"
    epub = ".epub"
    html = ".html"
    odt = ".odt"
    py = ".py"
    ipynb = ".ipynb"
    m4a = ".m4a"
    mp3 = ".mp3"
    webm = ".webm"
    mp4 = ".mp4"
    mpga = ".mpga"
    wav = ".wav"
    mpeg = ".mpeg"


def get_file_extension(file_path: Path) -> FileExtension | str:
    try:
        mime_type, _ = mimetypes.guess_type(file_path.name)
        if mime_type:
            mime_ext = mimetypes.guess_extension(mime_type)
            if mime_ext:
                return FileExtension(mime_ext)
        return FileExtension(file_path.suffix)
    except ValueError:
        warnings.warn(
            f"File {file_path.name} extension isn't recognized. Make sure you have registered a parser for {file_path.suffix}",
            stacklevel=2,
        )
        return file_path.suffix


async def load_qfile(brain_id: UUID, path: str | Path):
    if not isinstance(path, Path):
        path = Path(path)

    if not path.exists():
        raise FileExistsError(f"file {path} doesn't exist")

    # 这里还没有“上传”动作，只是把用户给的本地路径包装成 QuivrFile。
    # QuivrFile 会记录原始路径、文件大小、扩展名、sha1 和所属 brain_id，
    # 方便后面的 storage 和 processor 统一处理。
    file_size = os.stat(path).st_size

    async with aiofiles.open(path, mode="rb") as f:
        file_sha1 = hashlib.sha1(await f.read()).hexdigest()

    try:
        # NOTE: when loading from existing storage, file name will be uuid
        id = UUID(path.name)
    except ValueError:
        id = uuid4()

    # 这里没有赋值 metadata，是因为 load_qfile 这个入口本身没有传递“额外业务元数据”参数（比如上传时的自定义标签、描述、外部引用等），它只登记了和文件内容/路径/归属相关的核心属性。
    # QuivrFile 的 metadata 字段主要预留给后续管道里 processor/storage 层传递附加信息（如解析出来的作者、文本摘要、外部关联），而 load_qfile 只负责原始文件的基础属性采集。
    # 如果业务上需要在登记时就带 metadata，可以给 load_qfile 增加一个 metadata 参数，然后在这里补 metadata=metadata。
    return QuivrFile(
        id=id,
        brain_id=brain_id,
        path=path,
        original_filename=path.name,
        file_extension=get_file_extension(path),
        file_size=file_size,
        file_sha1=file_sha1,  # 这里只负责收集文件内容的SHA1指纹，无论内容是否和已有文件重复，系统每次“加载”/登记时都会先生成新的 QuivrFile（分配新的UUID），并记录sha1用于后续判重。
                              # 目前没有在这里直接用 file_sha1 检查重复、跳过生成 QuivrFile，因为：
                              # 1. QuivrFile 记录的是“本次业务层文件引用”或“上传记录”，需要每次都生成并持久化（比如同一内容被不同用户/会话上传）。
                              # 2. file_sha1 主要用于存储层面判断“底层内容是否已存在”（比如 dedup 或软链接），具体判重逻辑应该在存储管理/业务去重阶段，而不是 load_qfile 这个入口函数里实现。
                              # 3. “上传”动作可能还带有不同业务元数据、归属 brain_id、权限绑定，即使内容重复，也要新建引用，以支持多实例独立管理。
                              # 通常会在 storage 层/processor 层增加基于 file_sha1 的内容去重加速，这一步不能直接省略 QuivrFile 生成，否则业务链路无法串联、权限难区分。
    )


class QuivrFile:
    __slots__ = [
        "id",
        "brain_id",
        "path",
        "original_filename",
        "file_size",
        "file_extension",
        "file_sha1",
        "additional_metadata",
    ]

    def __init__(
        self,
        id: UUID,
        original_filename: str,
        path: Path,
        file_sha1: str,
        file_extension: FileExtension | str,
        brain_id: UUID | None = None,
        file_size: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.brain_id = brain_id
        self.path = path
        self.original_filename = original_filename
        self.file_size = file_size
        self.file_extension = file_extension
        self.file_sha1 = file_sha1
        self.additional_metadata = metadata if metadata else {}

    def __repr__(self) -> str:
        return f"QuivrFile-{self.id} original_filename:{self.original_filename}"

    @asynccontextmanager
    async def open(self) -> AsyncGenerator[AsyncIterable[bytes], None]:
        # TODO(@aminediro) : match on path type
        f = await aiofiles.open(self.path, mode="rb")
        try:
            yield f
        finally:
            await f.close()

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "qfile_id": self.id,
            "qfile_path": self.path,
            "original_file_name": self.original_filename,
            "file_sha1": self.file_sha1,
            "file_size": self.file_size,
            **self.additional_metadata,
        }

    def serialize(self) -> QuivrFileSerialized:
        return QuivrFileSerialized(
            id=self.id,
            brain_id=self.brain_id,
            path=self.path.absolute(),
            original_filename=self.original_filename,
            file_size=self.file_size,
            file_extension=self.file_extension,
            file_sha1=self.file_sha1,
            additional_metadata=self.additional_metadata,
        )

    @classmethod
    def deserialize(cls, serialized: QuivrFileSerialized) -> Self:
        return cls(
            id=serialized.id,
            brain_id=serialized.brain_id,
            path=serialized.path,
            original_filename=serialized.original_filename,
            file_size=serialized.file_size,
            file_extension=serialized.file_extension,
            file_sha1=serialized.file_sha1,
            metadata=serialized.additional_metadata,
        )
