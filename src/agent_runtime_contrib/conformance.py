from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_runtime_contrib.packs.base import PackMetadata


@dataclass(frozen=True)
class ConformanceReport:
    pack_id: str
    pack_kind: str
    support_level: str
    passed: bool
    checks: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "pack_id": self.pack_id,
            "pack_kind": self.pack_kind,
            "support_level": self.support_level,
            "passed": self.passed,
            "checks": self.checks,
            "failure_reasons": self.failure_reasons,
        }


class ConformanceRunner:
    def run_metadata(self, metadata: PackMetadata) -> ConformanceReport:
        checks = ["metadata_valid"]
        failure_reasons: list[str] = []
        if metadata.kind == "adapter" and metadata.capabilities_declared:
            failure_reasons.append("adapter_capability_declared")
        return ConformanceReport(
            pack_id=metadata.pack_id,
            pack_kind=metadata.kind,
            support_level=metadata.support_level,
            passed=not failure_reasons,
            checks=checks,
            failure_reasons=failure_reasons,
        )

    def run_adapter_pack(self, pack: Any) -> ConformanceReport:
        metadata_report = self.run_metadata(pack.metadata)
        checks = [*metadata_report.checks, "translate_only"]
        failure_reasons = list(metadata_report.failure_reasons)
        if not callable(getattr(pack, "translate", None)):
            failure_reasons.append("adapter_translate_missing")
        return ConformanceReport(
            pack_id=pack.metadata.pack_id,
            pack_kind=pack.metadata.kind,
            support_level=pack.metadata.support_level,
            passed=not failure_reasons,
            checks=checks,
            failure_reasons=failure_reasons,
        )
