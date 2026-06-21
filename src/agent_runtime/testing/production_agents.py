from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime


@dataclass(frozen=True)
class ProductionIncidentTranscript:
    status: str
    decisions: list[str]
    phases: list[str]
    findings: dict[str, Any]
    remediation: dict[str, Any]
    registration: str = "runtime"
    agent_id: str | None = None
    agent_metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    agent_span_id: str | None = None
    tool_results: list[ToolResult] = field(default_factory=list)
    audit_events: list[str] = field(default_factory=list)
    error: str | None = None


class ProductionIncidentAgent:
    """Deterministic production-style incident agent used to exercise runtime governance."""

    def __init__(self, service: str, feature_flag: str) -> None:
        self.service = service
        self.feature_flag = feature_flag
        self.runtime: AgentRuntime | None = None
        self.actor: dict[str, Any] = {}
        self.environment = "prod"

    def run(self, prompt: str) -> ProductionIncidentTranscript:
        if self.runtime is None:
            raise RuntimeError("runtime.required")
        return self._run_with_caller(
            caller=lambda tool_name, tool_input, decisions, results: self._call_runtime(
                tool_name,
                tool_input,
                decisions,
                results,
            ),
            registration="registered",
        )

    def run_unregistered(self, prompt: str, direct_tools: dict[str, Any]) -> ProductionIncidentTranscript:
        return self._run_with_caller(
            caller=lambda tool_name, tool_input, decisions, results: self._call_direct(
                tool_name,
                tool_input,
                direct_tools,
                decisions,
                results,
            ),
            registration="unregistered",
        )

    def _run_with_caller(self, caller: Any, registration: str) -> ProductionIncidentTranscript:
        phases = ["intake"]
        decisions = [f"intake:{self.service}"]
        results: list[ToolResult] = []

        phases.append("investigate")
        status = caller("read_deployment_status", {"service": self.service}, decisions, results)
        logs = caller("inspect_error_logs", {"service": self.service, "window_minutes": 15}, decisions, results)
        flag = caller("query_feature_flag", {"flag": self.feature_flag}, decisions, results)
        diagnostics = caller("run_diagnostics", {"service": self.service}, decisions, results)

        phases.append("diagnose")
        findings = self._findings(status, logs, flag, diagnostics)
        decisions.append("diagnosis:rollback_candidate")

        phases.append("remediate")
        rollback = caller(
            "propose_rollback",
            {
                "service": self.service,
                "target_version": "2026.06.21.2",
                "reason": "latency spike after high-rollout checkout router release",
            },
            decisions,
            results,
        )

        phases.append("guardrail")
        hotfix = caller("apply_hotfix", {"service": self.service, "patch_id": "unreviewed-hotfix"}, decisions, results)
        if hotfix.status != "success":
            decisions.append(f"blocked:{hotfix.error or hotfix.status}")

        phases.append("summarize")
        decisions.append("summary:ready_for_human_review")
        remediation = {
            "approved_action": "rollback" if rollback.status == "success" else None,
            "approved_ticket": (rollback.output or {}).get("ticket") if isinstance(rollback.output, dict) else None,
            "blocked_action": "apply_hotfix" if hotfix.status != "success" else None,
            "blocked_reason": hotfix.error,
        }
        status_text = "completed" if all(result.status == "success" for result in results) else "completed_with_denial"
        return ProductionIncidentTranscript(
            status=status_text,
            decisions=decisions,
            phases=phases,
            findings=findings,
            remediation=remediation,
            registration=registration,
            tool_results=results,
            audit_events=[] if registration == "unregistered" else [],
            error=hotfix.error if hotfix.status != "success" else None,
        )

    def _call_runtime(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        decisions: list[str],
        results: list[ToolResult],
    ) -> ToolResult:
        decisions.append(f"call:{tool_name}")
        assert self.runtime is not None
        result = self.runtime.call_tool(tool_name, tool_input, actor=self.actor, environment=self.environment)
        results.append(result)
        return result

    def _call_direct(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        direct_tools: dict[str, Any],
        decisions: list[str],
        results: list[ToolResult],
    ) -> ToolResult:
        decisions.append(f"call:{tool_name}")
        direct_tool = direct_tools.get(tool_name)
        if direct_tool is None:
            result = ToolResult(tool_call_id=f"direct:{tool_name}", status="denied", error="tool.missing", run_id=None)
            results.append(result)
            return result
        try:
            output = direct_tool(**tool_input)
        except Exception as error:
            result = ToolResult(
                tool_call_id=f"direct:{tool_name}",
                status="failed",
                error=error.__class__.__name__,
                run_id=None,
            )
            results.append(result)
            return result
        result = ToolResult(tool_call_id=f"direct:{tool_name}", output=output, status="success", run_id=None)
        results.append(result)
        return result

    def _findings(
        self,
        status: ToolResult,
        logs: ToolResult,
        flag: ToolResult,
        diagnostics: ToolResult,
    ) -> dict[str, Any]:
        status_output = status.output if isinstance(status.output, dict) else {}
        log_output = logs.output if isinstance(logs.output, dict) else {}
        flag_output = flag.output if isinstance(flag.output, dict) else {}
        return {
            "impact": f"{self.service} degraded in {status_output.get('region', 'unknown')}",
            "current_version": status_output.get("version"),
            "signals": log_output.get("signals", []),
            "feature_flag": {
                "name": flag_output.get("flag", self.feature_flag),
                "enabled": flag_output.get("enabled"),
                "rollout": flag_output.get("rollout"),
            },
            "sandbox_diagnostics": diagnostics.output,
            "suspected_cause": "high rollout feature flag increased dependency latency",
        }
