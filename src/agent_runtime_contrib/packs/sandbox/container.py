from __future__ import annotations

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import (
    SandboxCommandSpec,
    SandboxExecutionPlan,
    SandboxExecutor,
    SandboxViolationError,
    build_sandbox_execution_plan,
)
from agent_runtime_contrib.packs.base import PackMetadata


def _truncate(value: str, limit_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return value
    return encoded[:limit_bytes].decode("utf-8", errors="ignore")


class ContainerSandboxBackend(SandboxExecutor):
    backend_name = "container-plan-simulation"
    backend_version = "1.2.0"
    support_level = "stable_candidate"
    available = True
    metadata = PackMetadata(
        pack_id="container",
        kind="sandbox_backend",
        support_level="stable_candidate",
        dependencies_group="contrib-sandbox",
        conformance_profile="sandbox-v1.2",
    )

    def build_plan(self, spec: SandboxCommandSpec) -> SandboxExecutionPlan:
        return build_sandbox_execution_plan(spec)

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        try:
            plan = self.build_plan(spec)
        except SandboxViolationError as error:
            return ProcessResult(exit_code=126, stdout="", stderr=str(error))
        stdout = (
            f"container plan simulation: argv={plan.argv!r} "
            f"cwd={str(plan.cwd)!r} network_access={str(plan.network_access).lower()}"
        )
        return ProcessResult(
            exit_code=0,
            stdout=_truncate(stdout, plan.stdout_limit_bytes),
            stderr=_truncate("", plan.stderr_limit_bytes),
        )
