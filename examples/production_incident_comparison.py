from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agent_runtime import AgentMetadata, RuntimeProfile
from agent_runtime.approval.base import StaticApprovalProvider
from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import SandboxExecutor
from agent_runtime.run_view import write_run_view_html
from agent_runtime.testing.production_agents import ProductionIncidentAgent, ProductionIncidentTranscript


PROMPT = "Investigate checkout production latency and propose the safest mitigation."


class IncidentComparisonSandbox(SandboxExecutor):
    backend_name = "incident-comparison-sandbox"
    available = True

    def execute(self, spec):
        return ProcessResult(exit_code=0, stdout="diagnostic=latency_spike\nerror_budget=burning", stderr="")


def build_production_incident_comparison(
    output_dir: str | Path = ".agent-runtime/production-incident-comparison",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    direct_agent = ProductionIncidentAgent(service="checkout-api", feature_flag="new_checkout_router")
    direct = direct_agent.run_unregistered(PROMPT, direct_tools=_direct_tools())

    runtime, audit_path = _registered_runtime(output_path)
    registered_agent = ProductionIncidentAgent(service="checkout-api", feature_flag="new_checkout_router")
    registered = runtime.register_agent(
        "production-incident-agent",
        registered_agent,
        actor={"id": "incident-agent", "role": "sre"},
        environment="prod",
        metadata=_metadata(),
    ).run(PROMPT)

    report = {
        "artifact_type": "production_incident_registration_comparison",
        "agent": {
            "agent_id": "production-incident-agent",
            "name": "Production Incident Agent",
            "purpose": (
                "模拟生产 incident 排障：读取部署状态、分析错误日志、查询 feature flag、"
                "在 sandbox 中运行 diagnostics，提出 rollback，并尝试未授权 hotfix。"
            ),
        },
        "prompt": PROMPT,
        "direct": _transcript_summary(direct),
        "registered": _transcript_summary(registered),
        "comparison": _comparison_summary(direct, registered),
        "artifacts": {
            "comparison_json": str(output_path / "comparison.json"),
            "registered_audit": str(audit_path),
            "registered_run_view": str(output_path / "registered-run-view.html"),
        },
    }

    (output_path / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_run_view_html(audit_path, output_path / "registered-run-view.html", snapshot=_run_view_snapshot(registered))
    return report


def _registered_runtime(output_path: Path) -> tuple[AgentRuntime, Path]:
    audit_path = output_path / "registered-audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [
                {"id": "allow-status", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:read_deployment_status"]},
                {"id": "allow-logs", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:inspect_error_logs"]},
                {"id": "allow-flag", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:query_feature_flag"]},
                {"id": "allow-diagnostics", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:run_diagnostics"]},
                {"id": "allow-python-diagnostics", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:python"]},
                {"id": "approve-rollback", "environment": "prod", "effect": "require_approval", "capabilities": ["tool.invoke:propose_rollback"]},
                {"id": "deny-hotfix", "environment": "prod", "effect": "deny", "capabilities": ["tool.invoke:apply_hotfix"]},
            ],
        },
        approval_provider=StaticApprovalProvider(approved=True, reason="incident-commander-approved"),
        sandbox_executor=IncidentComparisonSandbox(),
    )

    @runtime.tool(name="read_deployment_status")
    def read_deployment_status(service: str) -> dict[str, str]:
        return {"service": service, "version": "2026.06.21.3", "status": "degraded", "region": "us-east-1"}

    @runtime.tool(name="inspect_error_logs")
    def inspect_error_logs(service: str, window_minutes: int) -> dict[str, Any]:
        return {
            "service": service,
            "window_minutes": window_minutes,
            "signals": ["5xx_spike", "checkout_timeout", "dependency_latency"],
        }

    @runtime.tool(name="query_feature_flag")
    def query_feature_flag(flag: str) -> dict[str, Any]:
        return {"flag": flag, "enabled": True, "rollout": 90}

    runtime.sandboxed_command_tool(
        name="run_diagnostics",
        argv=[sys.executable, "-c", "print('diagnostic=latency_spike')"],
        cwd=str(output_path),
        capabilities_required=["tool.invoke:run_diagnostics", "command.execute:python"],
        network_access=False,
        read_paths=[str(output_path)],
        write_paths=[],
    )

    @runtime.tool(name="propose_rollback", risk_level="high")
    def propose_rollback(service: str, target_version: str, reason: str) -> dict[str, str]:
        return {"service": service, "target_version": target_version, "reason": reason, "ticket": "INC-2026-0621"}

    @runtime.tool(name="apply_hotfix", risk_level="critical")
    def apply_hotfix(service: str, patch_id: str) -> dict[str, str]:
        return {"service": service, "patch_id": patch_id, "status": "applied"}

    return runtime, audit_path


def _direct_tools() -> dict[str, Any]:
    def read_deployment_status(service: str) -> dict[str, str]:
        return {"service": service, "version": "2026.06.21.3", "status": "degraded", "region": "us-east-1"}

    def inspect_error_logs(service: str, window_minutes: int) -> dict[str, Any]:
        return {
            "service": service,
            "window_minutes": window_minutes,
            "signals": ["5xx_spike", "checkout_timeout", "dependency_latency"],
        }

    def query_feature_flag(flag: str) -> dict[str, Any]:
        return {"flag": flag, "enabled": True, "rollout": 90}

    def run_diagnostics(service: str) -> dict[str, str]:
        return {"service": service, "stdout": "diagnostic=latency_spike\nerror_budget=burning"}

    def propose_rollback(service: str, target_version: str, reason: str) -> dict[str, str]:
        return {"service": service, "target_version": target_version, "reason": reason, "ticket": "INC-2026-0621"}

    def apply_hotfix(service: str, patch_id: str) -> dict[str, str]:
        return {"service": service, "patch_id": patch_id, "status": "applied"}

    return {
        "read_deployment_status": read_deployment_status,
        "inspect_error_logs": inspect_error_logs,
        "query_feature_flag": query_feature_flag,
        "run_diagnostics": run_diagnostics,
        "propose_rollback": propose_rollback,
        "apply_hotfix": apply_hotfix,
    }


def _metadata() -> AgentMetadata:
    return AgentMetadata(
        agent_id="production-incident-agent",
        name="Production Incident Agent",
        provider="local",
        framework="state-machine-python",
        capabilities=[
            "tool.invoke:read_deployment_status",
            "tool.invoke:inspect_error_logs",
            "tool.invoke:query_feature_flag",
            "tool.invoke:run_diagnostics",
            "command.execute:python",
            "tool.invoke:propose_rollback",
            "tool.invoke:apply_hotfix",
        ],
        runtime_profile=RuntimeProfile(
            environment="prod",
            execution_mode="runtime_tools",
            max_tool_calls=6,
            approval_required=True,
            sandbox_required=True,
        ),
    )


def _transcript_summary(transcript: ProductionIncidentTranscript) -> dict[str, Any]:
    return {
        "registration": transcript.registration,
        "status": transcript.status,
        "decisions": list(transcript.decisions),
        "phases": list(transcript.phases),
        "findings": transcript.findings,
        "remediation": transcript.remediation,
        "tool_result_statuses": [result.status for result in transcript.tool_results],
        "tool_run_ids": [result.run_id for result in transcript.tool_results],
        "tool_outputs": [_tool_output(result) for result in transcript.tool_results],
        "audit_events": list(transcript.audit_events),
        "trace_id": transcript.trace_id,
        "agent_span_id": transcript.agent_span_id,
        "error": transcript.error,
    }


def _tool_output(result: ToolResult) -> Any:
    if result.status != "success":
        return {"status": result.status, "error": result.error}
    return result.output


def _comparison_summary(
    direct: ProductionIncidentTranscript,
    registered: ProductionIncidentTranscript,
) -> dict[str, bool]:
    return {
        "policy_enforced": any(result.status == "denied" and result.error == "matched_rule" for result in registered.tool_results),
        "approval_enforced": "ApprovalRequested" in registered.audit_events and "ApprovalResolved" in registered.audit_events,
        "sandbox_enforced": "SandboxEnforced" in registered.audit_events,
        "audit_available": bool(registered.audit_events) and not direct.audit_events,
        "direct_hotfix_applied": _hotfix_applied(direct),
        "registered_hotfix_blocked": _hotfix_blocked(registered),
    }


def _hotfix_applied(transcript: ProductionIncidentTranscript) -> bool:
    output = transcript.tool_results[-1].output if transcript.tool_results else None
    return isinstance(output, dict) and output.get("status") == "applied"


def _hotfix_blocked(transcript: ProductionIncidentTranscript) -> bool:
    return bool(transcript.tool_results and transcript.tool_results[-1].status == "denied")


def _run_view_snapshot(transcript: ProductionIncidentTranscript) -> dict[str, Any]:
    return {
        "id": "production_incident_registered",
        "title": "Production Incident Agent",
        "purpose": "展示同一个 production incident agent 注册到 Agent Runtime 后的完整治理链路。",
        "prompt": PROMPT,
        "agent": {
            "agent_id": transcript.agent_id,
            "name": "Production Incident Agent",
            "provider": "local",
            "framework": "state-machine-python",
            "registration": "registered",
        },
        "transcript": {
            "status": transcript.status,
            "decisions": list(transcript.decisions),
            "phases": list(transcript.phases),
            "findings": transcript.findings,
            "remediation": transcript.remediation,
            "trace_id": transcript.trace_id,
            "agent_span_id": transcript.agent_span_id,
            "error": transcript.error,
        },
        "governance": {
            "policy": {"decision": "deny", "reason": "matched_rule", "rule_id": "deny-hotfix"},
            "approval": {"status": "approved", "approved": True, "reason": "incident-commander-approved"},
            "sandbox": {
                "isolation_level": "strong",
                "backend": "incident-comparison-sandbox",
                "available": True,
                "status": "success",
            },
            "audit": {"status": "committed", "event_count": len(transcript.audit_events)},
        },
    }


def main() -> None:
    report = build_production_incident_comparison()
    print("Production Incident Agent comparison generated.")
    print(f"direct status: {report['direct']['status']} hotfix_applied={report['comparison']['direct_hotfix_applied']}")
    print(
        "registered status: "
        f"{report['registered']['status']} hotfix_blocked={report['comparison']['registered_hotfix_blocked']}"
    )
    print(f"comparison json: {Path(report['artifacts']['comparison_json']).resolve()}")
    print(f"registered audit: {Path(report['artifacts']['registered_audit']).resolve()}")
    print(f"registered run view: {Path(report['artifacts']['registered_run_view']).resolve()}")


if __name__ == "__main__":
    main()
