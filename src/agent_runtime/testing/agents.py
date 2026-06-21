from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime_contrib.pilot.code_ci import CodeCIPilot
from agent_runtime_contrib.pilot.report import PilotReport


@dataclass(frozen=True)
class RuntimeAgentTranscript:
    status: str
    decisions: list[str]
    tool_results: list[ToolResult] = field(default_factory=list)


@dataclass(frozen=True)
class CodeCIAgentTranscript:
    status: str
    decisions: list[str]
    pilot_reports: list[PilotReport] = field(default_factory=list)


@dataclass(frozen=True)
class MCPStyleAgentTranscript(RuntimeAgentTranscript):
    adapter_source: str = ""
    capabilities_granted: list[str] = field(default_factory=list)


class ScriptedToolCallingAgent:
    def __init__(
        self,
        runtime: AgentRuntime,
        actor: dict[str, Any],
        environment: str,
        steps: list[dict[str, Any]],
    ) -> None:
        self.runtime = runtime
        self.actor = actor
        self.environment = environment
        self.steps = steps

    def run(self) -> RuntimeAgentTranscript:
        decisions: list[str] = []
        results: list[ToolResult] = []
        for step in self.steps:
            tool_name = str(step["tool"])
            decisions.append(f"call:{tool_name}")
            result = self.runtime.call_tool(
                tool_name,
                dict(step.get("input", {})),
                actor=self.actor,
                environment=self.environment,
            )
            results.append(result)
            if result.status not in {"success", "approved"}:
                decisions.append(f"blocked:{result.error or result.status}")
                return RuntimeAgentTranscript(status="blocked", decisions=decisions, tool_results=results)
        decisions.append("stop")
        return RuntimeAgentTranscript(status="completed", decisions=decisions, tool_results=results)


class CodeCIRealAgent:
    def __init__(self, repo_path: str | Path, pilot: CodeCIPilot, write_scope: str | Path) -> None:
        self.repo_path = Path(repo_path)
        self.pilot = pilot
        self.write_scope = Path(write_scope)

    def run(self, planned_commands: list[list[str]]) -> CodeCIAgentTranscript:
        decisions: list[str] = []
        reports: list[PilotReport] = []
        for command in planned_commands:
            report = self.pilot.run(repo_path=self.repo_path, command=command, write_scope=self.write_scope)
            reports.append(report)
            if report.status == "success":
                decisions.append(f"run:{Path(command[0]).name}")
                continue
            decisions.append(f"blocked:{report.error or report.status}")
            return CodeCIAgentTranscript(status="blocked", decisions=decisions, pilot_reports=reports)
        decisions.append("stop")
        return CodeCIAgentTranscript(status="completed", decisions=decisions, pilot_reports=reports)


class OpsDiagnosticRealAgent:
    def __init__(self, runtime: AgentRuntime, actor: dict[str, Any], environment: str) -> None:
        self.runtime = runtime
        self.actor = actor
        self.environment = environment

    def run(self) -> RuntimeAgentTranscript:
        decisions: list[str] = []
        results: list[ToolResult] = []
        for tool_name in ["ops_status", "ops_restart"]:
            decisions.append(f"call:{tool_name}")
            result = self.runtime.call_tool(tool_name, {}, actor=self.actor, environment=self.environment)
            results.append(result)
        decisions.append("stop")
        status = "completed" if all(result.status == "success" for result in results) else "completed_with_denial"
        return RuntimeAgentTranscript(status=status, decisions=decisions, tool_results=results)


class MCPStyleRealAgent:
    def __init__(self, runtime: AgentRuntime, adapter: Any, actor: dict[str, Any], environment: str) -> None:
        self.runtime = runtime
        self.adapter = adapter
        self.actor = actor
        self.environment = environment

    def run(self) -> MCPStyleAgentTranscript:
        call = self.adapter.translate(self.adapter.sample_payload())
        decisions = [f"translate:{call.adapter_source}", f"call:{call.tool_name}"]
        result = self.runtime.call_tool(call.tool_name, call.arguments, actor=self.actor, environment=self.environment)
        decisions.append("stop")
        return MCPStyleAgentTranscript(
            status="completed" if result.status == "success" else "blocked",
            decisions=decisions,
            tool_results=[result],
            adapter_source=call.adapter_source,
            capabilities_granted=list(call.capabilities_granted),
        )
