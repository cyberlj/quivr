from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quivr_core.auto_harness.contracts import AgentManifest, RoundState
from quivr_core.auto_harness.state_store import StateStore


@dataclass(frozen=True)
class LaunchResult:
    manifest: AgentManifest
    manifest_path: Path
    environment: dict[str, str]


class ExecutionLauncher:
    def __init__(self, repo_root: str | Path, state_store: StateStore):
        self.repo_root = Path(repo_root)
        self.state_store = state_store

    def launch_worker(
        self,
        round_state: RoundState,
        allowed_commands_override: list[str] | None = None,
    ) -> LaunchResult:
        return self._launch_execution_agent(
            round_state=round_state,
            agent_id="worker-1",
            role="Worker",
            forbidden_actions=["keep", "reset", "edit_runtime_state"],
            allowed_commands=allowed_commands_override
            or [
                f"core/scripts/auto_harness/execute_guard.sh worker --round-id {round_state.round_id} --agent-id worker-1"
            ],
            single_writer=True,
        )

    def launch_verifier(
        self,
        round_state: RoundState,
        allowed_commands_override: list[str] | None = None,
    ) -> LaunchResult:
        return self._launch_execution_agent(
            round_state=round_state,
            agent_id="verifier-1",
            role="Verifier",
            forbidden_actions=["edit_code", "keep", "reset", "edit_runtime_state"],
            allowed_commands=allowed_commands_override
            or [
                f"core/scripts/auto_harness/execute_guard.sh verifier --round-id {round_state.round_id} --agent-id verifier-1"
            ],
            single_writer=False,
        )

    def _launch_execution_agent(
        self,
        round_state: RoundState,
        agent_id: str,
        role: str,
        forbidden_actions: list[str],
        allowed_commands: list[str],
        single_writer: bool,
    ) -> LaunchResult:
        if round_state.execution_worktree is None:
            raise ValueError("execution worktree must be set before launching execution agents")

        manifest_path = self.state_store.agent_manifest_path(round_state.round_id, agent_id)
        if single_writer and manifest_path.exists():
            raise ValueError(f"worker manifest already exists for round {round_state.round_id}")

        self._validate_allowed_commands(allowed_commands)

        manifest = AgentManifest(
            round_id=round_state.round_id,
            agent_id=agent_id,
            role=role,
            worktree=round_state.execution_worktree,
            allowed_files=round_state.allowed_files,
            forbidden_actions=forbidden_actions,
            allowed_commands=allowed_commands,
        )
        written_path = self.state_store.write_agent_manifest(manifest)
        environment = {
            "ROUND_ID": round_state.round_id,
            "AGENT_ID": agent_id,
            "AGENT_ROLE": role,
            "AGENT_MANIFEST_PATH": str(written_path),
            "WORKTREE_PATH": str(round_state.execution_worktree),
        }
        return LaunchResult(
            manifest=manifest,
            manifest_path=written_path,
            environment=environment,
        )

    def _validate_allowed_commands(self, allowed_commands: list[str]) -> None:
        for command in allowed_commands:
            if not command.startswith("core/scripts/auto_harness/"):
                raise ValueError(f"execution command must use repo-local wrapper entrypoints: {command}")
            if ".sh " not in f"{command} ":
                raise ValueError(f"execution command must target a shell wrapper: {command}")
