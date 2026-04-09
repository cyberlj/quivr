import logging
import os
import re
from enum import Enum
from typing import Any, Dict, Hashable, List, Optional, Type, Union
from uuid import UUID

from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.tools import BaseTool
from langgraph.graph import END, START
from pydantic import BaseModel
from rapidfuzz import fuzz, process

from quivr_core.base_config import QuivrBaseConfig
from quivr_core.config import MegaparseConfig
from quivr_core.llm_tools.llm_tools import TOOLS_CATEGORIES, TOOLS_LISTS, LLMToolFactory
from quivr_core.processor.splitter import SplitterConfig

logger = logging.getLogger("quivr_core")
MIN_CONTEXT_TOKENS = 4096
MIN_OUTPUT_TOKENS = 4096


def normalize_to_env_variable_name(name: str) -> str:
    # Replace any character that is not a letter, digit, or underscore with an underscore
    env_variable_name = re.sub(r"[^A-Za-z0-9_]", "_", name).upper()

    # Check if the normalized name starts with a digit
    if env_variable_name[0].isdigit():
        raise ValueError(
            f"Invalid environment variable name '{env_variable_name}': Cannot start with a digit."
        )

    return env_variable_name


class SpecialEdges(str, Enum):
    start = "START"
    end = "END"


class BrainConfig(QuivrBaseConfig):
    brain_id: UUID | None = None
    name: str

    @property
    def id(self) -> UUID | None:
        return self.brain_id


class DefaultWebSearchTool(str, Enum):
    TAVILY = "tavily"


# DefaultRerankers 枚举类
# -------------------------------------------
# 作用：在 RAG 检索增强生成系统（RAG: Retrieval-Augmented Generation）中，DefaultRerankers 是内置重排序器（reranker）供应商的枚举（Enum）。
# 它用来规范和管理可以调用的“语义重排序服务”类型，便于后续统一配置和调用。例如检索后拿到 40 个 chunk，常常要用更智能的 reranker（不是简单 embedding 距离）做二次相关性排序。
#
# 枚举中的两个值分别如下：
# - COHERE：对应 Cohere 公司提供的语义重排序 API。Cohere 是加拿大一家专注于 NLP 的人工智能公司，其 rerank API 广泛应用于向量检索、文档排序、结构化知识检索等工业用例，支持多语言大模型服务。
# - JINA：对应 Jina AI 公司旗下的重排序服务（如 jina-reranker-v2-base-multilingual）。Jina AI 在开源和商业向量检索领域有较多实用解决方案，特别聚焦于多模态、神经向量数据库和下游 ranking。
#
# 在 rag 系统的作用：
# - 这个枚举配合 RerankerConfig 配置，允许开发者直接指定用哪个主流重量级 reranking 工具，避免自由拼写带来的风险。
# - 能帮助系统（如 UI、API、自动推荐等）枚举所有支持的 reranker 类型，并通过 default_model 属性直接拿到推荐的主力模型。
# - 让向量检索后的二次 re-ranking 选择更加结构化，方便扩展、切换及参数检查。
#
# 举例（伪代码）：
#   reranker_config = RerankerConfig(supplier=DefaultRerankers.COHERE)  # 会默认选择 Cohere 推荐的 rerank-v3.5 模型
#   print(DefaultRerankers.JINA.default_model)  # 输出："jina-reranker-v2-base-multilingual"
class DefaultRerankers(str, Enum):
    COHERE = "cohere"
    JINA = "jina"
    # MIXEDBREAD = "mixedbread-ai"

    @property
    def default_model(self) -> str:
        # Mapping of suppliers to their default models
        return {
            self.COHERE: "rerank-v3.5",
            self.JINA: "jina-reranker-v2-base-multilingual",
            # self.MIXEDBREAD: "rmxbai-rerank-large-v1",
        }[self]


class DefaultModelSuppliers(str, Enum):
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    META = "meta"
    MISTRAL = "mistral"
    GROQ = "groq"
    GEMINI = "gemini"


class LLMConfig(QuivrBaseConfig):
    max_context_tokens: int | None = None
    max_output_tokens: int | None = None
    tokenizer_hub: str | None = None


