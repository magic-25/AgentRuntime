from __future__ import annotations

from typing import Any


def production_release_manifest() -> dict[str, Any]:
    manifest = {
        "version": "1.0.0",
        "support_level": "production_core",
        "supported": [
            "python_sdk_core",
            "policy_config_schema_v1",
            "stable_public_api",
            "capability_policy",
            "approval_provider_interface",
            "jsonl_audit_sink",
            "sqlite_audit_sink",
            "tamper_evident_audit_chain",
            "audit_chain_verifier",
            "trace_span_events",
            "observer_metrics",
            "subprocess_limited_executor",
            "sandbox_provider_interface",
        ],
        "experimental": [
            "openai_style_adapter",
            "langgraph_style_adapter",
            "mcp_style_adapter",
            "production_pilot_report",
            "opentelemetry_sink",
            "http_api_tool",
            "sidecar_executor",
            "remote_executor",
            "container_executor",
        ],
        "unsupported": [
            "weak_subprocess_for_high_risk_prod",
            "untrusted_code_execution",
            "hosted_control_plane",
            "enterprise_dashboard",
            "rbac",
        ],
        "security_defaults": {
            "unknown_tool": "deny",
            "unknown_capability": "deny",
            "approval_timeout": "reject",
            "policy_hook_exception": "deny",
            "prod_audit_write_failure": "fail_closed",
            "prod_post_execution_audit_write_failure": "return_error",
            "raw_payload_storage": "disabled_by_default",
            "subprocess_environment": "allowlist_only",
        },
        "extension_pilot": {
            "version": "1.1.0",
            "support_level": "extension_pilot",
            "preview": [
                "agent_runtime_contrib_shell",
                "pack_registry",
                "openai_adapter_pack",
                "anthropic_adapter_pack",
                "langgraph_adapter_pack",
                "mcp_adapter_pack",
                "codex_adapter_pack",
                "container_backend_contract",
                "code_ci_reference_pilot",
                "control_plane_prelude",
            ],
            "stub": [
                "sidecar_backend",
                "remote_executor_backend",
            ],
            "defaults": {
                "packs": "disabled",
                "pack_enablement": "explicit_allowlist",
                "pilot_network": "deny",
                "pilot_commit_push_pr": "deny",
            },
        },
        "sandbox_runtime_hardening": {
            "version": "1.2.0",
            "support_level": "sandbox_runtime_hardening",
            "support_matrix": {
                "container": {
                    "support_level": "stable_candidate",
                    "suitable_for": ["high_risk_prod_candidate_with_explicit_policy_and_audit"],
                    "limitations": ["container_trusted_base_required", "no_absolute_escape_prevention"],
                },
                "sidecar": {
                    "support_level": "preview",
                    "suitable_for": ["sidecar_contract_validation", "controlled_preview"],
                    "limitations": ["minimal_request_response_only", "no_production_scheduler"],
                },
                "remote": {
                    "support_level": "contract_beta",
                    "suitable_for": ["protocol_design", "fail_closed_contract_tests"],
                    "limitations": ["no_production_execution", "transport_security_deferred"],
                },
                "weak_subprocess": {
                    "support_level": "low_risk_only",
                    "suitable_for": ["low_risk_allowlisted_commands"],
                    "limitations": ["not_for_high_risk_prod_write", "not_a_security_sandbox"],
                },
            },
            "limitations": [
                "absolute_escape_prevention",
                "multi_tenant_scheduling",
                "hosted_execution_pool",
                "remote_executor_production",
            ],
        },
        "adapter_stabilization": {
            "version": "1.3.0",
            "support_level": "adapter_stable_candidate",
            "compatibility_matrix": {
                "openai": {"support_level": "stable_candidate", "shape": "function_call"},
                "anthropic": {"support_level": "stable_candidate", "shape": "tool_use"},
                "langgraph": {"support_level": "stable_candidate", "shape": "tool_input"},
                "mcp": {"support_level": "stable_candidate", "shape": "tools_call"},
                "codex_workspace": {"support_level": "stable_candidate", "shape": "workspace_command"},
                "codex_workflow": {"support_level": "preview", "shape": "workflow"},
                "codex_connectors": {"support_level": "experimental", "shape": "connector"},
            },
            "migration_guide": [
                "0.4_spike_to_1.3_adapter",
                "keep_pack_disabled_until_explicit_allowlist",
                "move_provider_tool_call_to_translate_only_adapter",
            ],
            "failure_mode_guide": [
                "server_unavailable",
                "tool_unavailable",
                "deny",
                "approval_required",
                "sandbox_required",
                "redaction_error",
            ],
        },
        "platform_integration_preview": {
            "version": "1.5.0",
            "support_level": "preview",
            "contracts": [
                "policy_registry_contract",
                "audit_forwarding_contract",
                "run_export_contract",
                "adapter_backend_registry_contract",
                "tenant_project_actor_resource_model",
                "platform_simulation_harness",
            ],
            "prod_failure_semantics": {
                "platform_unavailable": "fail_closed",
                "policy_stale": "fail_closed",
                "audit_forwarding_failed": "local_chain_preserved",
            },
            "run_export": {
                "full_payload_default": "disabled",
                "payload_mode": "redacted",
            },
            "non_goals": [
                "hosted_control_plane",
                "dashboard",
                "rbac_ui",
                "remote_execution_orchestration_service",
            ],
        },
    }
    manifest["platform_ready_runtime"] = platform_ready_release_manifest()
    return manifest


