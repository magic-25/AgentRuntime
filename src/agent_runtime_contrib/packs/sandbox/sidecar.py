from __future__ import annotations

from typing import Protocol

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import (
    SandboxCommandSpec,
    SandboxExecutionPlan,
    SandboxExecutor,
    SandboxUnavailableError,
    build_sandbox_execution_plan,
)
from agent_runtime_contrib.packs.base import PackMetadata


class SidecarClient(Protocol):
    def run(self, plan: SandboxExecutionPlan) -> ProcessResult:
        ...


class LocalSidecarClient:
    def run(self, plan: SandboxExecutionPlan) -> ProcessResult:
        return ProcessResult(exit_code=0, stdout="sidecar-ok", stderr="")


class SidecarSandboxBackend(SandboxExecutor):
    backend_name = "sidecar"
    support_level = "preview"
    metadata = PackMetadata(
        pack_id="sidecar",
        kind="sandbox_backend",
        support_level="preview",
        dependencies_group="contrib-sandbox",
        conformance_profile="sandbox-v1.2",
    )

    def __init__(self, client: SidecarClient | None = None, backend_version: str = "1.2.0-preview") -> None:
        self.client = client
        self.backend_version = backend_version

    @property
    def available(self) -> bool:
        return self.client is not None

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        if self.client is None:
            raise SandboxUnavailableError("sandbox.unavailable: sidecar backend is unavailable")
        plan = build_sandbox_execution_plan(spec)
        try:
            return self.client.run(plan)
        except TimeoutError as error:
            raise SandboxUnavailableError("sandbox.timeout: sidecar backend timed out") from error
