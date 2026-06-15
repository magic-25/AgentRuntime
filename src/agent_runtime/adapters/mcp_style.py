from __future__ import annotations

from typing import Any

from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime


class MCPStyleAdapter:
    source = "mcp_style"

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def call_tool(self, request: dict[str, Any], actor: dict[str, Any], environment: str) -> ToolResult:
        return self.runtime.call_tool(
            request["name"],
            request.get("arguments", {}),
            actor=actor,
            environment=environment,
            adapter_source=self.source,
        )
