import pytest

from agent_runtime.certification import ConformanceCertification, validate_certification
from agent_runtime.release import platform_ready_release_manifest, production_release_manifest


def test_platform_ready_manifest_covers_stable_contracts_and_support_matrix_v2():
    manifest = platform_ready_release_manifest()

    assert manifest["version"] == "2.0.0"
    assert manifest["product_status"]["external_status"] == "technical_preview"
    assert manifest["product_status"]["next_gate"] == "design_partner_pilot"
    assert manifest["product_status"]["public_launch_ready"] is False
    assert {
        "adapter_contract",
        "sandbox_backend_contract",
        "contrib_pack_registry",
        "policy_bundle",
        "audit_forwarding",
        "run_export",
        "compatibility_manifest",
    } <= set(manifest["stable_contracts"])
    assert {"supported", "stable_candidate", "preview", "experimental", "unsupported"} <= set(
        manifest["support_matrix_v2"]
    )


def test_stable_candidate_subjects_have_conformance_evidence_and_remote_executor_stays_beta():
    manifest = platform_ready_release_manifest()

    stable_candidates = manifest["support_matrix_v2"]["stable_candidate"]
    evidence = manifest["conformance_evidence"]

    for subject in stable_candidates:
        assert subject in evidence
        assert evidence[subject]["passed"] is True

    assert manifest["support_matrix_v2"]["beta"]["remote_executor"] == "contract_beta"
    assert "remote_executor" not in stable_candidates


def test_every_production_claim_has_boundary_limitation_rollback_and_audit_behavior():
    manifest = platform_ready_release_manifest()

    for claim in manifest["production_claims"]:
        assert claim["known_limitations"]
        assert claim["security_boundary"]
        assert claim["rollback_degrade_behavior"]
        assert claim["audit_behavior"]


def test_enterprise_deployment_and_migration_guides_cover_required_paths():
    manifest = platform_ready_release_manifest()

    guide = manifest["enterprise_deployment_guide"]
    migration = manifest["migration_guide"]

    assert "core_contrib_platform_boundary" in guide
    assert "explicit_pack_enablement" in guide
    assert {"1.0_to_2.0", "1.1_to_2.0", "1.3_to_2.0"} <= set(migration)
    assert "hosted_saas" in manifest["support_matrix_v2"]["unsupported"]
    assert "enterprise_console" in manifest["support_matrix_v2"]["unsupported"]


def test_control_plane_api_is_stable_candidate_without_hosted_implementation():
    manifest = platform_ready_release_manifest()

    assert "control_plane_api" in manifest["support_matrix_v2"]["stable_candidate"]
    assert "hosted_control_plane" in manifest["support_matrix_v2"]["unsupported"]


def test_conformance_certification_format_requires_evidence_for_stable_candidate():
    cert = ConformanceCertification(
        subject="openai_adapter",
        contract="adapter_contract",
        support_level="stable_candidate",
        evidence_refs=["tests/test_adapter_conformance_v13.py"],
        passed=True,
    )

    assert validate_certification(cert).passed is True

    with pytest.raises(ValueError, match="evidence"):
        validate_certification(
            ConformanceCertification(
                subject="container_backend",
                contract="sandbox_backend_contract",
                support_level="stable_candidate",
                evidence_refs=[],
                passed=True,
            )
        )


def test_release_status_includes_platform_ready_manifest():
    manifest = production_release_manifest()

    assert manifest["platform_ready_runtime"]["version"] == "2.0.0"
