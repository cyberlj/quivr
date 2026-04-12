from __future__ import annotations

import argparse
from pathlib import Path


REVIEW_OUTCOMES = {"approved", "revise", "reject"}
ARCHIVE_FILES = {
    "plan.md",
    "plan-review.md",
    "verify.md",
    "decision.md",
    "reflection.md",
    "artifacts.json",
    "summary.md",
}


def lint_docs(docs_root: str | Path) -> None:
    docs_root = Path(docs_root)
    design = (docs_root / "phase1-mvp-design.md").read_text(encoding="utf-8")
    contract = (docs_root / "agent-contract.md").read_text(encoding="utf-8")
    planning = (docs_root / "planning-model.md").read_text(encoding="utf-8")
    implementation = (docs_root / "phase1-mvp-implementation-plan.md").read_text(encoding="utf-8")

    _check_ownership_consistency(design, contract)
    _check_review_outcomes(planning, implementation)
    _check_archive_layout(design, implementation)
    _check_write_boundaries(design, contract, implementation)


def _check_ownership_consistency(design: str, contract: str) -> None:
    required_contract_lines = [
        "- `runtime-state.md` -> Conductor",
        "- benchmark and validation output -> Verifier",
        "- `event-log.jsonl` -> Recorder",
        "- `tool-log.jsonl` -> Recorder",
        "- `api-log.jsonl` -> Recorder",
        "Recorder does not own `runtime-state.md`",
    ]
    required_design_lines = [
        "Recorder 不能改 `runtime-state.json`",
        "Verifier 不能改业务代码",
    ]
    if any(line not in contract for line in required_contract_lines):
        raise ValueError("ownership consistency failed")
    if any(line not in design for line in required_design_lines):
        raise ValueError("ownership consistency failed")


def _check_review_outcomes(planning: str, implementation: str) -> None:
    planning_outcomes = {outcome for outcome in REVIEW_OUTCOMES if f"`{outcome}`" in planning}
    implementation_outcomes = {outcome for outcome in REVIEW_OUTCOMES if outcome in implementation}
    if planning_outcomes != REVIEW_OUTCOMES:
        raise ValueError("review outcome semantics failed")
    if implementation_outcomes != REVIEW_OUTCOMES:
        raise ValueError("review outcome semantics failed")
    if "Only `approved` may unlock execution." not in planning:
        raise ValueError("review outcome semantics failed")
    if "`revise` does not unlock execution" not in implementation:
        raise ValueError("review outcome semantics failed")


def _check_archive_layout(design: str, implementation: str) -> None:
    for archive_file in ARCHIVE_FILES:
        if archive_file not in design or archive_file not in implementation:
            raise ValueError("round archive layout failed")


def _check_write_boundaries(design: str, contract: str, implementation: str) -> None:
    required_design_lines = [
        "产出结构化 API summary payload，由 Recorder 落盘",
        "Recorder 落盘 structured logs",
    ]
    required_contract_lines = [
        "- `event-log.jsonl` -> Recorder",
        "- `tool-log.jsonl` -> Recorder",
        "- `api-log.jsonl` -> Recorder",
    ]
    required_implementation_lines = [
        "Keep durable write ownership out of verifier:",
        "Controller does not directly append:",
        "- `event-log.jsonl`",
        "- `tool-log.jsonl`",
        "- `api-log.jsonl`",
        "- do not append `tool-log.jsonl`",
        "- do not append `api-log.jsonl`",
    ]
    if any(line not in design for line in required_design_lines):
        raise ValueError("write boundary consistency failed")
    if any(line not in contract for line in required_contract_lines):
        raise ValueError("write boundary consistency failed")
    if any(line not in implementation for line in required_implementation_lines):
        raise ValueError("write boundary consistency failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docs-root",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "docs" / "auto-harness",
    )
    args = parser.parse_args()
    lint_docs(args.docs_root)
    print("docs lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
