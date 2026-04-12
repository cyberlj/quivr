from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def _base_url_label(base_url: str) -> str:
    return urlparse(base_url).netloc or "unknown"


def run_shadow_e2e(
    worktree: str | Path,
    env: dict[str, str],
    fake_result: dict | None = None,
) -> dict:
    _ = Path(worktree)
    api_key = env.get("OPENAI_API_KEY")
    base_url = env.get("OPENAI_BASE_URL")
    model_name = env.get("OPENAI_MODEL")

    if not api_key or not base_url or not model_name:
        return {
            "model_name": model_name or "unknown",
            "base_url_label": _base_url_label(base_url or ""),
            "shadow_status": "skipped_env_missing",
            "shadow_full_session_ms": None,
            "api_event_id": None,
            "api_summary_payload": None,
        }

    result = {
        "model_name": model_name,
        "base_url_label": _base_url_label(base_url),
        "shadow_status": "needs_execution",
        "shadow_full_session_ms": None,
        "api_event_id": None,
        "api_summary_payload": None,
    }
    if fake_result:
        result.update(fake_result)

    if result["shadow_status"] == "success" and not result.get("api_event_id"):
        raise ValueError("shadow_status=success requires api_event_id")

    if result.get("api_event_id"):
        result["api_summary_payload"] = {
            "event_id": result["api_event_id"],
            "model_name": model_name,
            "base_url_label": _base_url_label(base_url),
        }

    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", required=True, type=Path)
    parser.add_argument("--openai-api-key")
    parser.add_argument("--openai-base-url")
    parser.add_argument("--openai-model")
    args = parser.parse_args()

    result = run_shadow_e2e(
        worktree=args.worktree,
        env={
            "OPENAI_API_KEY": args.openai_api_key or "",
            "OPENAI_BASE_URL": args.openai_base_url or "",
            "OPENAI_MODEL": args.openai_model or "",
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["shadow_status"] != "failure" else 1


if __name__ == "__main__":
    raise SystemExit(main())
