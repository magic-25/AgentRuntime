from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_runtime import AgentRuntime
from agent_runtime.approval.base import CallbackApprovalProvider
from agent_runtime.core.models import ApprovalDecision, ApprovalRequest
from agent_runtime.observer.memory import InMemoryObserver
from agent_runtime.pilot.records import PilotScenarioRecord, ProductionPilotReport


def run_pilot(work_dir: str | Path, reset: bool = False) -> dict[str, Any]:
    root = Path(work_dir)
    root.mkdir(parents=True, exist_ok=True)
    audit_path = root / "pilot-audit.db"
    observer_path = root / "observer.json"
    report_path = root / "pilot-report.json"
    if reset:
        for path in (audit_path, observer_path, report_path):
            if path.exists():
                path.unlink()
    observer = InMemoryObserver()
    runtime = AgentRuntime.from_dict(_config(audit_path), approval_provider=CallbackApprovalProvider(_approval), observer=observer)

    @runtime.tool(name="read_customer", capabilities_required=["tool.invoke:read_customer", "customer.read"])
    def read_customer(customer_id: str) -> dict[str, str]:
        return {"customer_id": customer_id, "tier": "internal-preview"}

    @runtime.tool(name="write_customer_note", risk_level="high", capabilities_required=["tool.invoke:write_customer_note", "customer.write"])
    def write_customer_note(customer_id: str, note: str) -> dict[str, str]:
        return {"customer_id": customer_id, "note": note, "status": "updated"}

    runtime.command_tool(
        name="check_build_status",
        argv=[sys.executable, "-c", "import os; print('BUILD_ID=' + os.environ.get('BUILD_ID', ''))"],
        cwd=str(root),
        env={"BUILD_ID": "build-123", "SECRET_TOKEN": "should-not-enter-process"},
        env_allowlist=["BUILD_ID"],
        timeout_ms=1000,
        stdout_limit_bytes=128,
        stderr_limit_bytes=128,
        capabilities_required=["tool.invoke:check_build_status", "command.execute:python"],
    )

    actor = {"id": "staging-admin", "role": "operator"}
    read_customer_result = runtime.call_tool("read_customer", {"customer_id": "cus_1"}, actor=actor, environment="staging")
    approved_write = runtime.call_tool(
        "write_customer_note",
        {"customer_id": "cus_1", "note": "approved pilot note"},
        actor=actor,
        environment="staging",
    )
    timed_out_write = runtime.call_tool(
        "write_customer_note",
        {"customer_id": "cus_1", "note": "timeout requested"},
        actor=actor,
        environment="staging",
    )
    unknown_prod_tool = runtime.call_tool("unknown_prod_tool", {}, actor=actor, environment="prod")
    command_status = runtime.call_tool("check_build_status", {}, actor=actor, environment="staging")

    observer_path.write_text(json.dumps(observer.status(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
    _report(report_path)
    return {
        "audit_path": audit_path,
        "observer_path": observer_path,
        "report_path": report_path,
        "read_customer": read_customer_result,
        "approved_write": approved_write,
        "timed_out_write": timed_out_write,
        "unknown_prod_tool": unknown_prod_tool,
        "command_status": command_status,
    }


def _approval(request: ApprovalRequest) -> ApprovalDecision:
    if request.input_summary.get("note") == "timeout requested":
        return ApprovalDecision(approved=False, reason="approval.timeout", timed_out=True)
    return ApprovalDecision(approved=True, reason="pilot-approved")


def _config(audit_path: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "default_decision": "deny",
        "audit": {"sink": "sqlite", "path": str(audit_path), "on_write_failure": {"staging": "fail_closed", "prod": "fail_closed"}},
        "tracing": {"enabled": True},
        "redaction": {"sensitive_fields": ["secret", "token", "password", "SECRET_TOKEN"]},
        "rules": [
            {"id": "staging-read", "environment": "staging", "effect": "allow", "capabilities": ["tool.invoke:read_customer", "customer.read"]},
            {"id": "staging-tool-invoke", "environment": "staging", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            {"id": "staging-write-approval", "environment": "staging", "effect": "require_approval", "capabilities": ["customer.write"]},
            {"id": "staging-command", "environment": "staging", "effect": "allow", "capabilities": ["command.execute:*"]},
            {"id": "prod-write-approval", "environment": "prod", "effect": "require_approval", "capabilities": ["customer.write"]},
        ],
    }


def _report(path: Path) -> None:
    ProductionPilotReport(
        pilot_name="internal-admin-staging",
        environment="staging",
        isolation_level="subprocess_limited_no_strong_sandbox",
        data_retention_policy="sqlite audit retained for 30 days; raw payload disabled by default",
        audit_sink_boundary="application owns sqlite file, runtime owns append-only event shape",
        failure_mode_drills=["approval.timeout", "policy.deny_unknown_tool", "executor.timeout"],
        risk_bypasses=["host application direct database writes", "host process has final filesystem/network authority"],
        scenarios=[
            PilotScenarioRecord(
                name="内部后台助手",
                production_support_judgement="pilot_supported_with_approval",
                data_governance_judgement="sqlite_audit_redacted_no_raw_secret_payloads",
                evidence={"audit_sink": "sqlite", "approval": "callback", "observer": "memory"},
            ),
            PilotScenarioRecord(
                name="低风险自动化任务",
                production_support_judgement="pilot_supported_for_low_risk_readonly_commands",
                data_governance_judgement="env_allowlist_and_output_truncation_required",
                evidence={"command_allowlist": "argv", "isolation": "subprocess_limited"},
            ),
            PilotScenarioRecord(
                name="框架迁移验证",
                production_support_judgement="pilot_supported_when_adapter_has_no_policy_logic",
                data_governance_judgement="adapter_source_recorded_in_audit_and_trace",
                evidence={"adapters": ["openai_style", "langgraph_style", "mcp_style"]},
            ),
        ],
    ).write_json(path)


if __name__ == "__main__":
    output = run_pilot(Path(".agent-runtime/staging-pilot"), reset=True)
    print(json.dumps({key: str(value) for key, value in output.items() if key.endswith("_path")}, ensure_ascii=False, indent=2))
