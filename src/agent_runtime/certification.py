from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConformanceCertification:
    subject: str
    contract: str
    support_level: str
    evidence_refs: list[str] = field(default_factory=list)
    passed: bool = False
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "subject": self.subject,
            "contract": self.contract,
            "support_level": self.support_level,
            "evidence_refs": self.evidence_refs,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class CertificationReport:
    release: str
    certifications: list[ConformanceCertification]
    passed: bool
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "release": self.release,
            "passed": self.passed,
            "certifications": [certification.to_dict() for certification in self.certifications],
        }


def validate_certification(certification: ConformanceCertification) -> ConformanceCertification:
    if certification.support_level in {"stable", "stable_candidate"} and not certification.evidence_refs:
        raise ValueError("conformance evidence is required for stable and stable_candidate subjects")
    if not certification.passed:
        raise ValueError("conformance certification must pass")
    return certification


def build_platform_ready_certification_report(subject: str = "all") -> CertificationReport:
    from agent_runtime.release import platform_ready_release_manifest

    manifest = platform_ready_release_manifest()
    matrix = manifest["support_matrix_v2"]
    candidates = list(matrix["stable_candidate"])
    selected = candidates if subject == "all" else [subject]
    evidence = manifest["conformance_evidence"]
    certifications = [
        validate_certification(
            ConformanceCertification(
                subject=item,
                contract=_contract_for_subject(item),
                support_level="stable_candidate",
                evidence_refs=list(evidence.get(item, {}).get("evidence_refs", [])),
                passed=bool(evidence.get(item, {}).get("passed", False)),
            )
        )
        for item in selected
    ]
    return CertificationReport(
        release="platform_ready_runtime",
        certifications=certifications,
        passed=all(certification.passed for certification in certifications),
    )


def _contract_for_subject(subject: str) -> str:
    if subject.endswith("_adapter"):
        return "adapter_contract"
    if subject.endswith("_backend"):
        return "sandbox_backend_contract"
    if subject == "control_plane_api":
        return "control_plane_api_contract"
    return "runtime_contract"
