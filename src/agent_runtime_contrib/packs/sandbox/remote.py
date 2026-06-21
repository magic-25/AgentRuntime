from __future__ import annotations

from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxExecutor, SandboxUnavailableError
from agent_runtime_contrib.packs.base import PackMetadata


class RemoteSandboxBackend(SandboxExecutor):
    backend_name = "remote"
    backend_version = "1.2.0-contract-beta"
    support_level = "contract_beta"
    available = False
    metadata = PackMetadata(
        pack_id="remote",
        kind="sandbox_backend",
        support_level="contract_beta",
        dependencies_group="contrib-sandbox",
        conformance_profile="sandbox-v1.2",
    )

    def execute(self, spec: SandboxCommandSpec) -> ProcessResult:
        raise SandboxUnavailableError("remote sandbox backend is contract_beta only in v1.2")