class LLMModelConfig:
    _model_defaults: Dict[DefaultModelSuppliers, Dict[str, LLMConfig]] = {
        DefaultModelSuppliers.OPENAI: {
            "gpt-4.1": LLMConfig(
                max_context_tokens=1047576,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4o": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=16384,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4o-mini": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=16384,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o3-mini": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o4-mini": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1-mini": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=65536,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1-preview": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "o1": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=100000,
                tokenizer_hub="Quivr/gpt-4o",
            ),
            "gpt-4-turbo": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gpt-4",
            ),
            "gpt-4": LLMConfig(
                max_context_tokens=8192,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/gpt-4",
            ),
            "gpt-3.5-turbo": LLMConfig(
                max_context_tokens=16385,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gpt-3.5-turbo",
            ),
            "text-embedding-3-large": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
            "text-embedding-3-small": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
            "text-embedding-ada-002": LLMConfig(
                max_context_tokens=8191, tokenizer_hub="Quivr/text-embedding-ada-002"
            ),
        },
        DefaultModelSuppliers.ANTHROPIC: {
            "claude-opus-4": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-sonnet-4": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-7-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-5-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=8192,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-opus": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-sonnet": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-3-haiku": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-2-1": LLMConfig(
                max_context_tokens=200000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-2-0": LLMConfig(
                max_context_tokens=100000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
            "claude-instant-1-2": LLMConfig(
                max_context_tokens=100000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/claude-tokenizer",
            ),
        },
        # Unclear for LLAMA models...
        # see https://huggingface.co/meta-llama/Llama-3.1-405B-Instruct/discussions/6
        DefaultModelSuppliers.META: {
            "llama-3.1": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3": LLMConfig(
                max_context_tokens=8192,
                max_output_tokens=2048,
                tokenizer_hub="Quivr/llama3-tokenizer-new",
            ),
            "code-llama": LLMConfig(
                max_context_tokens=16384, tokenizer_hub="Quivr/llama-code-tokenizer"
            ),
        },
        DefaultModelSuppliers.GROQ: {
            "llama-3.3-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3.1-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "llama-3": LLMConfig(
                max_context_tokens=8192, tokenizer_hub="Quivr/llama3-tokenizer-new"
            ),
            "code-llama": LLMConfig(
                max_context_tokens=16384, tokenizer_hub="Quivr/llama-code-tokenizer"
            ),
            "deepseek-r1-distill-llama-70b": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
            "meta-llama/llama-4-maverick-17b-128e-instruct": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=32768,
                tokenizer_hub="Quivr/Meta-Llama-3.1-Tokenizer",
            ),
        },
        DefaultModelSuppliers.MISTRAL: {
            "mistral-large": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/mistral-tokenizer-v3",
            ),
            "mistral-small": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/mistral-tokenizer-v3",
            ),
            "mistral-nemo": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/Mistral-Nemo-Instruct-Tokenizer",
            ),
            "codestral": LLMConfig(
                max_context_tokens=32000, tokenizer_hub="Quivr/mistral-tokenizer-v3"
            ),
        },
        DefaultModelSuppliers.GEMINI: {
            "gemini-2.5": LLMConfig(
                max_context_tokens=128000,
                max_output_tokens=4096,
                tokenizer_hub="Quivr/gemini-tokenizer",
            ),
        },
    }

    @classmethod
    def get_supplier_by_model_name(cls, model: str) -> DefaultModelSuppliers | None:
        # Iterate over the suppliers and their models
        for supplier, models in cls._model_defaults.items():
            # Check if the model name or a base part of the model name is in the supplier's models
            for base_model_name in models:
                if model.startswith(base_model_name):
                    return supplier
        # Return None if no supplier matches the model name
        return None

    @classmethod
    def get_llm_model_config(
        cls, supplier: DefaultModelSuppliers, model_name: str
    ) -> Optional[LLMConfig]:
        """Retrieve the LLMConfig (context and tokenizer_hub) for a given supplier and model."""
        supplier_defaults = cls._model_defaults.get(supplier)
        if not supplier_defaults:
            return None

        # Use startswith logic for matching model names
        for key, config in supplier_defaults.items():
            if model_name.startswith(key):
                return config

        return None


