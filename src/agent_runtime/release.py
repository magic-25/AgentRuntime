from __future__ import annotations

from typing import Any


def production_release_manifest() -> dict[str, Any]:
    return {
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
    }
