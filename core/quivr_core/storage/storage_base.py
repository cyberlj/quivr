from abc import ABC, abstractmethod
from uuid import UUID

from quivr_core.brain.info import StorageInfo
from quivr_core.storage.local_storage import QuivrFile


class StorageBase(ABC):
    """
    Abstract base class for storage systems. All subclasses are required to define certain attributes and implement specific methods for managing files

    Attributes:
        name (str): Name of the storage type.
    """

    name: str

    # __init_subclass__ 是 Python 提供的元类钩子函数之一，不是普通类，而是基础 object 类型的特殊方法。
    # 它会在“子类被定义”时自动执行，常用于框架或基类对所有子类做统一注册、强制属性检查等操作。
    # 例如在设计插件系统、抽象基类、自动注册等场景，经常用到 __init_subclass__。
    # 除了 __init_subclass__ 之外，Python 还有很多类似的“钩子函数”（特殊生命周期方法），常见的有：
    # - __new__(cls, ...)：控制对象的实际创建，优先于 __init__
    # - __init__(self, ...)：实例初始化
    # - __del__(self)：对象销毁时调用
    # - __call__(self, ...)：实例变可调用
    # - __getattr__/__setattr__：属性访问/赋值拦截
    # - __getattribute__：所有属性访问全局拦截
    # - __enter__/__exit__：上下文管理器协议
    # - __str__/__repr__：转字符串协议
    # - __set_name__(self, owner, name)：描述符被赋予名字时触发
    # - __slots__、__mro_entries__ 等。
    # 这些特殊方法本质是 Python 提供的标准“钩子入口”，用来增强类的元编程与生命周期管理能力，属于 Python 面向对象体系的高级特性。
    def __init_subclass__(cls, **kwargs):
        for required in ("name",):
            if not getattr(cls, required):
                raise TypeError(
                    f"Can't instantiate abstract class {cls.__name__} without {required} attribute defined"
                )
        return super().__init_subclass__(**kwargs)

    # __repr__ 是 Python 的“转字符串协议”钩子方法。
    # 当你在终端、日志或调试器里直接打印一个对象（如 print(obj)，或在 REPL 交互模式下敲回车），
    # Python 会调用这个对象的 __repr__ 方法，返回它的“官方字符串表示”。
    # 推荐 __repr__ 返回的信息足够详细，可以唯一标识、重建对象（但不是强制要求），
    # 用于开发和调试，便于定位对象实例的关键状态。
    def __repr__(self) -> str:
        return f"storage_type: {self.name}"

    @abstractmethod
    def nb_files(self) -> int:
        """
        Abstract method to get the number of files in the storage.

        Returns:
            int: The number of files in the storage.

        Raises:
            Exception: If the method is not implemented.
        """
        raise Exception("Unimplemented nb_files method")

    @abstractmethod
    async def get_files(self) -> list[QuivrFile]:
        """
        Abstract asynchronous method to get the files `QuivrFile` in the storage.

        Returns:
            list[QuivrFile]: A list of QuivrFile objects representing the files in the storage.

        Raises:
            Exception: If the method is not implemented.
        """
        raise Exception("Unimplemented get_files method")

    @abstractmethod
    async def upload_file(self, file: QuivrFile, exists_ok: bool = False) -> None:
        """
        Abstract asynchronous method to upload a file to the storage.

        Args:
            file (QuivrFile): The file to upload.
            exists_ok (bool): If True, allows overwriting the file if it already exists. Default is False.

        Raises:
            Exception: If the method is not implemented.
        """
        raise Exception("Unimplemented  upload_file method")

    @abstractmethod
    async def remove_file(self, file_id: UUID) -> None:
        """
        Abstract asynchronous method to remove a file from the storage.

        Args:
            file_id (UUID): The unique identifier of the file to be removed.

        Raises:
            Exception: If the method is not implemented.
        """
        raise Exception("Unimplemented remove_file method")

    def info(self) -> StorageInfo:
        """
        Returns information about the storage, including the storage type and the number of files.

        Returns:
            StorageInfo: An object containing details about the storage.
        """
        return StorageInfo(
            storage_type=self.name,
            n_files=self.nb_files(),
        )
