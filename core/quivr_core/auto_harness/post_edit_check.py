from __future__ import annotations

import argparse
import importlib.util
import py_compile
import sys
from pathlib import Path

from quivr_core.auto_harness.contracts import AgentManifest, RoundState


def _validate_changed_file(manifest: AgentManifest, changed_file: Path) -> None:
    try:
        relative_path = changed_file.relative_to(manifest.worktree).as_posix()
    except ValueError as exc:
        raise ValueError(f"changed file is outside worktree: {changed_file}") from exc

    if relative_path not in manifest.allowed_files:
        raise ValueError(f"changed file is outside allowed_files: {relative_path}")


def _import_smoke(changed_file: Path) -> None:
    module_name = f"auto_harness_post_edit_{changed_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, changed_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load module spec for {changed_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def run_post_edit_check(
    manifest_path: Path,
    round_state_path: Path,
    changed_files: list[Path],
) -> None:
    manifest = AgentManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    RoundState.model_validate_json(round_state_path.read_text(encoding="utf-8"))

    for changed_file in changed_files:
        _validate_changed_file(manifest, changed_file)
        try:
            py_compile.compile(str(changed_file), doraise=True)
        except py_compile.PyCompileError as exc:
            raise ValueError(f"py_compile failed for {changed_file}: {exc.msg}") from exc
        _import_smoke(changed_file)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-path", required=True, type=Path)
    parser.add_argument("--round-state-path", required=True, type=Path)
    parser.add_argument("--changed-file", action="append", default=[], type=Path)
    args = parser.parse_args()

    try:
        run_post_edit_check(
            manifest_path=args.manifest_path,
            round_state_path=args.round_state_path,
            changed_files=args.changed_file,
        )
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    print("post-edit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