class LLMEndpointConfig(QuivrBaseConfig):
    supplier: DefaultModelSuppliers = DefaultModelSuppliers.OPENAI
    model: str = "gpt-4o"
    tokenizer_hub: str | None = None
    llm_base_url: str | None = None
    env_variable_name: str | None = None
    llm_api_key: str | None = None
    max_context_tokens: int = 20000
    max_output_tokens: int = 4096
    temperature: float = 0.3
    streaming: bool = True
    prompt: BasePromptTemplate | None = None

    _FALLBACK_TOKENIZER = "cl100k_base"

    def __hash__(self):
        return hash(
            (
                self.supplier,
                self.model,
                self.tokenizer_hub,
                self.llm_base_url,
                self.env_variable_name,
                self.llm_api_key,
                self.max_context_tokens,
                self.max_output_tokens,
                self.temperature,
                self.streaming,
                repr(self.prompt) if self.prompt is not None else None,
            )
        )

    @property
    def fallback_tokenizer(self) -> str:
        return self._FALLBACK_TOKENIZER

    def __init__(self, **data):
        super().__init__(**data)
        self.set_llm_model_config()
        self.set_api_key()

    def set_api_key(self, force_reset: bool = False):
        if not self.supplier:
            return

        # Check if the corresponding API key environment variable is set
        if force_reset or not self.env_variable_name:
            self.env_variable_name = (
                f"{normalize_to_env_variable_name(self.supplier)}_API_KEY"
            )

        if not self.llm_api_key or force_reset:
            self.llm_api_key = os.getenv(self.env_variable_name)

        if not self.llm_api_key:
            logger.warning(f"The API key for supplier '{self.supplier}' is not set. ")
            logger.warning(
                f"Please set the environment variable: '{self.env_variable_name}'. "
            )

    def set_llm_model_config(self):
        # Automatically set context_length and tokenizer_hub based on the supplier and model
        llm_model_config = LLMModelConfig.get_llm_model_config(
            self.supplier, self.model
        )
        if llm_model_config:
            if llm_model_config.max_context_tokens:
                _max_context_tokens = (
                    llm_model_config.max_context_tokens
                    - llm_model_config.max_output_tokens
                    if llm_model_config.max_output_tokens
                    else llm_model_config.max_context_tokens
                )
                if self.max_context_tokens > _max_context_tokens:
                    logger.warning(
                        f"Lowering max_context_tokens from {self.max_context_tokens} to {_max_context_tokens}"
                    )
                    self.max_context_tokens = _max_context_tokens

                if self.max_context_tokens < MIN_CONTEXT_TOKENS:
                    logger.error(
                        f"max_context_tokens is too low: {self.max_context_tokens}. "
                    )
                    raise ValueError(
                        f"max_context_tokens is too low: {self.max_context_tokens}. "
                    )
            if llm_model_config.max_output_tokens:
                if self.max_output_tokens > llm_model_config.max_output_tokens:
                    logger.warning(
                        f"Lowering max_output_tokens from {self.max_output_tokens} to {llm_model_config.max_output_tokens}"
                    )
                    self.max_output_tokens = llm_model_config.max_output_tokens

                if self.max_output_tokens < MIN_OUTPUT_TOKENS:
                    logger.error(
                        f"max_output_tokens is too low: {self.max_output_tokens}. "
                    )
                    raise ValueError(
                        f"max_output_tokens is too low: {self.max_output_tokens}. "
                    )

            self.tokenizer_hub = llm_model_config.tokenizer_hub

    def set_llm_model(self, model: str):
        supplier = LLMModelConfig.get_supplier_by_model_name(model)
        if supplier is None:
            raise ValueError(
                f"Cannot find the corresponding supplier for model {model}"
            )
        self.supplier = supplier
        self.model = model

        self.set_llm_model_config()
        self.set_api_key(force_reset=True)

    def set_from_sqlmodel(self, sqlmodel: BaseModel, mapping: Dict[str, str]):
        """
        Set attributes in LLMEndpointConfig from Model attributes using a field mapping.

        :param model_instance: An instance of the Model class.
        :param mapping: A dictionary that maps Model fields to LLMEndpointConfig fields.
                        Example: {"max_input": "max_input_tokens", "env_variable_name": "env_variable_name"}
        """
        for model_field, llm_field in mapping.items():
            if hasattr(sqlmodel, model_field) and hasattr(self, llm_field):
                setattr(self, llm_field, getattr(sqlmodel, model_field))
            else:
                raise AttributeError(
                    f"Invalid mapping: {model_field} or {llm_field} does not exist."
                )


