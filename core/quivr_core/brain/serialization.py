from pathlib import Path
from typing import Any, Dict, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from quivr_core.rag.entities.config import LLMEndpointConfig
from quivr_core.rag.entities.models import ChatMessage
from quivr_core.files.file import QuivrFileSerialized


class EmbedderConfig(BaseModel):
    embedder_type: Literal["openai_embedding"] = "openai_embedding"
    # TODO: type this correctly
    config: Dict[str, Any]


class PGVectorConfig(BaseModel):
    vectordb_type: Literal["pgvector"] = "pgvector"
    pg_url: str
    pg_user: str
    pg_psswd: SecretStr
    table_name: str
    vector_dim: int


class FAISSConfig(BaseModel):
    vectordb_type: Literal["faiss"] = "faiss"
    vectordb_folder_path: str


class LocalStorageConfig(BaseModel):
    storage_type: Literal["local_storage"] = "local_storage"
    storage_path: Path
    files: dict[UUID, QuivrFileSerialized]


class TransparentStorageConfig(BaseModel):
    storage_type: Literal["transparent_storage"] = "transparent_storage"
    files: dict[UUID, QuivrFileSerialized]


class BrainSerialized(BaseModel):
    id: UUID
    name: str
    chat_history: list[ChatMessage]
    # 这里 `vectordb_config` 字段是“向量数据库配置”的联合类型（支持多种向量库配置结构）：
    # - Union[FAISSConfig, PGVectorConfig]    # 允许是 FAISS 或 PGVector 两种配置结构体之一
    # - Field(..., discriminator="vectordb_type") 指定“区分联合类型用哪个字段”，即根据其中的 "vectordb_type" 字段自动判别
    # 用法举例：
    # {
    #   "vectordb_type": "faiss",
    #   ...faiss相关配置项...
    # }
    # 或
    # {
    #   "vectordb_type": "pgvector",
    #   ...pgvector相关配置项...
    # }
    
    # Pydantic 会自动根据 "vectordb_type" 的值决定用 FAISSConfig 还是 PGVectorConfig 解析具体内容。
    # vectordb_config 字段支持 FAISS 和 PGVector 两种向量数据库的序列化配置结构体。
    # 它们的优缺点和典型适用场景如下：
    # - FAISS：本地嵌入式向量库，适合单机、快速原型、资源受限、无需高可用或分布式的应用。
    #   优点：无需外部依赖、部署简单、性能好，尤其适合小型项目或离线场景。
    #   缺点：无法多机/云端扩展，对大规模数据和团队协作不友好，不适合持久化（磁盘存储较原始）。
    # - PGVector：基于 PostgreSQL 的向量扩展，适合生产级、多用户、多节点部署场景。
    #   优点：支持持久化、权限控制、SQL 查询整合、弹性扩展，可与标准数据库运维体系结合。
    #   缺点：部署和配置较复杂、依赖外部数据库实例、单查询性能通常不如纯内存型FAISS。
    vectordb_config: Union[FAISSConfig, PGVectorConfig] = Field(
        ..., discriminator="vectordb_type"
    )
    # storage_config 字段用于序列化和反序列化“存储后端”的配置，它支持多种存储结构体（二选一），可适应不同存储模式：
    # - Union[TransparentStorageConfig, LocalStorageConfig]：表示可以是透明（内存临时态）存储，也可以是本地文件系统持久化存储。
    # - Field(..., discriminator="storage_type")：指定使用哪个字段（storage_type）来区分到底是哪一种配置，
    #   例如：
    #     {"storage_type": "local_storage", ...local配置内容...}
    #     {"storage_type": "transparent_storage", ...transparent配置内容...}
    #   Pydantic 反序列化时会自动根据 storage_type 字段选择 LocalStorageConfig 或 TransparentStorageConfig 结构体解析内容。
    # 这样可以让前端/后端统一处理两种存储配置，增强了可扩展性和类型安全。
    
    # storage_config 字段支持两种“存储后端配置类型”联合：TransparentStorageConfig 与 LocalStorageConfig。
    # - TransparentStorageConfig（透明存储）：
    #   - 区别：文件仅保存在内存，不落盘。
    #   - 优点：读写极快、不需要任何磁盘、无需处理权限、适合小量测试或临时会话。
    #   - 缺点：占用内存，随进程消亡，不能持久化，无法支撑大文件和多文件批量上传——内存瓶颈很快出现。
    #   - 使用场景：小文件 Demo、对话回话式体验、交互 Notebook、临时测试。
    # - LocalStorageConfig（本地存储）：
    #   - 区别：将所有文件直接保存到本地磁盘的某个目录。
    #   - 优点：数据可持久化，重启不丢失，下次可直接复用历史数据。
    #   - 缺点：遇到大量文件批量上传时，会有大量磁盘 IO 瞬时写入，可能拖慢主流程，且受限于本地硬盘空间。缺少异步/后台上传机制会影响体验。
    #   - 使用场景：本地小型知识库、长期数据保存、不用频繁批量导入超大文件时。
    #
    # ⭕️ 对于“有大量批量上传、文件很大”的场景，这两种方式都不是最佳方案：
    # - TransparentStorageConfig 会很快耗尽内存，完全不推荐用于批量/大文件。
    # - LocalStorageConfig 每上传一个文件都会即时写入本地磁盘，无法异步缓冲，会造成大量 IO 峰值并对磁盘有压力，也不适合“瞬间导入 TB 级文件”或云分布式扩展。
    #
    # 🚀 更适合大量/大文件上传的方案建议：
    # - 引入异步后台上传队列、断点续传，或用云对象存储（如 S3、OSS）存储后端。
    # - 生产环境可扩展为 S3StorageConfig 或专用分布式存储，并配合队列避免阻塞主线程。
    # 
    storage_config: Union[TransparentStorageConfig, LocalStorageConfig] = Field(
        ..., discriminator="storage_type"
    )

    llm_config: LLMEndpointConfig
    embedding_config: EmbedderConfig
