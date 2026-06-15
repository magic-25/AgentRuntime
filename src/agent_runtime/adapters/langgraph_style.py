from __future__ import annotations

from typing import Any

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime


class LangGraphStyleAdapter:
    source = "langgraph_style"

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def invoke_node(self, node: dict[str, Any], actor: dict[str, Any], environment: str) -> ToolResult:
        return self.runtime.call_tool(
            node["tool"],
            node.get("input", {}),
            actor=actor,
            environment=environment,
            adapter_source=self.source,
        )
