import os
import shutil
from pathlib import Path
from typing import Self, Set
from uuid import UUID

from quivr_core.brain.serialization import LocalStorageConfig, TransparentStorageConfig
from quivr_core.files.file import QuivrFile
from quivr_core.storage.storage_base import StorageBase


class LocalStorage(StorageBase):
    """
    LocalStorage is a concrete implementation of the `StorageBase` class that
    stores files locally on disk. This class manages file uploads, tracks file
    hashes, and allows retrieval of stored files from a specified directory.

    Attributes:
        name (str): The name of the storage type, set to "local_storage".
        files (list[QuivrFile]): A list of files stored in this local storage.
        hashes (Set[str]): A set of SHA-1 hashes of the uploaded files.
        copy_flag (bool): If `True`, files are copied to the storage directory.
                          If `False`, symbolic links are used instead.
        dir_path (Path): The directory path where files are stored.

    Args:
        dir_path (Path | None): Optional directory path for storing files.
                                Defaults to the environment variable `QUIVR_LOCAL_STORAGE`
                                or `~/.cache/quivr/files`.
        copy_flag (bool): Whether to copy the file or create a symlink.
                          Defaults to `True`.
    """

    name: str = "local_storage"

    def __init__(self, dir_path: Path | None = None, copy_flag: bool = True):
        self.files: list[QuivrFile] = []
        self.hashes: Set[str] = set()
        # copy_flag 用于控制上传文件时，是选择将文件内容复制一份到指定存储目录（True），
        # 还是只在存储目录创建指向原路径的符号链接（False）。
        # 实际生产中，通常推荐使用 True，也就是复制文件：
        # - 优点：文件物理独立保存，避免用户删除/移动原文件导致丢失，安全性和可控性更高
        # - 缺点：磁盘多占一份空间，IO 会略增加
        # 仅对安全、隔离要求不高但追求速度或空间极致优化的场景，才考虑用 False（如本地开发临时测试、磁盘空间极度有限时）。
        self.copy_flag = copy_flag

        if dir_path is None:
            self.dir_path = Path(
                os.getenv("QUIVR_LOCAL_STORAGE", "~/.cache/quivr/files")
            )
        else:
            self.dir_path = dir_path
        os.makedirs(self.dir_path, exist_ok=True)

    def _load_files(self) -> None:
        # TODO(@aminediro): load existing files
        pass

    def nb_files(self) -> int:
        return len(self.files)

    def info(self):
        return {"directory_path": self.dir_path, **super().info()}

    async def upload_file(self, file: QuivrFile, exists_ok: bool = False) -> None:
        """
        Uploads a file to the local storage. Copies or creates a symlink based
        on the `copy_flag` attribute. Checks for duplicate file uploads using
        the file's SHA-1 hash.

        Args:
            file (QuivrFile): The file object to upload.
            exists_ok (bool): If `True`, allows overwriting an existing file.
                              Defaults to `False`.

        Raises:
            FileExistsError: If a file with the same SHA-1 hash already exists
                             and `exists_ok` is set to `False`.
        """
        # LocalStorage 会把文件真正落到本地目录，并把 QuivrFile 放进内存列表 self.files。
        # 后续 process_files 调用 storage.get_files() 时，拿到的就是这里缓存过的文件对象。
        dst_path = os.path.join(
            self.dir_path, str(file.brain_id), f"{file.id}{file.file_extension}"
        )

        # 这里没有用向量数据库存储文件 hash，而是用本地内存 self.hashes 做判重，原因如下：
        # 1. Storage 层只负责“原始文件的本地登记与去重”，它管理的是文件元数据（hash/路径/归属等），不是知识块向量，不需复杂持久化。
        # 2. 本地集合集合法查重小文件高效、实现简单，只要单机生命周期内数据一致即可，满足大部分中小型用例（如数万量级）。
        # 3. 确实，如你所说，如果“单机内存判重”遇到百万级别甚至千万级别文档时，hash 索引会变大，查找和存取延迟也会上升——此时建议：
        #    - 如果需要横向扩展/冷启动恢复，可以将 hash 持久化存储（如 SQLite/RocksDB/Redis）。
        #    - 若量大分布式共享，可选像向量库或专门的 KV/Set 存储分担元数据唯一性检查。
        #    - 小而快的内存索引依然适合 ingestion 的“热路径”，持久化和分布式判重属于对海量数据“降级设计”。
        #    - 真正的知识库内容是落在向量数据库，原始文件判重仅在 ingestion 入口做一层轻量保护，不影响下游问答与检索逻辑。
        if file.file_sha1 in self.hashes and not exists_ok:
            raise FileExistsError(f"file {file.original_filename} already uploaded")

        if self.copy_flag:
            # 复制文件内容到本地存储指定目录
            # file.path：用户上传文件的原始路径，通常是临时文件或外部输入
            # dst_path：平台为每个文件生成的归档路径，形如 {self.dir_path}/{brain_id}/{file_id}{file_extension}
            shutil.copy2(file.path, dst_path)
        else:
            os.symlink(file.path, dst_path)

        file.path = Path(dst_path)
        self.files.append(file)
        self.hashes.add(file.file_sha1)

    async def get_files(self) -> list[QuivrFile]:
        """
        Retrieves the list of files stored in the local storage.

        Returns:
            list[QuivrFile]: A list of stored file objects.
        """
        # 这里不会重新扫描磁盘，而是直接返回 upload_file 时维护的内存列表。
        return self.files

    async def remove_file(self, file_id: UUID) -> None:
        """
        Removes a file from the local storage. This method is currently not
        implemented.

        Args:
            file_id (UUID): The unique identifier of the file to remove.

        Raises:
            NotImplementedError: Always raises this error as the method is not yet implemented.
        """
        
        raise NotImplementedError

    # storage_path 在项目里表示本地存储目录的“根路径”——也就是所有文件都归档在哪个主目录下。
    # 例如，storage_path 可能是 "data/brains/xxx"，本地存储会在这个目录下按 brain_id、file_id 分类保存所有入库文件。
    # LocalStorage 的 load 函数会用 config.storage_path 初始化本地存储对象，
    # 并把序列化的文件清单反序列化，恢复成内存中的 QuivrFile 列表，保证同一次脑袋启动时能拿到所有已归档的文件元数据。
    @classmethod
    def load(cls, config: LocalStorageConfig) -> Self:
        """
        Loads the local storage from a configuration object. This method
        initializes the storage directory and populates it with deserialized
        files from the configuration.

        Args:
            config (LocalStorageConfig): Configuration object containing the
                                         storage path and serialized file data.

        Returns:
            LocalStorage: An instance of `LocalStorage` with files loaded
                          from the configuration.
        """
        # 这行代码的作用是：用配置对象 config 里的存储路径 storage_path 创建一个本地存储实例 tstorage。
        # 例如，如果 config.storage_path 是 "data/brains/xxx"，函数会执行 tstorage = LocalStorage(dir_path="data/brains/xxx")。
        # 最终结果就是 tstorage 变成管理指定本地文件夹的 LocalStorage 对象，后面可以把文件登记进这个目录。
        tstorage = cls(dir_path=config.storage_path)
        tstorage.files = [QuivrFile.deserialize(f) for f in config.files.values()]
        return tstorage


class TransparentStorage(StorageBase):
    """Transparent Storage."""

    name: str = "transparent_storage"

    def __init__(self):
        self.id_files = {}

    async def upload_file(self, file: QuivrFile, exists_ok: bool = False) -> None:
        # TransparentStorage 不复制文件，只是在内存里登记 file.id -> QuivrFile。
        # 所以 get_files() 拿到的是“之前上传登记过的文件对象”。
        self.id_files[file.id] = file

    def nb_files(self) -> int:
        return len(self.id_files)

    async def remove_file(self, file_id: UUID) -> None:
        raise NotImplementedError

    async def get_files(self) -> list[QuivrFile]:
        # 这里返回 upload_file 写入的内存映射值。
        return list(self.id_files.values())

    @classmethod
    def load(cls, config: TransparentStorageConfig) -> Self:
        tstorage = cls()
        tstorage.id_files = {
            i: QuivrFile.deserialize(f) for i, f in config.files.items()
        }
        return tstorage
