from __future__ import annotations

import os
import subprocess
from pathlib import Path

from agent_runtime.execution.base import ProcessResult


class SubprocessExecutor:
    def execute(
        self,
        argv: list[str],
        cwd: str | Path,
        env: dict[str, str] | None = None,
        env_allowlist: list[str] | None = None,
        timeout_ms: int = 30000,
        stdout_limit_bytes: int = 65536,
        stderr_limit_bytes: int = 65536,
    ) -> ProcessResult:
        allowed_env = self._allowed_env(env or {}, env_allowlist or [])
        completed = subprocess.run(
            argv,
            cwd=Path(cwd),
            env=allowed_env,
            text=True,
            capture_output=True,
            timeout=timeout_ms / 1000,
            check=False,
        )
        return ProcessResult(
            exit_code=completed.returncode,
            stdout=_truncate(completed.stdout, stdout_limit_bytes),
            stderr=_truncate(completed.stderr, stderr_limit_bytes),
        )

    def _allowed_env(self, env: dict[str, str], env_allowlist: list[str]) -> dict[str, str]:
        base = {"PATH": os.environ.get("PATH", "")}
        for key in env_allowlist:
            if key in env:
                base[key] = env[key]
        return base


def _truncate(value: str, limit_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return value
    return encoded[:limit_bytes].decode("utf-8", errors="ignore")
