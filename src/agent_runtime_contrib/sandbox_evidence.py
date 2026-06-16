from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class SandboxRuntimeEvidence:
    backend: str
    runtime_present: bool
    daemon_available: bool
    client_version: str = ""
    server_version: str = ""
    smoke_ran: bool = False
    smoke_passed: bool = False
    smoke_output: str = ""
    failure_reason: str = ""
    limitations: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backend": self.backend,
            "runtime_present": self.runtime_present,
            "daemon_available": self.daemon_available,
            "client_version": self.client_version,
            "server_version": self.server_version,
            "smoke_ran": self.smoke_ran,
            "smoke_passed": self.smoke_passed,
            "smoke_output": self.smoke_output,
            "failure_reason": self.failure_reason,
            "limitations": self.limitations,
        }


class DockerRuntimeEvidenceCollector:
    def __init__(self, run: RunCommand = subprocess.run) -> None:
        self.run = run

    def collect(self, run_smoke: bool = False, image: str = "busybox:latest") -> SandboxRuntimeEvidence:
        limitations = [
            "container_trusted_base_required",
            "no_absolute_escape_prevention",
            "smoke_does_not_prove_escape_resistance",
        ]
        try:
            client = self.run(["docker", "--version"], text=True, capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            return SandboxRuntimeEvidence(
                backend="docker",
                runtime_present=False,
                daemon_available=False,
                failure_reason=f"docker.client_unavailable: {error}",
                limitations=limitations,
            )

        try:
            server = self.run(
                ["docker", "info", "--format", "{{json .ServerVersion}}"],
                text=True,
                capture_output=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            return SandboxRuntimeEvidence(
                backend="docker",
                runtime_present=True,
                daemon_available=False,
                client_version=client.stdout.strip(),
                failure_reason=f"docker.daemon_unavailable: {error}",
                limitations=limitations,
            )

        smoke_passed = False
        smoke_output = ""
        failure_reason = ""
        if run_smoke:
            try:
                smoke = self.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network",
                        "none",
                        "--read-only",
                        "--cap-drop",
                        "ALL",
                        image,
                        "sh",
                        "-c",
                        "echo agent-runtime-smoke",
                    ],
                    text=True,
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
                smoke_passed = True
                smoke_output = smoke.stdout.strip()
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                failure_reason = f"docker.smoke_failed: {error}"

        return SandboxRuntimeEvidence(
            backend="docker",
            runtime_present=True,
            daemon_available=True,
            client_version=client.stdout.strip(),
            server_version=_decode_json_string(server.stdout.strip()),
            smoke_ran=run_smoke,
            smoke_passed=smoke_passed,
            smoke_output=smoke_output,
            failure_reason=failure_reason,
            limitations=limitations,
        )


def _decode_json_string(value: str) -> str:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return value
    return str(decoded)
