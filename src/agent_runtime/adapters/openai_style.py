from __future__ import annotations

from typing import Any

from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.core.models import ToolResult


class OpenAIStyleAdapter:
    source = "openai_style"

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def call(self, tool_call: dict[str, Any], actor: dict[str, Any], environment: str) -> ToolResult:
        return self.runtime.call_tool(
            tool_call["name"],
            tool_call.get("arguments", {}),
            actor=actor,
            environment=environment,
            adapter_source=self.source,
        )
