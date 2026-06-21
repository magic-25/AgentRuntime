from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_runtime.execution.base import ProcessResult


class SandboxUnavailableError(RuntimeError):
    pass


class SandboxViolationError(ValueError):
    pass


@dataclass(frozen=True)
class SandboxResourceLimits:
    cpu_count: int = 1
    memory_mb: int = 512
    process_limit: int = 64


@dataclass(frozen=True)
class SandboxExecutionPlan:
    argv: list[str]
    cwd: Path
    env: dict[str, str]
    read_mounts: list[Path]
    write_mounts: list[Path]
    network_access: bool
    timeout_ms: int
    stdout_limit_bytes: int
    stderr_limit_bytes: int
    resource_limits: SandboxResourceLimits


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
    resource_limits: SandboxResourceLimits = field(default_factory=SandboxResourceLimits)


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


def build_sandbox_execution_plan(spec: SandboxCommandSpec) -> SandboxExecutionPlan:
    cwd = Path(spec.cwd).expanduser().resolve()
    if not cwd.exists():
        raise SandboxViolationError("path.escape: cwd does not exist")
    if spec.network_access:
        raise SandboxViolationError("sandbox.network_denied: network.denied")

    read_mounts = _resolve_mounts(spec.read_paths, cwd)
    write_mounts = _resolve_mounts(spec.write_paths, cwd)
    _reject_overlapping_mounts(read_mounts, write_mounts)
    _validate_resource_limits(spec.resource_limits)

    return SandboxExecutionPlan(
        argv=list(spec.argv),
        cwd=cwd,
        env=_filtered_env(spec.env, spec.env_allowlist),
        read_mounts=read_mounts,
        write_mounts=write_mounts,
        network_access=False,
        timeout_ms=spec.timeout_ms,
        stdout_limit_bytes=spec.stdout_limit_bytes,
        stderr_limit_bytes=spec.stderr_limit_bytes,
        resource_limits=spec.resource_limits,
    )


def _resolve_mounts(paths: list[str], cwd: Path) -> list[Path]:
    mounts: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        resolved = path.resolve()
        if _is_credential_path(path) or _is_credential_path(resolved):
            raise SandboxViolationError("credential.denied")
        if not _is_within(resolved, cwd):
            raise SandboxViolationError("path.escape")
        mounts.append(resolved)
    return mounts


def _reject_overlapping_mounts(read_mounts: list[Path], write_mounts: list[Path]) -> None:
    for read_path in read_mounts:
        for write_path in write_mounts:
            if _paths_overlap(read_path, write_path):
                raise SandboxViolationError("mount.overlap")


def _validate_resource_limits(limits: SandboxResourceLimits) -> None:
    if limits.cpu_count < 1 or limits.memory_mb < 16 or limits.process_limit < 1:
        raise SandboxViolationError("resource.invalid")


def _filtered_env(env: dict[str, str], allowlist: list[str]) -> dict[str, str]:
    filtered = {key: env[key] for key in allowlist if key in env}
    for key in filtered:
        if _is_secret_env_key(key):
            raise SandboxViolationError("env.secret_denied")
    return filtered


def _is_within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _is_credential_path(path: Path) -> bool:
    text = str(path)
    parts = set(path.parts)
    home = Path.home()
    if path == home:
        return True
    if path == Path("/var/run/docker.sock"):
        return True
    if ".ssh" in parts:
        return True
    if ".git-credentials" in parts:
        return True
    if ".docker" in parts and "config.json" in parts:
        return True
    if ".config" in parts and ({"gh", "gcloud", "aws"} & parts):
        return True
    return "TOKEN" in text or "credential" in text.lower()


def _is_secret_env_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in ("api_key", "apikey", "token", "password", "secret", "private_key", "credential"))
