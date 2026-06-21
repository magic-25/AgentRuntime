from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from agent_runtime.execution.sandbox import SandboxCommandSpec, SandboxUnavailableError, SandboxViolationError
from agent_runtime_contrib.packs.sandbox.container import ContainerSandboxBackend
from agent_runtime_contrib.packs.sandbox.docker import DockerSandboxBackend
from agent_runtime_contrib.packs.sandbox.remote import RemoteSandboxBackend
from agent_runtime_contrib.packs.sandbox.sidecar import LocalSidecarClient, SidecarSandboxBackend


@dataclass(frozen=True)
class SandboxConformanceReport:
    backend: str
    backend_version: str
    support_level: str
    passed: bool
    checks: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backend": self.backend,
            "backend_version": self.backend_version,
            "support_level": self.support_level,
            "passed": self.passed,
            "checks": self.checks,
            "failure_reasons": self.failure_reasons,
            "limitations": self.limitations,
        }


class SandboxConformanceRunner:
    def run_backend(self, backend: Any) -> SandboxConformanceReport:
        checks = ["metadata_valid"]
        failure_reasons: list[str] = []
        limitations = _limitations_for_backend(backend)

        if isinstance(backend, ContainerSandboxBackend):
            checks.extend(_run_container_abuse_checks(backend, failure_reasons))
        elif isinstance(backend, DockerSandboxBackend):
            checks.extend(_run_docker_contract_checks(backend, failure_reasons))
        elif isinstance(backend, SidecarSandboxBackend):
            checks.append("sidecar.request_response")
            try:
                backend.execute(SandboxCommandSpec(argv=["python", "-V"], cwd="."))
            except SandboxUnavailableError as error:
                failure_reasons.append(str(error).split(":", maxsplit=1)[0])
        elif isinstance(backend, RemoteSandboxBackend):
            checks.append("remote.contract_beta")
            failure_reasons.append("remote.contract_beta_only")
        else:
            failure_reasons.append("backend.unsupported")

        return SandboxConformanceReport(
            backend=_public_backend_name(backend),
            backend_version=getattr(backend, "backend_version", "unknown"),
            support_level=getattr(backend, "support_level", "unknown"),
            passed=not failure_reasons,
            checks=checks,
            failure_reasons=failure_reasons,
            limitations=limitations,
        )


def backend_for_name(name: str) -> Any:
    if name == "container":
        return ContainerSandboxBackend()
    if name == "docker":
        return DockerSandboxBackend()
    if name == "sidecar":
        return SidecarSandboxBackend(client=LocalSidecarClient())
    if name == "remote":
        return RemoteSandboxBackend()
    raise ValueError(f"unsupported sandbox backend: {name}")


def _run_container_abuse_checks(backend: ContainerSandboxBackend, failure_reasons: list[str]) -> list[str]:
    checks: list[str] = []
    with TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        repo = root / "repo"
        src = repo / "src"
        out = repo / "out"
        src.mkdir(parents=True)
        out.mkdir()

        checks.append("abuse.path_traversal")
        if _sandbox_request_was_allowed(
            backend,
            SandboxCommandSpec(argv=["python", "-V"], cwd=str(repo), read_paths=[str(repo / "..")]),
        ):
            failure_reasons.append("path_traversal.allowed")

        checks.append("abuse.credential_path")
        if _sandbox_request_was_allowed(
            backend,
            SandboxCommandSpec(argv=["python", "-V"], cwd=str(repo), read_paths=[str(Path.home() / ".ssh" / "id_rsa")]),
        ):
            failure_reasons.append("credential_path.allowed")

        checks.append("abuse.network_attempt")
        if _sandbox_request_was_allowed(
            backend,
            SandboxCommandSpec(
                argv=["curl", "https://example.com"],
                cwd=str(repo),
                read_paths=[str(src)],
                write_paths=[str(out)],
                network_access=True,
            )
        ):
            failure_reasons.append("network.allowed")

        checks.append("abuse.output_flood")
        output_result = backend.execute(
            SandboxCommandSpec(
                argv=["python", "-c", "print('x' * 100)"],
                cwd=str(repo),
                read_paths=[str(src)],
                write_paths=[str(out)],
                stdout_limit_bytes=24,
            )
        )
        if len(output_result.stdout.encode("utf-8")) > 24:
            failure_reasons.append("output_limit.missing")

    return checks


def _run_docker_contract_checks(backend: DockerSandboxBackend, failure_reasons: list[str]) -> list[str]:
    checks = ["docker.real_execution_contract"]
    with TemporaryDirectory() as raw_tmp:
        root = Path(raw_tmp)
        checks.append("abuse.network_attempt")
        if _sandbox_request_was_allowed(
            backend,
            SandboxCommandSpec(argv=["curl", "https://example.com"], cwd=str(root), network_access=True),
        ):
            failure_reasons.append("network.allowed")
    return checks


def _sandbox_request_was_allowed(backend: Any, spec: SandboxCommandSpec) -> bool:
    try:
        return backend.execute(spec).exit_code == 0
    except SandboxViolationError:
        return False


def _public_backend_name(backend: Any) -> str:
    metadata = getattr(backend, "metadata", None)
    if metadata is not None:
        return metadata.pack_id
    return getattr(backend, "backend_name", "unknown")


def _limitations_for_backend(backend: Any) -> list[str]:
    if isinstance(backend, ContainerSandboxBackend):
        return [
            "container_plan_only_no_real_docker_execution",
            "container_trusted_base_required",
            "no_absolute_escape_prevention",
        ]
    if isinstance(backend, DockerSandboxBackend):
        return [
            "docker_real_execution_requires_local_daemon",
            "container_trusted_base_required",
            "no_absolute_escape_prevention",
            "host_docker_security_baseline_required",
        ]
    support_level = getattr(backend, "support_level", "unknown")
    if support_level == "preview":
        return ["minimal_sidecar_contract_only", "no_production_scheduler"]
    if support_level == "contract_beta":
        return ["contract_beta_only", "no_production_execution"]
    return ["unknown_support_level"]
