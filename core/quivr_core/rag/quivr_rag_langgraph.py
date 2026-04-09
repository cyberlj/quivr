import asyncio
import datetime
import logging
from collections import OrderedDict
from typing import (
    Annotated,
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
)
from uuid import UUID, uuid4

import openai
from langchain.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain_community.document_compressors import JinaRerank
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.messages.ai import AIMessageChunk
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.prompts.base import BasePromptTemplate
from langchain_core.runnables.schema import StreamEvent
from langchain_core.vectorstores import VectorStore
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Send
from pydantic import BaseModel, Field

from quivr_core.llm import LLMEndpoint
from quivr_core.llm_tools.llm_tools import LLMToolFactory
from quivr_core.rag.entities.chat import ChatHistory
from quivr_core.rag.entities.config import DefaultRerankers, NodeConfig, RetrievalConfig
from quivr_core.rag.entities.models import (
    LangchainMetadata,
    ParsedRAGChunkResponse,
    QuivrKnowledge,
    RAGResponseMetadata,
)
from quivr_core.rag.prompts import TemplatePromptName, custom_prompts
from quivr_core.rag.utils import (
    LangfuseService,
    collect_tools,
    combine_documents,
    format_dict,
    format_file_list,
    get_chunk_metadata,
    parse_chunk_response,
)

logger = logging.getLogger("quivr_core")

langfuse_service = LangfuseService()
langfuse_handler = langfuse_service.get_handler()


class SplittedInput(BaseModel):
    instructions_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the user instructions to the system",
    )
    instructions: Optional[str] = Field(
        default=None, description="The instructions to the system"
    )

    tasks_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the explicit or implicit user tasks and questions",
    )
    task_list: Optional[List[str]] = Field(
        default_factory=lambda: ["No explicit or implicit tasks found"],
        description="The list of standalone, self-contained tasks or questions.",
    )


class TasksCompletion(BaseModel):
    is_task_completable_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying whether the user task or question can be completed using the provided context and chat history BEFORE any tool is used.",
    )

    is_task_completable: bool = Field(
        description="Whether the user task or question can be completed using the provided context and chat history BEFORE any tool is used.",
    )

    tool_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to identifying the tool that shall be used to complete the task.",
    )
    tool: Optional[str] = Field(
        description="The tool that shall be used to complete the task.",
    )


class FinalAnswer(BaseModel):
    reasoning_answer: str = Field(
        description="The step-by-step reasoning that led to the final answer"
    )
    answer: str = Field(description="The final answer to the user tasks/questions")

    all_tasks_completed: bool = Field(
        description="Whether all tasks/questions have been successfully answered/completed or not. "
        " If the final answer to the user is 'I don't know' or 'I don't have enough information' or 'I'm not sure', "
        " this variable should be 'false'"
    )


class UpdatedPromptAndTools(BaseModel):
    prompt_reasoning: Optional[str] = Field(
        default=None,
        description="The step-by-step reasoning that leads to the updated system prompt",
    )
    prompt: Optional[str] = Field(default=None, description="The updated system prompt")

    tools_reasoning: Optional[str] = Field(
        default=None,
        description="The reasoning that leads to activating and deactivating the tools",
    )
    tools_to_activate: Optional[List[str]] = Field(
        default_factory=list, description="The list of tools to activate"
    )
    tools_to_deactivate: Optional[List[str]] = Field(
        default_factory=list, description="The list of tools to deactivate"
    )


class UserTaskEntity(BaseModel):
    id: UUID
    definition: str
    docs: List[Document] = Field(default_factory=list)
    completable: bool = Field(
        default=False, description="Whether the task has been completed or not"
    )
    tool: Optional[str] = Field(
        default=None, description="The tool that shall be used to complete the task"
    )

    def has_tool(self) -> bool:
        return bool(self.tool)

    def is_completable(self) -> bool:
        return self.completable


class UserTasks:
    def __init__(self, task_definitions: List[str] | None = None):
        self.user_tasks = {}
        if task_definitions:
            for definition in task_definitions:
                id = uuid4()
                self.user_tasks[id] = UserTaskEntity(
                    id=id, definition=definition, docs=[]
                )

    def __iter__(self):
        return iter(self.user_tasks.values())

    def set_docs(self, id: UUID, docs: List[Document]):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].docs = docs
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_definition(self, id: UUID, definition: str):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].definition = definition
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_completion(self, id: UUID, completable: bool):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].completable = completable
            else:
                raise ValueError(f"Task with id {id} not found")

    def set_tool(self, id: UUID, tool: str):
        if self.user_tasks:
            if id in self.user_tasks:
                self.user_tasks[id].tool = tool
            else:
                raise ValueError(f"Task with id {id} not found")

    def __call__(self, id: UUID) -> UserTaskEntity:
        return self.user_tasks[id]

    def has_tasks(self) -> bool:
        return bool(self.user_tasks)

    def has_non_completable_tasks(self) -> bool:
        return bool(self.non_completable_tasks)

    @property
    def non_completable_tasks(self) -> List[UserTaskEntity]:
        return [task for task in self.user_tasks.values() if not task.is_completable()]

    @property
    def completable_tasks(self) -> List[UserTaskEntity]:
        return [task for task in self.user_tasks.values() if task.is_completable()]

    @property
    def ids(self) -> List[UUID]:
        return list(self.user_tasks.keys())

    @property
    def definitions(self) -> List[str]:
        return [task.definition for task in self.user_tasks.values()]

    @property
    def docs(self) -> List[Document]:
        # Return the concatenation of all docs
        return [doc for task in self.user_tasks.values() for doc in task.docs]


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    reasoning: List[str]
    chat_history: ChatHistory
    files: str
    tasks: UserTasks
    instructions: str
    ticket_metadata: Optional[dict[str, str]]
    user_metadata: Optional[dict[str, str]]
    additional_information: Optional[dict[str, str]]
    tool: str
    guidelines: str
    enforced_system_prompt: str
    _filter: Optional[Dict[str, Any]]
    ticket_history: str


