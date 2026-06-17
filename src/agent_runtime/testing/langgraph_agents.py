from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime


@dataclass(frozen=True)
class LangGraphAgentTranscript:
    status: str
    registration: str
    decisions: list[str]
    raw_tool_name: str | None = None
    raw_arguments: dict[str, Any] = field(default_factory=dict)
    tool_results: list[ToolResult] = field(default_factory=list)
    audit_events: list[str] = field(default_factory=list)
    agent_id: str | None = None
    agent_metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class LangGraphToolCallingAgent:
    def __init__(self, runtime: AgentRuntime | None, graph: Any, actor: dict[str, Any], environment: str) -> None:
        self.runtime = runtime
        self.graph = graph
        self.actor = actor
        self.environment = environment

    def run(self, prompt: str) -> LangGraphAgentTranscript:
        tool_name, arguments = self.request_tool_call(prompt)
        if self.runtime is None:
            return LangGraphAgentTranscript(
                status="blocked",
                registration="unregistered",
                decisions=["graph:invoke", f"tool_call:{tool_name}", "blocked:runtime.required"],
                raw_tool_name=tool_name,
                raw_arguments=arguments,
                error="runtime.required",
            )
        result = self.runtime.call_tool(tool_name, arguments, actor=self.actor, environment=self.environment, adapter_source="langgraph")
        return LangGraphAgentTranscript(
            status="completed" if result.status == "success" else "blocked",
            registration="registered",
            decisions=["graph:invoke", f"tool_call:{tool_name}", f"runtime:{result.status}", "stop" if result.status == "success" else "blocked"],
            raw_tool_name=tool_name,
            raw_arguments=arguments,
            tool_results=[result],
            error=result.error,
        )

    def run_unregistered(self, prompt: str, direct_tools: dict[str, Any]) -> LangGraphAgentTranscript:
        tool_name, arguments = self.request_tool_call(prompt)
        if tool_name not in direct_tools:
            return LangGraphAgentTranscript(
                status="blocked",
                registration="unregistered",
                decisions=["graph:invoke", f"tool_call:{tool_name}", "blocked:tool.missing"],
                raw_tool_name=tool_name,
                raw_arguments=arguments,
                error="tool.missing",
            )
        output = direct_tools[tool_name](**arguments)
        return LangGraphAgentTranscript(
            status="completed",
            registration="unregistered",
            decisions=["graph:invoke", f"tool_call:{tool_name}", "direct:success", "stop"],
            raw_tool_name=tool_name,
            raw_arguments=arguments,
            tool_results=[ToolResult(tool_call_id="direct", output=output, status="success", run_id=None)],
            audit_events=[],
        )

    def request_tool_call(self, prompt: str) -> tuple[str, dict[str, Any]]:
        output = self.graph.invoke({"message": prompt})
        tool_name = output.get("tool_name")
        arguments = output.get("arguments", {})
        if not tool_name:
            raise ValueError("langgraph.tool_name_missing")
        if not isinstance(arguments, dict):
            raise ValueError("langgraph.arguments_invalid")
        return tool_name, arguments