# Cannot use Pydantic v2 field_validator because of conflicts with pydantic v1 still in use in LangChain
class RerankerConfig(QuivrBaseConfig):
    supplier: DefaultRerankers | None = None
    model: str | None = None
    top_n: int = 5  # Number of chunks returned by the re-ranker
    api_key: str | None = None
    relevance_score_threshold: float | None = None
    relevance_score_key: str = "relevance_score"

    def __init__(self, **data):
        super().__init__(**data)  # Call Pydantic's BaseModel init
        self.validate_model()  # Automatically call external validation

    def validate_model(self):
        # If model is not provided, get default model based on supplier
        if self.model is None and self.supplier is not None:
            self.model = self.supplier.default_model

        # Check if the corresponding API key environment variable is set
        if self.supplier:
            api_key_var = f"{normalize_to_env_variable_name(self.supplier)}_API_KEY"
            self.api_key = os.getenv(api_key_var)

            if self.api_key is None:
                raise ValueError(
                    f"The API key for supplier '{self.supplier}' is not set. "
                    f"Please set the environment variable: {api_key_var}"
                )


class ConditionalEdgeConfig(QuivrBaseConfig):
    routing_function: str
    conditions: Union[list, Dict[Hashable, str]]

    def __init__(self, **data):
        super().__init__(**data)
        self.resolve_special_edges()

    def resolve_special_edges(self):
        """Replace SpecialEdges enum values with their corresponding langgraph values."""

        if isinstance(self.conditions, dict):
            # If conditions is a dictionary, iterate through the key-value pairs
            for key, value in self.conditions.items():
                if value == SpecialEdges.end:
                    self.conditions[key] = END
                elif value == SpecialEdges.start:
                    self.conditions[key] = START
        elif isinstance(self.conditions, list):
            # If conditions is a list, iterate through the values
            for index, value in enumerate(self.conditions):
                if value == SpecialEdges.end:
                    self.conditions[index] = END
                elif value == SpecialEdges.start:
                    self.conditions[index] = START


class NodeConfig(QuivrBaseConfig):
    name: str
    description: str | None = None
    edges: List[str] | None = None
    conditional_edge: ConditionalEdgeConfig | None = None
    tools: List[Dict[str, Any]] | None = None
    instantiated_tools: List[BaseTool | Type] | None = None

    def __init__(self, **data):
        super().__init__(**data)
        self._instantiate_tools()
        self.resolve_special_edges_in_name_and_edges()

    def resolve_special_edges_in_name_and_edges(self):
        """Replace SpecialEdges enum values in name and edges with corresponding langgraph values."""
        if self.name == SpecialEdges.start:
            self.name = START
        elif self.name == SpecialEdges.end:
            self.name = END

        if self.edges:
            for i, edge in enumerate(self.edges):
                if edge == SpecialEdges.start:
                    self.edges[i] = START
                elif edge == SpecialEdges.end:
                    self.edges[i] = END

    def _instantiate_tools(self):
        """Instantiate tools based on the configuration."""
        if self.tools:
            self.instantiated_tools = [
                LLMToolFactory.create_tool(tool_config.pop("name"), tool_config)
                for tool_config in self.tools
            ]


class DefaultWorkflow(str, Enum):
    RAG = "rag"

    @property
    def nodes(self) -> List[NodeConfig]:
        # Mapping of workflow types to their default node configurations
        workflows = {
            self.RAG: [
                NodeConfig(name=START, edges=["filter_history"]),
                NodeConfig(name="filter_history", edges=["rewrite"]),
                NodeConfig(name="rewrite", edges=["retrieve"]),
                NodeConfig(name="retrieve", edges=["generate_rag"]),
                NodeConfig(name="generate_rag", edges=[END]),
            ]
        }
        return workflows[self]


