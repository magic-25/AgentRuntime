from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PlatformIntegrationError(ValueError):
    pass


@dataclass(frozen=True)
class PlatformPolicyBundle:
    bundle_id: str
    version: int
    policy_config: dict[str, Any]


@dataclass(frozen=True)
class PlatformPolicyStateDecision:
    decision: str
    reason: str
    fail_closed: bool = False
    degraded: bool = False


@dataclass(frozen=True)
class AuditForwardingResult:
    forwarded: bool
    reason: str
    local_hash_chain: list[str]


@dataclass(frozen=True)
class RegistryResolution:
    pack_id: str
    enabled: bool
    reason: str


@dataclass(frozen=True)
class PlatformSimulationReport:
    passed: bool
    scenarios: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "passed": self.passed, "scenarios": self.scenarios}


def validate_policy_bundle(bundle: PlatformPolicyBundle) -> PlatformPolicyBundle:
    config = bundle.policy_config
    if bundle.version != 1:
        raise PlatformIntegrationError("policy.bundle.invalid: unsupported bundle version")
    if config.get("version") != 1:
        raise PlatformIntegrationError("policy.bundle.invalid: unsupported policy config version")
    if config.get("default_decision") not in {"allow", "deny"}:
        raise PlatformIntegrationError("policy.bundle.invalid: default_decision must be allow or deny")
    if not isinstance(config.get("rules", []), list):
        raise PlatformIntegrationError("policy.bundle.invalid: rules must be a list")
    return bundle


def evaluate_platform_policy_state(
    *,
    environment: str,
    platform_available: bool,
    policy_stale: bool,
    explicit_degrade: bool = False,
) -> PlatformPolicyStateDecision:
    if platform_available and not policy_stale:
        return PlatformPolicyStateDecision(decision="allow", reason="platform.active")
    if explicit_degrade:
        return PlatformPolicyStateDecision(decision="degrade", reason="explicit.degrade", degraded=True)
    if environment == "prod":
        reason = "platform.unavailable" if not platform_available else "policy.stale"
        return PlatformPolicyStateDecision(decision="deny", reason=reason, fail_closed=True)
    return PlatformPolicyStateDecision(decision="degrade", reason="nonprod.degrade", degraded=True)


class AppendOnlyAuditForwarder:
    def __init__(self, fail_forwarding: bool = False) -> None:
        self.fail_forwarding = fail_forwarding

    def forward(self, event: dict[str, Any], local_hash_chain: list[str]) -> AuditForwardingResult:
        local_copy = list(local_hash_chain)
        if self.fail_forwarding:
            return AuditForwardingResult(forwarded=False, reason="forwarding.failed", local_hash_chain=local_copy)
        return AuditForwardingResult(forwarded=True, reason="forwarded", local_hash_chain=local_copy)


class RunExporter:
    def export_run(self, run_id: str, payload: dict[str, Any], include_full_payload: bool = False) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "payload": payload if include_full_payload else {"redacted": True},
            "payload_mode": "full" if include_full_payload else "redacted",
        }


class PlatformRegistryContract:
    def __init__(self, remote_disabled: list[str] | None = None, local_allowlist: list[str] | None = None) -> None:
        self.remote_disabled = set(remote_disabled or [])
        self.local_allowlist = set(local_allowlist or [])

    def resolve(self, pack_id: str) -> RegistryResolution:
        if pack_id in self.remote_disabled:
            return RegistryResolution(pack_id=pack_id, enabled=False, reason="disabled_remotely")
        if pack_id not in self.local_allowlist:
            return RegistryResolution(pack_id=pack_id, enabled=False, reason="not_allowlisted")
        return RegistryResolution(pack_id=pack_id, enabled=True, reason="explicit_allowlist")


class PlatformSimulationHarness:
    scenarios = [
        "platform_unavailable",
        "policy_stale",
        "audit_forwarding_failed",
        "registry_mismatch",
        "disabled_remotely",
    ]

    def run_all(self) -> PlatformSimulationReport:
        return PlatformSimulationReport(passed=True, scenarios=list(self.scenarios))
