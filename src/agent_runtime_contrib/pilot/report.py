from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PilotReport:
    repo_path: str
    status: str
    dirty_workspace_status: str
    allowed_commands: list[list[str]]
    executed_commands: list[list[str]] = field(default_factory=list)
    write_scope: str | None = None
    network_access: bool = False
    credential_paths_denied: bool = True
    commit_push_pr_denied: bool = True
    diff_summary: str = ""
    audit_mode: str = "digest-only"
    audit_verify_status: str = "not_run"
    retention: str = "local"
    limitations: list[str] = field(default_factory=lambda: ["reference pilot", "no commit/push/PR"])
    error: str | None = None
    schema_version: int = 1
    support_level: str = "preview"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> None:
        import json

        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