class WorkflowConfig(QuivrBaseConfig):
    name: str | None = None
    nodes: List[NodeConfig] = []
    available_tools: List[str] | None = None
    validated_tools: List[BaseTool | Type] = []
    activated_tools: List[BaseTool | Type] = []

    def __init__(self, **data):
        super().__init__(**data)
        self.check_first_node_is_start()
        self.validate_available_tools()

    def check_first_node_is_start(self):
        # 为什么应该是 SpecialEdges.start？
        # 在 RAG 工作流配置中，节点（nodes）描述了问题处理经过的步骤和流向。
        # 工作流需要有明确的起点，以保证每次流程都是从“入口节点”有序开始：
        # - START 节点标志流程的起始，后续所有工具、节点执行顺序都依赖这个有序流动。
        # - 如果第一个节点不是 START，整个流程框架可能无法连接所有后续节点，存在无效配置或异常跳转。
        # - 即：“流程必须有唯一/显式的入口点。”
        if self.nodes and self.nodes[0].name != START:
            # 如果工作流配置的第一个节点不是 START，抛异常 warn 配置错误
            raise ValueError(f"The first node should be a {SpecialEdges.start} node")

    # ======================================
    # RAG 系统 workflow 中 node 的典型量级和不同场景说明
    #
    # - 通常每个 RAG 工作流只包含 4~8 个 nodes（节点），覆盖从输入、预处理、检索到生成等基本处理流程。
    # - 实际 node 总数与流程复杂度高度相关：
    #   - 标准“问题→检索→生成”流程，节点一般有 START、filter_history、rewrite、retrieve、generate_rag、END 共 5~6 个，属于经典 minimum RAG pipeline。
    #   - 如果有多模型召回、多步推理、插入 rerank/聚合环节，节点可能增至 8~15 个（如检索规则、聚合复杂度、上下文增强、调用外部工具等）。
    #   - 企业级场景/链式多 RAG 可能一个 workflow 有十几二十个 nodes，把语音识别、结构化抽取、多文档裁剪等都串进来。
    # - 通常一个 node 承担一个语义步骤，如 rewrite 输入、筛选历史、调检索、上下文聚合、最终生成，每步细分都可设计一个 node。
    # - 对于交互简洁的问答机器人，nodes 量级控制在 5~10 最易管理、易观测和 debug。
    # - 工具类/插件流式场景，可能某些 node 负责 tool-invoke、function-call 或包裹外部 API。
    # - RAG 全链路流程推荐每个 node 做到单一职责、可插拔，进阶场景支持 workflow 动态配置和扩展。
    #
    # 下面是获取指定节点 tools（工具插件）的代码接口。
    
    # quivr 当前最小原生 workflow（参见 DefaultWorkflow.RAG.nodes）里，一共定义了 5 个 node：
    # - START
    # - filter_history
    # - rewrite
    # - retrieve
    # - generate_rag
    #   终止节点为 END，但 END 不单独实例化 node（只是 edges 跳转终点，不参与 tools 分配）。
    # 如需复用可变流程，实际 node 数会随 workflow 配置增长，但默认最小主链路为 5 个步骤。
    def get_node_tools(self, node_name: str) -> List[Any]:
        """Get tools for a specific node."""
        for node in self.nodes:
            if node.name == node_name and node.instantiated_tools:
                return node.instantiated_tools
        return []


    # validate_available_tools 的逻辑：
    # - 负责检测 workflow/workflow_config/assistant_config 里声明的 available_tools 字段里每个工具名是否在系统已支持的工具白名单内。
    # - 校验通过则自动将工具对象实例化 append 到 self.validated_tools，为下游 RAG 执行流直接引用。
    # - 校验不通过时，报错并给出拼写建议，避免写错工具名“静默失效”。
    #
    # 为什么需要 validate?
    # - RAG 流程允许用户灵活配置“这轮推理能用哪些工具”，但必须保证这些工具确实已在当前后端注册。
    # - 如果没有提前 validate，流程执行时一旦引用了不存在工具，会导致难以定位的错误或运行期崩溃。
    # - 通过集中统一校验，把所有合法性错误提前暴露、强约束，提升体验。
    #
    # quivr 项目内内置的工具（tool）有哪些？
    # -----【下面是目前 quivr 默认内置与支持的 tool 类型说明】-----
    # 工具是 RAG 流程节点可以动态调用的“外部智能插件”，用于支撑特定功能如搜索、内容生成、数据处理等。
    # 主要类别有（依赖 TOOLS_CATEGORIES 和 TOOLS_LISTS 注册表，详见 llm_tools 源码）：
    #
    # 1. TOOLS_CATEGORIES 里的工具（按大类分组）：
    #    - "web_search"      网络检索型工具（例：实时查网页、Bing/Web接口）
    #    - "calculator"      算法/计算器（例：复杂数学计算）
    #    - "summarizer"      内容摘要与压缩
    #    - "python"          代码执行
    #    - "file_read"       文件读入/解析
    #    - ...（可能持续增加，依据 quivr_core/llm_tools/ 目录注册的合集）
    #
    # 2. TOOLS_LISTS 里的工具（每类下的具体实现名）：
    #    - 如 web_search 下包含 "tavily", "serpapi" 等具体接口工具名
    #    - "calculator" 下包含基础 calculator、复杂 math 等
    #    - 其它如 "text_qa"，"summary" 等。
    #
    # 3. 用户自定义或扩展工具
    #    - 用户可以自定义 LLMSkill/Tool 实现，注册到 TOOLS_LISTS。
    #    - 只要在工具注册表声明，validate 就能识别。
    #
    # tools 配置举例:
    #   available_tools = ["web_search", "tavily", "calculator", "summarizer"]
    # 
    #   其中既可以填大类名（由系统自动分配同类内所有实现），也可以按需点名具体类别或某个专用子工具。
    #
    def validate_available_tools(self):
        if self.available_tools:
            valid_tools = list(TOOLS_CATEGORIES.keys()) + list(TOOLS_LISTS.keys())
            for tool in self.available_tools:
                if tool.lower() in valid_tools:
                    self.validated_tools.append(
                        LLMToolFactory.create_tool(tool, {}).tool
                    )
                else:
                    matches = process.extractOne(
                        tool.lower(), valid_tools, scorer=fuzz.WRatio
                    )
                    if matches:
                        raise ValueError(
                            f"Tool {tool} is not a valid ToolsCategory or ToolsList. Did you mean {matches[0]}?"
                        )
                    else:
                        raise ValueError(
                            f"Tool {tool} is not a valid ToolsCategory or ToolsList"
                        )


