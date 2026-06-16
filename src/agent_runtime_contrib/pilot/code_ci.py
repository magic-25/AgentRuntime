from __future__ import annotations

import subprocess
from pathlib import Path

from agent_runtime_contrib.pilot.report import PilotReport


DENIED_GIT_ACTIONS = {"commit", "push", "pull-request", "pr"}


class CodeCIPilot:
    def __init__(self, allowed_commands: list[list[str]]) -> None:
        self.allowed_commands = [list(command) for command in allowed_commands]

    def run(
        self,
        repo_path: str | Path,
        command: list[str],
        write_scope: str | Path,
        report_path: str | Path | None = None,
    ) -> PilotReport:
        repo = Path(repo_path)
        normalized_command = list(command)
        base = self._base_report(repo, write_scope)

        denied_error = self._denied_command_error(normalized_command)
        if denied_error is not None:
            return self._finalize(
                PilotReport(**{**base, "status": "denied", "error": denied_error}),
                report_path,
            )

        if normalized_command not in self.allowed_commands:
            return self._finalize(
                PilotReport(**{**base, "status": "denied", "error": "command.not_allowlisted"}),
                report_path,
            )

        dirty_status = self._dirty_workspace_status(repo)
        if dirty_status == "dirty":
            return self._finalize(
                PilotReport(
                    **{
                        **base,
                        "status": "aborted",
                        "dirty_workspace_status": dirty_status,
                        "error": "dirty_workspace",
                    }
                ),
                report_path,
            )

        completed = subprocess.run(normalized_command, cwd=repo, check=False, capture_output=True, text=True)
        status = "success" if completed.returncode == 0 else "error"
        return self._finalize(
            PilotReport(
                **{
                    **base,
                    "status": status,
                    "dirty_workspace_status": dirty_status,
                    "executed_commands": [normalized_command],
                    "diff_summary": completed.stdout.strip(),
                    "error": None if status == "success" else "command.failed",
                }
            ),
            report_path,
        )

    def _base_report(self, repo: Path, write_scope: str | Path) -> dict[str, object]:
        return {
            "repo_path": str(repo),
            "dirty_workspace_status": "clean",
            "allowed_commands": self.allowed_commands,
            "write_scope": str(write_scope),
        }

    def _denied_command_error(self, command: list[str]) -> str | None:
        if not command:
            return "command.empty"
        if command[0] == "git" and len(command) > 1 and command[1] in DENIED_GIT_ACTIONS:
            return "command.denied"
        if command[0] == "gh" and len(command) > 1 and command[1] in {"pr"}:
            return "command.denied"
        return None

    def _dirty_workspace_status(self, repo: Path) -> str:
        if not (repo / ".git").exists():
            return "clean"
        result = subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=False, capture_output=True, text=True)
        return "dirty" if result.stdout.strip() else "clean"

    def _finalize(self, report: PilotReport, report_path: str | Path | None) -> PilotReport:
        if report_path is not None:
            report.write_json(report_path)
        return report
