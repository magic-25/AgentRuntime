from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeRun:
    run_id: str
    environment: str
    status: str


@dataclass(frozen=True)
class PolicyBundle:
    bundle_id: str
    version: int
    default_decision: str


@dataclass(frozen=True)
class PackEnablement:
    pack_id: str
    enabled: bool
    reason: str = ""


@dataclass(frozen=True)
class AuditForwardingTarget:
    target_id: str
    kind: str
    enabled: bool
