from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from agent_runtime_contrib.packs.base import AdapterTranslationError, PackMetadata, RuntimeToolCall


@dataclass(frozen=True)
class AdapterDiscovery:
    tool_names: list[str]
    capabilities_granted: list[str] = field(default_factory=list)


FAILURE_STATUSES = {"deny", "approval_required", "runtime_error", "sandbox_required"}


def preserve_runtime_status(status: str) -> str:
    if status not in FAILURE_STATUSES:
        raise AdapterTranslationError("failure status must be preserved and cannot be rewritten")
    return status


class TranslateOnlyAdapterPack:
    source: str
    payload_tool_field = "name"
    payload_arguments_field = "arguments"
    support_level = "stable_candidate"

    def __init__(self) -> None:
        self.metadata = PackMetadata(
            pack_id=self.source,
            kind="adapter",
            support_level=self.support_level,
            dependencies_group=self.source,
        )

    def translate(self, payload: dict[str, Any]) -> RuntimeToolCall:
        tool_name, arguments = self._extract_tool_call(payload)
        return RuntimeToolCall(tool_name=tool_name, arguments=arguments, adapter_source=self.source)

    def sample_payload(self) -> dict[str, Any]:
        return {self.payload_tool_field: "echo", self.payload_arguments_field: {"value": self.source}}

    def _extract_tool_call(self, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        tool_name = payload.get(self.payload_tool_field)
        if not tool_name:
            raise AdapterTranslationError("adapter.tool_name_missing: tool name is required")
        arguments = _coerce_arguments(payload.get(self.payload_arguments_field, {}))
        return tool_name, arguments


def _coerce_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise AdapterTranslationError("adapter.arguments_invalid: arguments must be valid JSON") from error
        if not isinstance(arguments, dict):
            raise AdapterTranslationError("adapter.arguments_invalid: arguments must decode to an object")
        return arguments
    if not isinstance(arguments, dict):
        raise AdapterTranslationError("adapter.arguments_invalid: arguments must be an object")
    return arguments
