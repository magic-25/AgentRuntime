from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import (
    SandboxCommandSpec,
    SandboxExecutionPlan,
    SandboxExecutor,
    SandboxUnavailableError,
    build_sandbox_execution_plan,
)
from agent_runtime_contrib.packs.base import PackMetadata


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def _truncate(value: str, limit_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return value
    return encoded[:limit_bytes].decode("utf-8", errors="ignore")


class DockerSandboxBackend(SandboxExecutor):
    backend_name = "docker"
    backend_version = "0.1.0"
    support_level = "preview"
    available = True
    metadata = PackMetadata(
        pack_id="docker",
        kind="sandbox_backend",
        support_level="preview",
        dependencies_group="contrib-sandbox",
        conformance_profile="sandbox-v1.2",
    )

    def __init__(self, image: str = "python:3.12-slim", run: RunCommand = subprocess.run) -> None:
        self.image = image
        self.run = run

    def build_plan(self, spec: SandboxCommandSpec) -> SandboxExecutionPlan:
        return build_sandbox_execution_plan(spec)

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        plan = self.build_plan(spec)
        docker_argv = self._build_docker_argv(plan)
        timeout_seconds = max(1, int((plan.timeout_ms + 999) / 1000))
        try:
            completed = self.run(docker_argv, text=True, capture_output=True, check=False, timeout=timeout_seconds)
        except FileNotFoundError as error:
            raise SandboxUnavailableError(f"docker.unavailable: {error}") from error
        except OSError as error:
            raise SandboxUnavailableError(f"docker.unavailable: {error}") from error
        except subprocess.TimeoutExpired as error:
            stdout = error.output if isinstance(error.output, str) else ""
            stderr = error.stderr if isinstance(error.stderr, str) else str(error)
            return ProcessResult(
                exit_code=124,
                stdout=_truncate(stdout, plan.stdout_limit_bytes),
                stderr=_truncate(f"docker.timeout: {stderr}", plan.stderr_limit_bytes),
            )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return ProcessResult(
            exit_code=completed.returncode,
            stdout=_truncate(stdout, plan.stdout_limit_bytes),
            stderr=_truncate(stderr, plan.stderr_limit_bytes),
        )

    def _build_docker_argv(self, plan: SandboxExecutionPlan) -> list[str]:
        argv = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(plan.resource_limits.process_limit),
            "--cpus",
            str(plan.resource_limits.cpu_count),
            "--memory",
            f"{plan.resource_limits.memory_mb}m",
            "--memory-swap",
            f"{plan.resource_limits.memory_mb}m",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m",
            "--workdir",
            "/workspace",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
        ]

        workspace_mode = "rw" if plan.cwd in plan.write_mounts else "ro"
        argv.extend(["--volume", _volume(plan.cwd, Path("/workspace"), workspace_mode)])

        for write_mount in plan.write_mounts:
            if write_mount == plan.cwd:
                continue
            argv.extend(["--volume", _volume(write_mount, _container_path(plan.cwd, write_mount), "rw")])

        for key in sorted(plan.env):
            argv.extend(["--env", f"{key}={plan.env[key]}"])

        argv.append(self.image)
        argv.extend(plan.argv)
        return argv


def _container_path(cwd: Path, host_path: Path) -> Path:
    relative = host_path.relative_to(cwd)
    return Path("/workspace") / relative


def _volume(host_path: Path, container_path: Path, mode: str) -> str:
    return f"{host_path}:{container_path}:{mode}"
