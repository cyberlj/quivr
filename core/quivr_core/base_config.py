from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from typing import Self


class QuivrBaseConfig(BaseModel):
    """
    Base configuration class for Quivr.

    This class extends Pydantic's BaseModel and provides a foundation for
    configuration management in quivr-core.

    Attributes:
        # pydantic model 是指基于 Pydantic 库定义的数据结构模型，支持类型注解、字段校验和自动序列化。
        # 在 agent 系统和 RAG（检索增强生成）系统中，pydantic model 常用于配置（如 LLM 参数、数据源设置）、消息/事件结构体、检索项标准化、向量入库的元信息、插件/工具协议描述等环节。
        # 例如：在 agent 架构的“技能注册、提示组装、交互参数拆解”，RAG 架构的“切块元数据、文档静态配置、检索器参数绑定”都广泛应用 pydantic model 进行数据标准化与自动校验。
        model_config (ConfigDict): Configuration for the Pydantic model.
            It's set to forbid extra attributes, ensuring strict adherence
            to the defined schema.

    Class Methods:
        from_yaml: Create an instance of the class from a YAML file.
    """

    # ConfigDict 是 Pydantic v2 引入的配置类，用于指定 Pydantic 数据模型的行为选项（如是否允许多余字段、序列化风格、校验细节等）。
    # 这里 ConfigDict(extra="forbid") 表示禁止模型接收未定义的附加属性——即仅允许预先声明的字段，防止配置书写错误或无关参数混入。
    # model_config 是 Pydantic 支持的特殊 class 属性，接收一个 ConfigDict 实例。设置后，当前模型实例化时会使用这些配置覆盖默认行为，不是对 ConfigDict 实例的普通赋值，而是实现模型全局行为的声明方式。
    model_config = ConfigDict(extra="forbid")


  # from_yaml 是“类方法”（class method），其第一个参数必须是cls（代表当前类），类似于实例方法的第一个参数是self。这里用@classmethod装饰，意味着调用时不用依赖某个实例，而是依赖类本身。
    # 什么时候要用cls参数？——当你需要在方法里创建当前类的实例，或操作类级别的数据、做“工厂模式”初始化时。如果方法最终要返回cls(...)而不是self，就需要传cls。
    # 这样写的好处是：无论你继承（如MyConfig(QuivrBaseConfig)），from_yaml总能自动用正确的子类去构建对象，实现多态灵活扩展。
    @classmethod
    def from_yaml(cls, file_path: str | Path) -> Self:
        """
        Create an instance of the class from a YAML file.

        Args:
            file_path (str | Path): The path to the YAML file.

        Returns:
            QuivrBaseConfig: An instance of the class initialized with the data from the YAML file.
        """
        # Load the YAML file
        # with语句是Python里的上下文管理器语法，常用于像文件、锁、数据库连接等这类需要“用完即释放资源”的场景。它能保证无论操作中间是否报错，最后一定自动帮你关闭和清理资源。
        # Go语言没有with这种语法糖，但有“defer”关键字可以达到类似效果。Go里一般写成：
        #   f, err := os.Open("file.txt")
        #   if err != nil { ... }
        #   defer f.Close()
        # 这样f.Close()会在函数返回前自动执行，实现“用完即关”。
        with open(file_path, "r") as stream:
            config_data = yaml.safe_load(stream)

        # Instantiate the class using the YAML data
        # 这里是直接根据当前类cls的构造方法，把YAML里读取到的参数（config_data字典）解包传入，从而生成一个cls类型的实例。
        # 具体是哪一种类取决于你调用from_yaml时用的那个类本身，比如你写MyConfig.from_yaml('a.yaml')就是MyConfig；
        # 如果你传的是RetrievalConfig.from_yaml(...)，那生成的就是RetrievalConfig实例。
        # 下面是原样返回，用法示例可参考：

        # 示例：假设你有这样一个配置子类
        # class MyConfig(QuivrBaseConfig):
        #     foo: str
        #     bar: int
        # config = MyConfig.from_yaml('config.yaml')

        # 通用写法如下：
        return cls(**config_data)
