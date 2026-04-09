import argparse
import asyncio
import os
import tempfile
from uuid import uuid4

# 在导入 quivr_core 之前先补上最小环境变量，
# 避免配置对象初始化时反复打印缺少 OPENAI_API_KEY 的告警。
os.environ.setdefault("OPENAI_API_KEY", "debug-key")

from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import FakeListChatModel

from quivr_core.brain import Brain
from quivr_core.files.file import FileExtension
from quivr_core.language.models import Language
from quivr_core.llm import LLMEndpoint
from quivr_core.processor import processor_base
from quivr_core.processor.implementations.simple_txt_processor import SimpleTxtProcessor
from quivr_core.processor.registry import register_processor
from quivr_core.rag.entities.config import LLMEndpointConfig


def build_fake_llm() -> LLMEndpoint:
    responses = [
        "Gold is described in the document as a liquid of blue-like colour.",
        "Gold est decrit dans le document comme un liquide de couleur bleuatre.",
        "The document says gold is a liquid of blue-like colour.",
    ]
    # FakeListChatModel是一个子类，它本质还是Python的dataclass风格定义，没有自定义__init__方法。
    # 但因为它继承自langchain_core里SimpleChatModel（进一步是BaseModel），
    # 所以它可以通过关键字参数直接注入responses等字段，自动完成对应属性赋值。
    # 这样responses参数其实底层通过dataclasses/pydantic提供的默认构造器注入进去了。
    llm = FakeListChatModel(responses=responses)
    # FakeListChatModel 是 langchain-core 提供的测试专用模型（fake/模拟）——它不会连任何真实大模型，只是返回预设的字符串，方便本地调试/单元测试用。
    # 这里 model="fake_model" 也是占位，和真实模型名（如 gpt-4o、qwen、claude-3 等）没任何实际推理功能绑定。
    # 所以这类 fake_model/FakeListChatModel 配合用法，属于 mock 测试场景，完全离线可跑，无需环境变量、API Key 或联网依赖。
    return LLMEndpoint(llm=llm, llm_config=LLMEndpointConfig(model="fake_model"))


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimal debug entry for stepping through Brain build and ask flows."
    )
    # 这几行代码通过 parser.add_argument 方法依次注册了 --mode、--text 和 --question 三个命令行参数：
    # 1. --mode：控制程序运行模式，是用来“只建库”还是“建库并提问”。实际影响后面主流程是仅执行建库（build），还是建库+问答（ask）。默认值 'build'。
    # 2. --text：指定写入临时 txt 文件的字符串内容。方便调试时自定义 ingest 内容，无需手动编辑文件。默认文本为 "Gold is a liquid of blue-like colour."。
    # 3. --question：调试提问时实际送入 RAG 系统的英文问题。便于灵活切换不同问句验证效果。默认问题是 "what is gold? answer in french"。
    # 这些参数让 debug_brain_entry.py 脚本既可以一键复现固定流程，也支持命令行动态替换测试内容和交互模式，便于开发者在不同输入/问题下快速定位和复查核心逻辑。
    parser.add_argument(
        "--mode",
        choices=["build", "ask"],
        default="build",
        help="`build` only builds the Brain; `ask` builds and then runs a question.",
    )
    parser.add_argument(
        "--text",
        default="Gold is a liquid of blue-like colour.",
        help="Text written into a temporary .txt file that will be ingested.",
    )
    parser.add_argument(
        "--question",
        default="what is gold? answer in french",
        help="Question used when --mode ask is selected.",
    )
    args = parser.parse_args()

    embedder = DeterministicFakeEmbedding(size=20)
    llm = build_fake_llm()

    # 调试脚本固定把 .txt 路径切到离线可跑的 SimpleTxtProcessor。
    # 这样可以避开默认 TikTokenTxtProcessor 在当前环境下触发的联网分词器下载。
    register_processor(FileExtension.txt, SimpleTxtProcessor, override=True)

    # 调试脚本固定绕开在线语言检测模型下载。
    # 这里不影响主流程理解，因为我们当前调试目标是看文件登记、解析、建库和问答接线。
    processor_base.detect_language = lambda text, low_memory=True: Language.EN

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=True) as temp_file:
        temp_file.write(args.text)
        temp_file.flush()

        print(f"[debug] temp file: {temp_file.name}")
        print(f"[debug] mode: {args.mode}")

        brain = await Brain.afrom_files(
            name="debug_brain",
            file_paths=[temp_file.name],
            llm=llm,
            embedder=embedder,
        )

        print(f"[debug] brain created: {brain.name}")
        print(f"[debug] files in storage: {len(await brain.storage.get_files())}")

        if args.mode == "build":
            print("[debug] build mode complete")
            return

        response = await brain.aask(
            run_id=uuid4(),
            question=args.question,
        )
        print("[debug] final answer:")
        print(response.answer)


if __name__ == "__main__":
    asyncio.run(main())