def platform_ready_release_manifest() -> dict[str, Any]:
    stable_candidates = [
        "openai_adapter",
        "anthropic_adapter",
        "langgraph_adapter",
        "mcp_adapter",
        "codex_workspace_adapter",
        "container_backend",
        "sidecar_backend",
        "control_plane_api",
    ]
    return {
        "version": "2.0.0",
        "support_level": "platform_ready_runtime",
        "product_status": {
            "external_status": "technical_preview",
            "next_gate": "design_partner_pilot",
            "public_launch_ready": False,
            "claim_boundary": "platform_ready_contracts_not_hosted_enterprise_platform",
        },
        "stable_contracts": [
            "adapter_contract",
            "sandbox_backend_contract",
            "contrib_pack_registry",
            "policy_bundle",
            "audit_forwarding",
            "run_export",
            "compatibility_manifest",
        ],
        "support_matrix_v2": {
            "supported": [
                "core_runtime_contracts",
                "policy_config_schema_v1",
                "approval_provider_interface",
                "audit_sink_contract",
                "observer_metrics",
                "adapter_conformance_contract",
                "sandbox_conformance_contract",
            ],
            "stable_candidate": stable_candidates,
            "preview": ["codex_workflow", "platform_integration_contracts"],
            "experimental": ["codex_connectors", "opentelemetry_sink", "http_api_tool"],
            "beta": {"remote_executor": "contract_beta"},
            "unsupported": [
                "hosted_saas",
                "hosted_control_plane",
                "enterprise_console",
                "rbac_ui",
                "absolute_sandbox_escape_prevention",
            ],
        },
        "conformance_evidence": {
            subject: {
                "passed": True,
                "evidence_refs": _evidence_refs_for(subject),
            }
            for subject in stable_candidates
        },
        "production_claims": [
            {
                "claim": "platform_ready_runtime_contracts",
                "known_limitations": ["not_hosted_saas", "explicit_pack_enablement_required"],
                "security_boundary": ["runtime_policy_audit_sandbox_local_enforcement"],
                "rollback_degrade_behavior": ["core_only_mode", "prod_platform_failure_fail_closed"],
                "audit_behavior": ["local_hash_chain_preserved", "forwarding_best_effort_after_local_write"],
            },
            {
                "claim": "stable_candidate_extension_ecosystem",
                "known_limitations": ["provider_sdk_full_coverage_not_claimed", "remote_executor_beta"],
                "security_boundary": ["adapter_translate_only", "registry_no_auto_enable"],
                "rollback_degrade_behavior": ["disable_optional_pack", "remove_allowlist_entry"],
                "audit_behavior": ["adapter_source_recorded", "conformance_evidence_required"],
            },
        ],
        "enterprise_deployment_guide": [
            "core_contrib_platform_boundary",
            "explicit_pack_enablement",
            "policy_bundle_validation",
            "audit_forwarding_after_local_chain",
            "run_export_redacted_by_default",
            "sandbox_support_level_selection",
        ],
        "migration_guide": [
            "1.0_to_2.0",
            "1.1_to_2.0",
            "1.3_to_2.0",
        ],
        "certification_format": {
            "schema_version": 1,
            "required_fields": ["subject", "contract", "support_level", "evidence_refs", "passed"],
        },
    }


def _evidence_refs_for(subject: str) -> list[str]:
    if subject.endswith("_adapter"):
        return ["tests/test_adapter_conformance_v13.py", "tests/test_adapter_stabilization_v13.py"]
    if subject in {"container_backend", "sidecar_backend"}:
        return ["tests/test_sandbox_conformance_v12.py", "tests/test_sandbox_hardening_v12.py"]
    if subject == "control_plane_api":
        return ["tests/test_platform_integration_v15.py", "tests/test_platform_release_v15.py"]
    return ["tests"]
