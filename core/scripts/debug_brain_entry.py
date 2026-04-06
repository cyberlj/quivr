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
    llm = FakeListChatModel(responses=responses)
    return LLMEndpoint(llm=llm, llm_config=LLMEndpointConfig(model="fake_model"))


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Minimal debug entry for stepping through Brain build and ask flows."
    )
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
