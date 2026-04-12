from pathlib import Path

import pytest

from quivr_core.auto_harness.harness_docs_lint import lint_docs


def write_docs(root: Path) -> Path:
    docs_root = root / "docs" / "auto-harness"
    docs_root.mkdir(parents=True, exist_ok=True)
    (docs_root / "phase1-mvp-design.md").write_text(
        "\n".join(
            [
                "Recorder 不能改 `runtime-state.json`",
                "Verifier 不能改业务代码",
                "产出结构化 API summary payload，由 Recorder 落盘",
                "Recorder 落盘 structured logs",
                "review 为 `revise` 或 `reject` 时优先回到 re-plan",
                "├── plan.md",
                "├── plan-review.md",
                "├── verify.md",
                "├── decision.md",
                "├── reflection.md",
                "├── artifacts.json",
                "└── summary.md",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs_root / "agent-contract.md").write_text(
        "\n".join(
            [
                "- `runtime-state.md` -> Conductor",
                "- benchmark and validation output -> Verifier",
                "- `event-log.jsonl` -> Recorder",
                "- `tool-log.jsonl` -> Recorder",
                "- `api-log.jsonl` -> Recorder",
                "Recorder does not own `runtime-state.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs_root / "planning-model.md").write_text(
        "\n".join(
            [
                "Allowed review outcomes:",
                "- `approved`",
                "- `revise`",
                "- `reject`",
                "Only `approved` may unlock execution.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (docs_root / "phase1-mvp-implementation-plan.md").write_text(
        "\n".join(
            [
                "approved review is required before execution",
                "- `revise` does not unlock execution",
                "- `review_outcome=reject` triggers re-plan",
                "docs/auto-harness/rounds/<round_id>/plan.md",
                "docs/auto-harness/rounds/<round_id>/plan-review.md",
                "docs/auto-harness/rounds/<round_id>/verify.md",
                "docs/auto-harness/rounds/<round_id>/decision.md",
                "docs/auto-harness/rounds/<round_id>/reflection.md",
                "docs/auto-harness/rounds/<round_id>/artifacts.json",
                "docs/auto-harness/rounds/<round_id>/summary.md",
                "Keep durable write ownership out of verifier:",
                "- do not append `tool-log.jsonl`",
                "- do not append `api-log.jsonl`",
                "Controller does not directly append:",
                "- `event-log.jsonl`",
                "- `tool-log.jsonl`",
                "- `api-log.jsonl`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return docs_root


def test_mismatched_ownership_fails(tmp_path):
    docs_root = write_docs(tmp_path)
    (docs_root / "agent-contract.md").write_text(
        (docs_root / "agent-contract.md").read_text(encoding="utf-8").replace(
            "- `runtime-state.md` -> Conductor",
            "- `runtime-state.md` -> Recorder",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lint_docs(docs_root)


def test_mismatched_archive_layout_fails(tmp_path):
    docs_root = write_docs(tmp_path)
    (docs_root / "phase1-mvp-implementation-plan.md").write_text(
        (docs_root / "phase1-mvp-implementation-plan.md").read_text(encoding="utf-8").replace(
            "docs/auto-harness/rounds/<round_id>/summary.md\n",
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lint_docs(docs_root)


def test_mismatched_review_state_semantics_fail(tmp_path):
    docs_root = write_docs(tmp_path)
    (docs_root / "planning-model.md").write_text(
        (docs_root / "planning-model.md").read_text(encoding="utf-8").replace(
            "- `revise`\n",
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        lint_docs(docs_root)


def test_valid_docs_pass(tmp_path):
    docs_root = write_docs(tmp_path)

    lint_docs(docs_root)
