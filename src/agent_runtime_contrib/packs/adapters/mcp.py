from __future__ import annotations

from typing import Any

from agent_runtime_contrib.packs.adapters._base import AdapterDiscovery, TranslateOnlyAdapterPack, _coerce_arguments
from agent_runtime_contrib.packs.base import AdapterTranslationError, RuntimeToolCall


class MCPAdapterPack(TranslateOnlyAdapterPack):
    source = "mcp"

    def translate(self, payload: dict[str, Any]) -> RuntimeToolCall:
        if payload.get("method") == "tools/call":
            params = payload.get("params", {})
            if not isinstance(params, dict):
                raise AdapterTranslationError("adapter.arguments_invalid: params must be an object")
            tool_name = params.get("name")
            if not tool_name:
                raise AdapterTranslationError("adapter.tool_name_missing: tool name is required")
            return RuntimeToolCall(
                tool_name=tool_name,
                arguments=_coerce_arguments(params.get("arguments", {})),
                adapter_source=self.source,
            )
        return super().translate(payload)

    def discover(self, payload: dict[str, Any]) -> AdapterDiscovery:
        tools = payload.get("tools", [])
        names = [item["name"] for item in tools if isinstance(item, dict) and isinstance(item.get("name"), str)]
        return AdapterDiscovery(tool_names=names)

    def sample_payload(self) -> dict:
        return {"method": "tools/call", "params": {"name": "echo", "arguments": {"value": "mcp"}}}