class IdempotentCompressor(BaseDocumentCompressor):
    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """
        A no-op document compressor that simply returns the documents it is given.

        This is a placeholder until a more sophisticated document compression
        algorithm is implemented.
        """
        return documents


# ===================
# QuivrQARAGLangGraph 这个类用来封装和协调 RAG（Retrieval Augmented Generation，检索增强生成）流程，结合了检索（Retriever）、重排序（Reranker）和大模型生成（LLM）等能力，是贯穿“资料召回-相关性排序-AI生成回答”完整链路的核心编排入口。
# 
# 作用总结：
# - 统一持有检索配置(retrieval_config)、向量库(vector_store)、大模型(LLM)等关键组件。
# - 负责实例化和选择不同的重排序器(reranker)，比如 Cohere Rerank，可以让检索结果经过大模型理解后再排序，提升检索+生成的相关性。
# - 作为多步骤RAG推理编排的主流程入口，使外部例如Brain能够调用 answer_astream 或其它方法与底层RAG流程解耦。
# 
# 典型调用链举例：
#     Brain（决策层） --> QuivrQARAGLangGraph（RAG流程层） --> Retriever/Reranker/LLM（检索与生成底层）
# 
# 设计意义：
# - 让检索/排序/生成能力可以灵活互换、易于扩展、可插拔，方便不同场景下快速切换底层实现。
# - 为后续支持更复杂的多工具长链路RAG（如LangGraph工作流）封装好流程入口，未来加功能也只需扩展这里的流程节点。
class QuivrQARAGLangGraph:
    def __init__(
        self,
        *,
        retrieval_config: RetrievalConfig,
        llm: LLMEndpoint,
        vector_store: VectorStore | None = None,
    ):
        """
        Construct a QuivrQARAGLangGraph object.

        Args:
            retrieval_config (RetrievalConfig): The configuration for the RAG model.
            llm (LLMEndpoint): The LLM to use for generating text.
            vector_store (VectorStore): The vector store to use for storing and retrieving documents.
            reranker (BaseDocumentCompressor | None): The document compressor to use for re-ranking documents. Defaults to IdempotentCompressor if not provided.
        """
        self.retrieval_config = retrieval_config
        self.vector_store = vector_store
        self.llm_endpoint = llm

        # 这里 self.graph 赋值为 None，目的是实现“懒加载”（lazy initialization）——也就是在对象创建时暂不构建 LangGraph 工作流，而是等到首次需要使用时（通常在 answer_astream 或 get_or_create_graph 等方法中）再真正初始化 self.graph。
        # 这样做的好处是：有些 RAG 配置或依赖对象可能会在 __init__ 后续阶段（如热加载、外部配置等）才确定，提前实例化工作流反而会浪费资源或导致出错。因此这里用 None 作为占位，后续再根据需要补全 graph 实例。
        # type: ignore[name-defined] 是为了静态检查友好，这里 LangGraph 只是类型注释，具体实现在 runtime 时构造。
        self.graph = None  # type: ignore[name-defined]

    # get_reranker 方法的作用是：根据当前的 reranker 配置（如 supplier、model、api_key 等），实例化并返回一个文档重排序器（Reranker）对象，例如 CohereRerank 或 JinaRerank。
    # 这个重排序器会在 RAG 流程中，对初步检索出来的一批文档，利用大模型（或深度双塔/跨编码器）算法，按query与文档的“实际语义相关性”进行精细化排序，提升后续生成式AI回答的准确性和上下文匹配度。
    # 典型作用场景是在“向量检索”结果不精准时，进一步用强模型比对 query 和每个 doc 的关联度，选出最贴合用户问题的那几条文档，最终送交LLM生成答案。
    def get_reranker(self, **kwargs):
        # Extract the reranker configuration from self
        config = self.retrieval_config.reranker_config

        # Allow kwargs to override specific config values
        supplier = kwargs.pop("supplier", config.supplier)
        model = kwargs.pop("model", config.model)
        top_n = kwargs.pop("top_n", config.top_n)
        api_key = kwargs.pop("api_key", config.api_key)

        if supplier == DefaultRerankers.COHERE: # 提供语意重排序
            # Cohere Rerank 实际上是用类似于 LLM 架构（Transformer 大模型）来做检索结果的语义重排序（cross-encoder），不是用 embedding 向量距离简单排，而是模型“读懂”了 query 与文档关系再打分。
            # 算法流程如下：
            #   1. 输入：召回的一组文档与1条用户query。
            #   2. Cohere Rerank 内部用一个“跨编码器”大模型，把query和每个文档拼接，送入Transformer。
            #   3. 模型（预训练自带）会像LLM理解问答语境那样，输出一个相关性分数（如0.93/0.44），代表该文档与query的结合程度。
            #   4. 最后对所有召回文档，按这个分数降序重新排序，选分最高的前N。
            # 举例：
            #   - query: "什么叫图神经网络"
            #   - 文档A: "图神经网络用于处理图结构数据，比如社交关系、化合物分析。"
            #   - 文档B: "GAN是一种生成模型。"
            #   - 文档C: "卷积神经网络擅长图像任务。"
            #   Rerank输出（分数）：A 0.95, C 0.37, B 0.15
            #   排序后：[A, C, B]
            # 总结：
            #   - 是“用大模型做精细比对，让模型主动理解query和文档谁更相关”，与传统“只比向量距离”完全不同，效果提升显著。
            #   - 模型本身属于预训练大模型范畴，所以本质上确实是“借助了LLM进行重排序”，但它专门调优了排序能力，和一般生成式LLM（ChatGPT这类）不同，不是直接生成内容，而是专注于相关性打分排序。
            reranker = CohereRerank(
                model=model, top_n=top_n, cohere_api_key=api_key, **kwargs
            )
        elif supplier == DefaultRerankers.JINA:
            # JinaRerank 实现的也是基于深度神经网络的重排序（Rerank）算法，采用跨编码器（cross-encoder）结构，与 Cohere Rerank 类似，但有一些区别。
            # Jina Reranker 的底层核心流程如下：
            #   1. 输入：一组召回回来的文档 + 用户 query。
            #   2. Jina 的重排序 API（如 jina-reranker-v2-base-en/zh）会将 query 和每个文档拼成对：
            #       (query, doc1), (query, doc2), ...
            #   3. 每对送进神经网络模型（如 Jina 训练的改进型 Transformer），模型“深度理解”query 与文档内容，评分每一组的相关性（通常为0~1的分数）。
            #   4. 按分数降序排列文档，排序后的前 top_n 作为最终的高相关性检索结果。
            # 具体例子：
            #   - query: "中心极限定理的应用"
            #   - docA: "中心极限定理广泛应用于金融风险建模与抽样分布分析。"
            #   - docB: "大语言模型在NLP里非常流行。"
            #   执行 Jina Rerank，得到分数：A 0.94, B 0.21
            #   排序结果：[A, B]
            #
            # 【与 Cohere Rerank 的区别】
            #   - 算法原理都采用 cross-encoder（大模型读query和文档后统一判别相关性），但底层模型权重和数据来源有差异：
            #     - Cohere 的 Rerank 通常在英文或多语种全球主流数据集上训练，覆盖面广，适合国际化/英文本地化场景。
            #     - Jina Rerank 有专门针对中文的版本（如 zh-v2），在中文语料/问答场景做过较多优化，适合纯中文/双语本地化场景，推理接口国内CDN极快。
            #   - API 访问与授权方式略有不同，Jina 国内部署便利性更强、低延时，Cohere 在海外云端更易获得算力和可用性。
            #   - 两者都支持RAG场景下的高相关性排序，但针对行业和语种细节，Jina 在中国区和中文提升更自然；Cohere 更均衡面向通用语种和国际业务。
            #
            # 【场景适用建议】
            #   - 优先选 JinaRerank：你需要高性能中文重排序、本地快、国产模型合规，或者你的知识库问答对象大部分是中文。
            #   - 优先选 CohereRerank：你的业务以英文/多语种为主，注重全球化/模型权重的稳定与通用性，对国内加速无极致要求。
            reranker = JinaRerank(
                model=model, top_n=top_n, jina_api_key=api_key, **kwargs
            )
        else:
            # IdempotentCompressor 和 Cohere/Jina Rerank 的区别：
            # - CohereRerank/JinaRerank 都是 "跨编码器大模型" 方式进行真实的语义重排序，会读取 query-文档对理解其相关性，然后输出一个相关性分数，真正打乱原本的向量检索顺序，效果大幅提升。
            # - IdempotentCompressor 并不是重排序 "Reranker" 算法，更像是一个“不改变顺序/不做语义判断”的压缩器（无操作或者pass-through占位实现），它不会分析 query 与 doc 的语义关系，也不重新打分，只是把原输入列表原样返回。
            # - 适用场景一般为“未指定任何重排序算法时的兜底/占位”，确保整个RAG流程成立，但不会对输出顺序做任何优化。
            # - 所以选用 IdempotentCompressor 并不能提升结果，只能保证没有重排序时流程不中断。
            reranker = IdempotentCompressor()

        return reranker

    def get_retriever(self, **kwargs):
        """
        Returns a retriever that can retrieve documents from the vector store.

        Returns:
            VectorStoreRetriever: The retriever.
        """
        if self.vector_store:
            retriever = self.vector_store.as_retriever(**kwargs)
        else:
            raise ValueError("No vector store provided")

        return retriever

    def routing(self, state: AgentState) -> List[Send]:
        """
        The routing function for the RAG model.

        Args:
            state (AgentState): The current state of the agent.

        Returns:
            dict: The next state of the agent.
        """

        msg = custom_prompts[TemplatePromptName.SPLIT_PROMPT].format(
            user_input=state["messages"][0].content,
        )

        response: SplittedInput

        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                SplittedInput, method="json_schema"
            )
            response = structured_llm.invoke(msg)

        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                SplittedInput
            )
            response = structured_llm.invoke(msg)

        send_list: List[Send] = []

        instructions = (
            response.instructions
            if response.instructions
            else self.retrieval_config.prompt
        )

        if instructions:
            send_list.append(Send("edit_system_prompt", {"instructions": instructions}))
        elif response.task_list:
            chat_history = state["chat_history"]
            send_list.append(
                Send(
                    "filter_history",
                    {
                        "chat_history": chat_history,
                        "tasks": UserTasks(response.task_list),
                    },
                )
            )

        return send_list

    def routing_split(self, state: AgentState):
        response: SplittedInput = self.invoke_structured_output(
            custom_prompts[TemplatePromptName.SPLIT_PROMPT].format(
                chat_history=state["chat_history"].to_list(),
                user_input=state["messages"][0].content,
            ),
            SplittedInput,
        )

        instructions = response.instructions or self.retrieval_config.prompt
        tasks = UserTasks(response.task_list) if response.task_list else None

        if instructions:
            return [
                Send(
                    "edit_system_prompt",
                    {**state, "instructions": instructions, "tasks": tasks},
                )
            ]
        elif tasks:
            return [Send("filter_history", {**state, "tasks": tasks})]

        return []

    def update_active_tools(self, updated_prompt_and_tools: UpdatedPromptAndTools):
        if updated_prompt_and_tools.tools_to_activate:
            for tool in updated_prompt_and_tools.tools_to_activate:
                for (
                    validated_tool
                ) in self.retrieval_config.workflow_config.validated_tools:
                    if tool == validated_tool.name:
                        self.retrieval_config.workflow_config.activated_tools.append(
                            validated_tool
                        )

        if updated_prompt_and_tools.tools_to_deactivate:
            for tool in updated_prompt_and_tools.tools_to_deactivate:
                for (
                    activated_tool
                ) in self.retrieval_config.workflow_config.activated_tools:
                    if tool == activated_tool.name:
                        self.retrieval_config.workflow_config.activated_tools.remove(
                            activated_tool
                        )

    def edit_system_prompt(self, state: AgentState) -> AgentState:
        user_instruction = state["instructions"]
        prompt = self.retrieval_config.prompt
        available_tools, activated_tools = collect_tools(
            self.retrieval_config.workflow_config
        )
        inputs = {
            "instruction": user_instruction,
            "system_prompt": prompt if prompt else "",
            "available_tools": available_tools,
            "activated_tools": activated_tools,
        }

        msg = custom_prompts[TemplatePromptName.UPDATE_PROMPT].format(**inputs)

        response: UpdatedPromptAndTools = self.invoke_structured_output(
            msg, UpdatedPromptAndTools
        )

        self.update_active_tools(response)
        self.retrieval_config.prompt = response.prompt

        reasoning = [response.prompt_reasoning] if response.prompt_reasoning else []
        reasoning += [response.tools_reasoning] if response.tools_reasoning else []

        return {**state, "messages": [], "reasoning": reasoning}

    def filter_history(self, state: AgentState) -> AgentState:
        """
        Filter out the chat history to only include the messages that are relevant to the current question

        Takes in a chat_history= [HumanMessage(content='Qui est Chloé ? '),
        AIMessage(content="Chloé est une salariée travaillant pour l'entreprise Quivr en tant qu'AI Engineer,
        sous la direction de son supérieur hiérarchique, Stanislas Girard."),
        HumanMessage(content='Dis moi en plus sur elle'), AIMessage(content=''),
        HumanMessage(content='Dis moi en plus sur elle'),
        AIMessage(content="Désolé, je n'ai pas d'autres informations sur Chloé à partir des fichiers fournis.")]
        Returns a filtered chat_history with in priority: first max_tokens, then max_history where a Human message and an AI message count as one pair
        a token is 4 characters
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - state["chat_history"]: 当前 Brain 已经累计的多轮问答记录
        #
        # 输出:
        # - 一个被裁剪过的新 chat_history
        #
        # 在 RAG 系统里的角色:
        # - 这是“会话记忆裁剪层”
        # - 它解决的是“多轮对话上下文不能无限膨胀”的问题
        #
        # 核心理解:
        # - 不是所有历史对当前问题都有价值
        # - LLM 上下文窗口有限
        # - 所以在真正检索和生成之前，要先把历史压缩到可接受范围

        chat_history = state["chat_history"]
        total_tokens = 0
        total_pairs = 0
        _chat_id = uuid4()
        _chat_history = ChatHistory(chat_id=_chat_id, brain_id=chat_history.brain_id)
        # 从最新一轮开始倒着拿历史，优先保留最近问答。
        for human_message, ai_message in reversed(list(chat_history.iter_pairs())):
            # TODO: replace with tiktoken
            message_tokens = self.llm_endpoint.count_tokens(
                human_message.content
            ) + self.llm_endpoint.count_tokens(ai_message.content)

            # 一旦超过 token 上限或 max_history 上限，就停止继续追加更老的历史。
            if (
                total_tokens + message_tokens
                > self.retrieval_config.llm_config.max_context_tokens
                or total_pairs >= self.retrieval_config.max_history
            ):
                break
            # 只把被保留下来的历史写入新的 _chat_history。
            _chat_history.append(human_message)
            _chat_history.append(ai_message)
            total_tokens += message_tokens
            total_pairs += 1

        return {**state, "chat_history": _chat_history}

    async def rewrite(self, state: AgentState) -> AgentState:
        """
        Transform the query to produce a better question.

        Args:
            state (messages): The current state

        Returns:
            dict: The updated state with re-phrased question
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 当前任务 tasks
        # - 已裁剪过的 chat_history
        #
        # 输出:
        # - 被改写成“独立可理解问题”的 tasks
        #
        # 在 RAG 系统里的角色:
        # - 这是“问题标准化层”
        # - 它把依赖上下文的追问，改写成独立查询，提升后续检索命中率
        #
        # 例子:
        # - 用户前面问了“Chloe 是谁？”
        # - 下一句只说“再多说一点”
        # - 如果直接检索“再多说一点”，几乎没法召回
        # - 改写后会变成“再多介绍一下 Chloe”

        if "tasks" in state and state["tasks"]:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        # 每个 task 都单独发给模型改写，支持一个用户输入拆成多个任务后并行处理。
        async_jobs = []
        for task_id in tasks.ids:
            msg = custom_prompts[TemplatePromptName.CONDENSE_TASK_PROMPT].format(
                chat_history=state["chat_history"].to_list(),
                task=tasks(task_id).definition,
            )

            model = self.llm_endpoint._llm
            # Asynchronously invoke the model for each question
            async_jobs.append((model.ainvoke(msg), task_id))

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        # 用模型返回的新表述覆盖旧 task 定义。
        for response, task_id in zip(responses, task_ids, strict=False):
            tasks.set_definition(task_id, response.content)

        return {**state, "tasks": tasks}

    def filter_chunks_by_relevance(self, chunks: List[Document], **kwargs):
        config = self.retrieval_config.reranker_config
        relevance_score_threshold = kwargs.get(
            "relevance_score_threshold", config.relevance_score_threshold
        )

        if relevance_score_threshold is None:
            return chunks

        filtered_chunks = []
        for chunk in chunks:
            if config.relevance_score_key not in chunk.metadata:
                logger.warning(
                    f"Relevance score key {config.relevance_score_key} not found in metadata, cannot filter chunks by relevance"
                )
                filtered_chunks.append(chunk)
            elif (
                chunk.metadata[config.relevance_score_key] >= relevance_score_threshold
            ):
                filtered_chunks.append(chunk)

        return filtered_chunks

    async def tool_routing(self, state: AgentState):
        tasks = state["tasks"]
        if not tasks.has_tasks():
            return [Send("generate_rag", state)]

        validated_tools, _ = collect_tools(self.retrieval_config.workflow_config)

        async_jobs = []
        for task_id in tasks.ids:
            input = {
                "chat_history": state["chat_history"].to_list(),
                "tasks": tasks(task_id).definition,
                "context": combine_documents(tasks(task_id).docs),
                "activated_tools": validated_tools,
            }

            msg = custom_prompts[TemplatePromptName.TOOL_ROUTING_PROMPT].format(**input)
            async_jobs.append(
                (self.ainvoke_structured_output(msg, TasksCompletion), task_id)
            )

        responses: List[TasksCompletion] = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        for response, task_id in zip(responses, task_ids, strict=False):
            tasks.set_completion(task_id, response.is_task_completable)
            if not response.is_task_completable and response.tool:
                tasks.set_tool(task_id, response.tool)

        send_list: List[Send] = []

        payload = {**state, "tasks": tasks}

        if tasks.has_non_completable_tasks():
            send_list.append(Send("run_tool", payload))
        else:
            send_list.append(Send("generate_rag", payload))

        return send_list

    async def run_tool(self, state: AgentState) -> AgentState:
        # if tool not in [
        #     t.name for t in self.retrieval_config.workflow_config.activated_tools
        # ]:
        #     raise ValueError(f"Tool {tool} not activated")

        tasks = state["tasks"]

        # Prepare the async tasks for all questions
        async_jobs = []
        for task_id in tasks.ids:
            if not tasks(task_id).is_completable() and tasks(task_id).has_tool():
                tool = tasks(task_id).tool
                tool_wrapper = LLMToolFactory.create_tool(tool, {})
                formatted_input = tool_wrapper.format_input(tasks(task_id).definition)
                async_jobs.append((tool_wrapper.tool.ainvoke(formatted_input), task_id))

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(jobs[0] for jobs in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

        for response, task_id in zip(responses, task_ids, strict=False):
            _docs = tool_wrapper.format_output(response)
            _docs = self.filter_chunks_by_relevance(_docs)
            tasks.set_docs(task_id, _docs)

        return {**state, "tasks": tasks}

    async def retrieve(self, state: AgentState) -> AgentState:
        """
        Retrieve relevent chunks

        Args:
            state (messages): The current state

        Returns:
            dict: The retrieved chunks
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 改写后的任务 tasks
        # - vector store
        # - reranker 配置
        #
        # 输出:
        # - 每个 task 对应的一组相关 docs
        #
        # 在 RAG 系统里的角色:
        # - 这是“基础召回层”
        # - 它先从向量库取候选，再用 reranker 压缩排序
        #
        # 状态变化:
        # - 输入: task 文本
        # - 输出: 与 task 绑定的 docs
        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks.has_tasks():
            return {**state}

        _filter = state.get("_filter", None)

        # 第 1 步：先配置基础 retriever，从向量库里拿 top-k 候选。
        kwargs = {
            "search_kwargs": {
                "k": self.retrieval_config.k,
                "filter": _filter,  # Add your desired filter here
            }
        }  # type: ignore
        base_retriever = self.get_retriever(**kwargs)

        # 第 2 步：准备 reranker，对候选结果进一步压缩和排序。
        kwargs = {"top_n": self.retrieval_config.reranker_config.top_n}  # type: ignore
        reranker = self.get_reranker(**kwargs)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker, base_retriever=base_retriever
        )

        # 第 3 步：对每个 task 并行检索。
        async_jobs = []
        for task_id in tasks.ids:
            # Create a tuple of the retrieval task and task_id
            async_jobs.append(
                (compression_retriever.ainvoke(tasks(task_id).definition), task_id)
            )

        # Gather all the responses asynchronously
        responses = (
            await asyncio.gather(*(task[0] for task in async_jobs))
            if async_jobs
            else []
        )
        task_ids = [task[1] for task in async_jobs] if async_jobs else []

        # 第 4 步：把检索结果写回 task，供后面的 generate_rag 使用。
        for response, task_id in zip(responses, task_ids, strict=False):
            _docs = self.filter_chunks_by_relevance(response)
            tasks.set_docs(task_id, _docs)  # Associate docs with the specific task

        return {**state, "tasks": tasks}

    async def dynamic_retrieve(self, state: AgentState) -> AgentState:
        """
        Retrieve relevent chunks

        Args:
            state (messages): The current state

        Returns:
            dict: The retrieved chunks
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - task 文本
        # - reranker top_n / k / context token 限制
        #
        # 输出:
        # - 动态扩张后的一组 docs
        #
        # 在 RAG 系统里的角色:
        # - 这是“自适应召回层”
        # - 它不是固定 top-k，而是根据结果数量和上下文预算动态增加召回范围
        #
        # 核心理解:
        # - 普通 retrieve 是固定拿 k 个候选
        # - dynamic_retrieve 会看“目前拿到的相关 chunk 够不够”
        # - 不够就继续增大 top_n 和 k，再检索一轮

        MAX_ITERATIONS = 3

        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks or not tasks.has_tasks():
            return {**state}

        k = self.retrieval_config.k
        top_n = self.retrieval_config.reranker_config.top_n
        number_of_relevant_chunks = top_n
        i = 1

        # 只有在“当前相关 chunk 数仍然顶满 top_n”时，才说明可能还没拿够，
        # 这时继续扩大召回范围。
        while number_of_relevant_chunks == top_n and i <= MAX_ITERATIONS:
            top_n = self.retrieval_config.reranker_config.top_n * i
            kwargs = {"top_n": top_n}
            reranker = self.get_reranker(**kwargs)

            k = max([top_n * 2, self.retrieval_config.k])
            kwargs = {"search_kwargs": {"k": k}}  # type: ignore
            base_retriever = self.get_retriever(**kwargs)

            if i > 1:
                logging.info(
                    f"Increasing top_n to {top_n} and k to {k} to retrieve more relevant chunks"
                )

            compression_retriever = ContextualCompressionRetriever(
                base_compressor=reranker, base_retriever=base_retriever
            )

            # Prepare the async tasks for all questions
            async_jobs = []
            for task_id in tasks.ids:
                # Asynchronously invoke the model for each question
                async_jobs.append(
                    (compression_retriever.ainvoke(tasks(task_id).definition), task_id)
                )

            # Gather all the responses asynchronously
            responses = (
                await asyncio.gather(*(jobs[0] for jobs in async_jobs))
                if async_jobs
                else []
            )
            task_ids = [jobs[1] for jobs in async_jobs] if async_jobs else []

            _n = []
            for response, task_id in zip(responses, task_ids, strict=False):
                _docs = self.filter_chunks_by_relevance(response)
                _n.append(len(_docs))
                tasks.set_docs(task_id, _docs)

            docs = tasks.docs
            if not docs:
                break

            # 如果上下文已经接近模型上限，就算还能召回更多，也必须停下来。
            context_length = self.get_rag_context_length(state, docs)
            if context_length >= self.retrieval_config.llm_config.max_context_tokens:
                logging.warning(
                    f"The context length is {context_length} which is greater than "
                    f"the max context tokens of {self.retrieval_config.llm_config.max_context_tokens}"
                )
                break

            number_of_relevant_chunks = max(_n)
            i += 1

        return {**state, "tasks": tasks}

    def _sort_docs_by_relevance(self, docs: List[Document]) -> List[Document]:
        return sorted(
            docs,
            key=lambda x: x.metadata[
                self.retrieval_config.reranker_config.relevance_score_key
            ],
            reverse=True,
        )

    async def retrieve_full_documents_context(self, state: AgentState) -> AgentState:
        if "tasks" in state:
            tasks = state["tasks"]
        else:
            tasks = UserTasks([state["messages"][0].content])

        if not tasks.has_tasks():
            return {**state}

        docs = tasks.docs if tasks else []

        relevant_knowledge: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            knowledge_id = doc.metadata["knowledge_id"]
            similarity_score = doc.metadata.get("similarity", 0)
            if knowledge_id in relevant_knowledge:
                relevant_knowledge[knowledge_id]["count"] += 1
                relevant_knowledge[knowledge_id]["max_similarity_score"] = max(
                    relevant_knowledge[knowledge_id]["max_similarity_score"],
                    similarity_score,
                )
                relevant_knowledge[knowledge_id]["chunk_index"] = max(
                    doc.metadata["chunk_index"],
                    relevant_knowledge[knowledge_id]["chunk_index"],
                )
            else:
                relevant_knowledge[knowledge_id] = {
                    "count": 1,
                    "max_similarity_score": similarity_score,
                    "chunk_index": doc.metadata["chunk_index"],
                }

        top_n = min(3, len(relevant_knowledge))
        # FIXME: Tweak this to return the most relevant knowledges
        top_knowledge_ids = OrderedDict(
            sorted(
                relevant_knowledge.items(),
                key=lambda x: (
                    x[1]["max_similarity_score"],
                    x[1]["count"],
                ),
                reverse=True,
            )[:top_n]
        )

        logger.info(f"Top knowledge IDs: {top_knowledge_ids}")

        _docs = []

        assert hasattr(
            self.vector_store, "get_vectors_by_knowledge_id"
        ), "Vector store must have method 'get_vectors_by_knowledge_id', this is an enterprise only feature"

        for knowledge_id in top_knowledge_ids:
            _docs.append(
                await self.vector_store.get_vectors_by_knowledge_id(  # type: ignore
                    knowledge_id,
                    end_index=relevant_knowledge[knowledge_id]["chunk_index"],
                )
            )

        tasks.set_docs(
            id=tasks.ids[0], docs=_docs
        )  # FIXME If multiple IDs is not handled.

        return {**state, "tasks": tasks}

    def get_rag_context_length(self, state: AgentState, docs: List[Document]) -> int:
        final_inputs = self._build_rag_prompt_inputs(state, docs)
        msg = custom_prompts[TemplatePromptName.RAG_ANSWER_PROMPT].format(
            **final_inputs
        )
        return self.llm_endpoint.count_tokens(msg)

    def reduce_rag_context(
        self,
        state: AgentState,
        inputs: Dict[str, Any],
        prompt: BasePromptTemplate,
        max_context_tokens: int | None = None,
    ) -> Tuple[AgentState, Dict[str, Any]]:
        MAX_ITERATIONS = 20
        SECURITY_FACTOR = 0.85
        iteration = 0

        tasks = state["tasks"] if "tasks" in state else None
        docs = tasks.docs if tasks else []
        msg = prompt.format(**inputs)
        n = self.llm_endpoint.count_tokens(msg)

        max_context_tokens = (
            max_context_tokens
            if max_context_tokens
            else self.retrieval_config.llm_config.max_context_tokens
        )

        # Get token counts for each doc in each task
        if tasks:
            task_token_counts = {}
            for task_id in tasks.ids:
                doc_tokens = [
                    self.llm_endpoint.count_tokens(doc.page_content)
                    for doc in tasks(task_id).docs
                ]
                task_token_counts[task_id] = {
                    "docs": doc_tokens,
                    "total": sum(doc_tokens),
                }

        while n > max_context_tokens * SECURITY_FACTOR:
            chat_history = inputs["chat_history"] if "chat_history" in inputs else []

            if len(chat_history) > 0:
                inputs["chat_history"] = chat_history[2:]
            elif tasks:
                longest_task_id = max(
                    task_token_counts.items(), key=lambda x: x[1]["total"]
                )[0]

                # Remove last doc from that task
                if task_token_counts[longest_task_id]["docs"]:
                    removed_tokens = task_token_counts[longest_task_id]["docs"].pop()
                    task_token_counts[longest_task_id]["total"] -= removed_tokens
                    tasks.set_docs(longest_task_id, tasks(longest_task_id).docs[:-1])
            else:
                logging.warning(
                    f"Not enough context to reduce. The context length is {n} "
                    f"which is greater than the max context tokens of {max_context_tokens}"
                )
                break

            docs = tasks.docs if tasks else []
            inputs["context"] = combine_documents(docs)

            msg = prompt.format(**inputs)
            n = self.llm_endpoint.count_tokens(msg)

            iteration += 1
            if iteration > MAX_ITERATIONS:
                logging.warning(
                    f"Attained the maximum number of iterations ({MAX_ITERATIONS})"
                )
                break

        return {**state, "tasks": tasks}, inputs

    def bind_tools_to_llm(self, node_name: str):
        if self.llm_endpoint.supports_func_calling():
            tools = self.retrieval_config.workflow_config.get_node_tools(node_name)
            if tools:  # Only bind tools if there are any available
                return self.llm_endpoint._llm.bind_tools(tools, tool_choice="any")
        return self.llm_endpoint._llm

    def generate_zendesk_rag(self, state: AgentState) -> AgentState:
        tasks = state["tasks"]
        docs: List[Document] = tasks.docs if tasks else []
        messages = state["messages"]
        user_task = messages[0].content
        prompt_template: BasePromptTemplate = custom_prompts[
            TemplatePromptName.ZENDESK_TEMPLATE_PROMPT
        ]

        ticket_metadata = state["ticket_metadata"] or {}
        user_metadata = state["user_metadata"] or {}
        ticket_history = state.get("ticket_history", "")
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inputs = {
            "similar_tickets": "\n".join([doc.page_content for doc in docs]),
            "ticket_metadata": format_dict(ticket_metadata),
            "user_metadata": format_dict(user_metadata),
            "client_query": user_task,
            "ticket_history": ticket_history,
            "current_time": current_time,
        }
        required_variables = prompt_template.input_variables
        for variable in required_variables:
            if variable not in inputs:
                inputs[variable] = state.get(variable, "")

        msg = prompt_template.format_prompt(**inputs)
        llm = self.bind_tools_to_llm(self.generate_zendesk_rag.__name__)

        response = llm.invoke(msg)

        return {**state, "messages": [response]}

    def generate_rag(self, state: AgentState) -> AgentState:
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 当前任务 tasks
        # - 检索得到的 docs
        # - chat_history
        # - prompt 配置
        #
        # 输出:
        # - state["messages"] 中的最终模型回答
        #
        # 在 RAG 系统里的角色:
        # - 这是“答案生成层”
        # - 前面的工作都是在为这里准备足够好的上下文
        tasks = state["tasks"]
        docs = tasks.docs if tasks else []
        # 把 docs、task、history、custom prompt 等组装成最终 prompt 输入。
        inputs = self._build_rag_prompt_inputs(state, docs)
        prompt = custom_prompts[TemplatePromptName.RAG_ANSWER_PROMPT]
        # 如果上下文太长，这里会裁剪 docs/history，保证不超过模型限制。
        state, inputs = self.reduce_rag_context(state, inputs, prompt)
        msg = prompt.format(**inputs)
        # 某些场景下这里还会把工具绑定到 LLM 上。
        llm = self.bind_tools_to_llm(self.generate_rag.__name__)
        response = llm.invoke(msg)

        return {**state, "messages": [response]}

    def generate_chat_llm(self, state: AgentState) -> AgentState:
        """
        Generate answer

        Args:
            state (messages): The current state

        Returns:
            dict: The updated state with re-phrased question
        """
        messages = state["messages"]

        # Check if there is a system message in messages
        system_message = None
        user_message = None

        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_message = str(msg.content)
            elif isinstance(msg, HumanMessage):
                user_message = str(msg.content)

        user_task = (
            user_message if user_message else (messages[0].content if messages else "")
        )

        # Prompt
        prompt = self.retrieval_config.prompt

        final_inputs = {}
        final_inputs["task"] = user_task
        final_inputs["custom_instructions"] = prompt if prompt else "None"
        final_inputs["chat_history"] = state["chat_history"].to_list()

        # LLM
        llm = self.llm_endpoint._llm

        prompt = custom_prompts[TemplatePromptName.CHAT_LLM_PROMPT]
        state, reduced_inputs = self.reduce_rag_context(
            state, final_inputs, system_message if system_message else prompt
        )
        CHAT_LLM_PROMPT = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=str(system_message)),
                MessagesPlaceholder(variable_name="chat_history"),
                HumanMessage(content=str(user_message)),
            ]
        )
        # Run
        chat_llm_prompt = CHAT_LLM_PROMPT.invoke(
            {"chat_history": final_inputs["chat_history"]}
        )
        response = llm.invoke(chat_llm_prompt)
        return {**state, "messages": [response]}

    def build_chain(self):
        """
        Builds the langchain chain for the given configuration.

        Returns:
            Callable[[Dict], Dict]: The langchain chain.
        """
        if not self.graph:
            self.graph = self.create_graph()

        return self.graph

    def create_graph(self):
        # 这是“工作流组装层”。
        # 它把 retrieval_config.workflow_config 里的节点定义真正编译成 LangGraph 状态图。
        #
        # 你可以把它理解成:
        # - YAML / config 只是描述流程
        # - create_graph() 才是把描述变成可运行工作流
        workflow = StateGraph(AgentState)
        self.final_nodes = []

        self._build_workflow(workflow)

        return workflow.compile()

    def _build_workflow(self, workflow: StateGraph):
        for node in self.retrieval_config.workflow_config.nodes:
            if node.name not in [START, END]:
                workflow.add_node(node.name, getattr(self, node.name))

        for node in self.retrieval_config.workflow_config.nodes:
            self._add_node_edges(workflow, node)

    def _add_node_edges(self, workflow: StateGraph, node: NodeConfig):
        if node.edges:
            for edge in node.edges:
                workflow.add_edge(node.name, edge)
                if edge == END:
                    self.final_nodes.append(node.name)
        elif node.conditional_edge:
            routing_function = getattr(self, node.conditional_edge.routing_function)
            workflow.add_conditional_edges(
                node.name, routing_function, node.conditional_edge.conditions
            )
            if END in node.conditional_edge.conditions:
                self.final_nodes.append(node.name)
        else:
            raise ValueError("Node should have at least one edge or conditional_edge")

    async def answer_astream(
        self,
        run_id: UUID,
        question: str,
        system_prompt: str | None,
        history: ChatHistory,
        list_files: list[QuivrKnowledge],
        metadata: LangchainMetadata | None = None,
        **input_kwargs,
    ) -> AsyncGenerator[ParsedRAGChunkResponse, ParsedRAGChunkResponse]:
        """
        Answer a question using the langgraph chain and yield each chunk of the answer separately.
        """
        # =========================
        # 这段函数的教学视角
        # =========================
        # 输入:
        # - 用户问题 question
        # - history / list_files / metadata
        #
        # 输出:
        # - 一个持续产出 ParsedRAGChunkResponse 的异步流
        #
        # 在 RAG 系统里的角色:
        # - 这是“工作流执行层 + 流式输出层”
        # - 它真正启动 LangGraph，并把中间节点状态和最终回答流出来
        #
        # 你可以把它看成 4 个阶段:
        # 1. 准备输入 state
        # 2. 编译或复用 graph
        # 3. 消费 LangGraph 的事件流
        # 4. 把事件转换成前端/上层可消费的 chunk
        concat_list_files = format_file_list(
            list_files, self.retrieval_config.max_files
        )
        # build_chain() 内部如果 graph 还没创建，就会触发 create_graph()。
        conversational_qa_chain = self.build_chain()

        rolling_message = AIMessageChunk(content="")
        docs: list[Document] | None = None
        previous_content = ""
        system_prompt = system_prompt
        # 这里把外部 question 和 system_prompt 组装成工作流入口消息。
        messages = [("system", system_prompt)] if system_prompt else []
        messages.append(("user", question))

        # astream_events(...) 会流出整个 LangGraph 的事件，而不只是最终答案。
        # 所以这里既能看到工作流节点切换，也能看到最后的 token/chunk 流。
        async for event in conversational_qa_chain.astream_events(
            {
                "messages": messages,
                "chat_history": history,
                "files": concat_list_files,
                **input_kwargs,
            },
            version="v1",
            config={
                "run_id": run_id,
                "metadata": metadata.model_dump() if metadata else {},
                "callbacks": [langfuse_handler],
            },
        ):
            node_name = self._extract_node_name(event)

            # 如果当前事件来自最终生成节点，并且带了 tasks/docs，就把 docs 取出来，
            # 后面生成 metadata / citations 时要用到。
            if self._is_final_node_with_docs(event):
                tasks = event["data"]["output"]["tasks"]
                docs = tasks.docs if tasks else []

            # 如果当前事件是最终节点的模型流式输出，就解析成 answer chunk。
            if self._is_final_node_and_chat_model_stream(event):
                chunk = event["data"]["chunk"]
                rolling_message, new_content, previous_content = parse_chunk_response(
                    rolling_message,
                    chunk,
                    self.llm_endpoint.supports_func_calling(),
                    previous_content,
                )

                if new_content:
                    chunk_metadata = get_chunk_metadata(rolling_message, docs)
                    if node_name:
                        chunk_metadata.workflow_step = node_name
                    yield ParsedRAGChunkResponse(
                        answer=new_content, metadata=chunk_metadata
                    )
            else:
                # 对非最终 token 流事件，这里主要把“当前工作流走到了哪个节点”抛出去。
                # 对理解执行过程和前端展示中间状态很有帮助。
                if node_name:
                    yield ParsedRAGChunkResponse(
                        answer="",
                        metadata=RAGResponseMetadata(workflow_step=node_name),
                    )

        # 最后补一个 metadata-only chunk，告诉上层“本轮流式输出已经结束”。
        chunk_metadata = get_chunk_metadata(rolling_message, docs)
        if metadata:
            chunk_metadata.langchain_metadata = metadata
            chunk_metadata.langchain_metadata.langfuse_trace_url = (
                langfuse_handler.get_trace_url()
            )

        yield ParsedRAGChunkResponse(
            answer="",
            metadata=chunk_metadata,
            last_chunk=True,
        )

    def _is_final_node_with_docs(self, event: StreamEvent) -> bool:
        return (
            "output" in event["data"]
            and event["data"]["output"] is not None
            and "tasks" in event["data"]["output"]
            and event["metadata"]["langgraph_node"] in self.final_nodes
        )

    def _is_final_node_and_chat_model_stream(self, event: StreamEvent) -> bool:
        return (
            event["event"] == "on_chat_model_stream"
            and "langgraph_node" in event["metadata"]
            and event["metadata"]["langgraph_node"] in self.final_nodes
        )

    def _extract_node_name(self, event: StreamEvent) -> str:
        if "metadata" in event and "langgraph_node" in event["metadata"]:
            name = event["metadata"]["langgraph_node"]
            for node in self.retrieval_config.workflow_config.nodes:
                if node.name == name:
                    if node.description:
                        return node.description
                    else:
                        return node.name
        return ""

    async def ainvoke_structured_output(
        self, prompt: str, output_class: Type[BaseModel]
    ) -> Any:
        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                output_class, method="json_schema"
            )
            return await structured_llm.ainvoke(prompt)
        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(output_class)
            return await structured_llm.ainvoke(prompt)

    def invoke_structured_output(
        self, prompt: str, output_class: Type[BaseModel]
    ) -> Any:
        try:
            structured_llm = self.llm_endpoint._llm.with_structured_output(
                output_class, method="json_schema"
            )
            return structured_llm.invoke(prompt)
        except openai.BadRequestError:
            structured_llm = self.llm_endpoint._llm.with_structured_output(output_class)
            return structured_llm.invoke(prompt)

    def _build_rag_prompt_inputs(
        self, state: AgentState, docs: List[Document] | None
    ) -> Dict[str, Any]:
        """Build the input dictionary for RAG_ANSWER_PROMPT.

        Args:
            state: Current agent state
            docs: List of documents or None

        Returns:
            Dictionary containing all inputs needed for RAG_ANSWER_PROMPT
        """
        messages = state["messages"]
        user_task = messages[0].content
        files = state["files"]
        prompt = self.retrieval_config.prompt
        # available_tools, _ = collect_tools(self.retrieval_config.workflow_config)

        return {
            "context": combine_documents(docs) if docs else "None",
            "task": user_task,
            "rephrased_task": state["tasks"].definitions if state["tasks"] else "None",
            "custom_instructions": prompt if prompt else "None",
            "files": files if files else "None",
            "chat_history": state["chat_history"].to_list(),
            # "reasoning": state["reasoning"] if "reasoning" in state else "None",
            # "tools": available_tools,
        }
