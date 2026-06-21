from __future__ import annotations

import json
import sys

from agent_runtime import AgentMetadata, RuntimeProfile
from agent_runtime.approval.base import StaticApprovalProvider
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.base import ProcessResult
from agent_runtime.testing.production_agents import ProductionIncidentAgent


class RecordingIncidentSandbox:
    backend_name = "incident-strong-sandbox"
    available = True

    def __init__(self) -> None:
        self.specs = []

    def execute(self, spec):
        self.specs.append(spec)
        return ProcessResult(exit_code=0, stdout="diagnostic=latency_spike\nerror_budget=burning", stderr="")


def _events(audit_path):
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _trace_finish(events, span_kind):
    return [
        event
        for event in events
        if event["event_type"] == "TraceSpanFinished" and event["payload"].get("span_kind") == span_kind
    ]


def _direct_tools():
    def read_deployment_status(service: str) -> dict[str, str]:
        return {"service": service, "version": "2026.06.21.3", "status": "degraded", "region": "us-east-1"}

    def inspect_error_logs(service: str, window_minutes: int) -> dict[str, object]:
        return {
            "service": service,
            "window_minutes": window_minutes,
            "signals": ["5xx_spike", "checkout_timeout", "dependency_latency"],
        }

    def query_feature_flag(flag: str) -> dict[str, object]:
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


def _runtime(tmp_path):
    audit_path = tmp_path / "production-incident-audit.jsonl"
    sandbox = RecordingIncidentSandbox()
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
        sandbox_executor=sandbox,
    )

    @runtime.tool(name="read_deployment_status")
    def read_deployment_status(service: str) -> dict[str, str]:
        return {"service": service, "version": "2026.06.21.3", "status": "degraded", "region": "us-east-1"}

    @runtime.tool(name="inspect_error_logs")
    def inspect_error_logs(service: str, window_minutes: int) -> dict[str, object]:
        return {
            "service": service,
            "window_minutes": window_minutes,
            "signals": ["5xx_spike", "checkout_timeout", "dependency_latency"],
        }

    @runtime.tool(name="query_feature_flag")
    def query_feature_flag(flag: str) -> dict[str, object]:
        return {"flag": flag, "enabled": True, "rollout": 90}

    runtime.sandboxed_command_tool(
        name="run_diagnostics",
        argv=[sys.executable, "-c", "print('diagnostic=latency_spike')"],
        cwd=str(tmp_path),
        capabilities_required=["tool.invoke:run_diagnostics", "command.execute:python"],
        network_access=False,
        read_paths=[str(tmp_path)],
        write_paths=[],
    )

    @runtime.tool(name="propose_rollback", risk_level="high")
    def propose_rollback(service: str, target_version: str, reason: str) -> dict[str, str]:
        return {"service": service, "target_version": target_version, "reason": reason, "ticket": "INC-2026-0621"}

    @runtime.tool(name="apply_hotfix", risk_level="critical")
    def apply_hotfix(service: str, patch_id: str) -> dict[str, str]:
        return {"service": service, "patch_id": patch_id, "status": "applied"}

    return runtime, audit_path, sandbox


def test_production_incident_agent_exercises_governed_runtime_paths(tmp_path):
    runtime, audit_path, sandbox = _runtime(tmp_path)
    agent = ProductionIncidentAgent(service="checkout-api", feature_flag="new_checkout_router")

    transcript = runtime.register_agent(
        "production-incident-agent",
        agent,
        actor={"id": "incident-agent", "role": "sre"},
        environment="prod",
        metadata=AgentMetadata(
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
        ),
    ).run("Investigate checkout production latency and propose the safest mitigation.")

    assert transcript.status == "completed_with_denial"
    assert transcript.phases == ["intake", "investigate", "diagnose", "remediate", "guardrail", "summarize"]
    assert transcript.decisions == [
        "intake:checkout-api",
        "call:read_deployment_status",
        "call:inspect_error_logs",
        "call:query_feature_flag",
        "call:run_diagnostics",
            "diagnosis:rollback_candidate",
            "call:propose_rollback",
            "call:apply_hotfix",
            "blocked:matched_rule",
            "summary:ready_for_human_review",
        ]
    assert [result.status for result in transcript.tool_results] == [
        "success",
        "success",
        "success",
        "success",
        "success",
        "denied",
    ]
    assert transcript.findings["impact"] == "checkout-api degraded in us-east-1"
    assert transcript.remediation["approved_action"] == "rollback"
    assert transcript.remediation["blocked_action"] == "apply_hotfix"
    assert sandbox.specs[0].network_access is False
    assert sandbox.specs[0].write_paths == []

    events = _events(audit_path)
    assert [event["event_type"] for event in events].count("ToolCallRequested") == 6
    assert _trace_finish(events, "agent_run")[0]["payload"]["status"] == "completed_with_denial"
    assert any(span["payload"].get("status") == "approved" for span in _trace_finish(events, "approval_gate"))
    assert any(span["payload"].get("isolation_level") == "strong" for span in _trace_finish(events, "sandbox_execution"))
    assert any(
        span["payload"].get("decision") == "deny" and span["payload"].get("rule_id") == "deny-hotfix"
        for span in _trace_finish(events, "policy_evaluation")
    )


def test_production_incident_agent_can_run_unregistered_with_direct_tools():
    agent = ProductionIncidentAgent(service="checkout-api", feature_flag="new_checkout_router")

    transcript = agent.run_unregistered(
        "Investigate checkout production latency and propose the safest mitigation.",
        direct_tools=_direct_tools(),
    )

    assert transcript.status == "completed"
    assert transcript.registration == "unregistered"
    assert transcript.audit_events == []
    assert transcript.decisions == [
        "intake:checkout-api",
        "call:read_deployment_status",
        "call:inspect_error_logs",
        "call:query_feature_flag",
        "call:run_diagnostics",
        "diagnosis:rollback_candidate",
        "call:propose_rollback",
        "call:apply_hotfix",
        "summary:ready_for_human_review",
    ]
    assert [result.run_id for result in transcript.tool_results] == [None, None, None, None, None, None]
    assert [result.status for result in transcript.tool_results] == ["success", "success", "success", "success", "success", "success"]
    assert transcript.remediation["approved_action"] == "rollback"
    assert transcript.remediation["blocked_action"] is None
