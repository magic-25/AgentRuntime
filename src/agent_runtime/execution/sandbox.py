from __future__ import annotations

from dataclasses import dataclass, field

from agent_runtime.execution.base import ProcessResult


class SandboxUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxCommandSpec:
    argv: list[str]
    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    env_allowlist: list[str] = field(default_factory=list)
    timeout_ms: int = 30000
    stdout_limit_bytes: int = 65536
    stderr_limit_bytes: int = 65536
    isolation_level: str = "strong"
    network_access: bool = False
    read_paths: list[str] = field(default_factory=list)
    write_paths: list[str] = field(default_factory=list)


class SandboxExecutor:
    backend_name = "sandbox"
    available = True

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        raise NotImplementedError


class UnavailableSandboxExecutor(SandboxExecutor):
    backend_name = "unavailable"
    available = False

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        raise SandboxUnavailableError("strong sandbox backend is unavailable")