class RetrievalConfig(QuivrBaseConfig):
    """
    RetrievalConfig 负责配置 RAG 检索阶段的整体行为，包括召回参数、历史窗口、文件数等。

    参数说明：
    - max_history: 历史对话窗口的最大轮数，决定问答时携带多少轮上下文给模型参与检索（影响多轮对话时上下文保留的深度）。
    - max_files: 检索场景下，允许纳入检索范围的最大文件数（例如当上传多个文档时，检索操作会限定只在前N个文件中召回）。
    - k: 控制向量召回时返回的 chunk 数量。实际 RAG 检索时，向量数据库会返回与输入 query 最近的前k个文本片段（chunk），这些 chunk 作为检索环节的主要输入，也就是 RAG“读进来多少知识”的软上限。

    这些参数协同决定了：RAG 检索时能引用的历史范围、可以用到的文件上限，以及每次检索端返回给 llm 的 chunk 数量。增大这些参数通常能提升召回范围，但也可能带来响应变慢、召回不精等副作用。
    """
    reranker_config: RerankerConfig = RerankerConfig()
    llm_config: LLMEndpointConfig = LLMEndpointConfig()
    max_history: int = 10
    max_files: int = 20
    k: int = 40  # Number of chunks returned by the retriever
    prompt: str | None = None
    workflow_config: WorkflowConfig = WorkflowConfig(nodes=DefaultWorkflow.RAG.nodes)

    def __init__(self, **data):
        super().__init__(**data)
        self.llm_config.set_api_key(force_reset=True)


class ParserConfig(QuivrBaseConfig):
    splitter_config: SplitterConfig = SplitterConfig()
    megaparse_config: MegaparseConfig = MegaparseConfig()


class IngestionConfig(QuivrBaseConfig):
    parser_config: ParserConfig = ParserConfig()


class AssistantConfig(QuivrBaseConfig):
    retrieval_config: RetrievalConfig = RetrievalConfig()
    ingestion_config: IngestionConfig = IngestionConfig()
