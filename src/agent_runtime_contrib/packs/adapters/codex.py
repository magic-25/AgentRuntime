from __future__ import annotations

from typing import Any

from agent_runtime_contrib.packs.adapters._base import TranslateOnlyAdapterPack
from agent_runtime_contrib.packs.base import AdapterTranslationError, RuntimeToolCall


class CodexAdapterPack(TranslateOnlyAdapterPack):
    source = "codex"

    def translate(self, payload: dict[str, Any]) -> RuntimeToolCall:
        if payload.get("kind") == "workspace_command":
            command = payload.get("command")
            if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
                raise AdapterTranslationError("adapter.arguments_invalid: command must be a string list")
            return RuntimeToolCall(
                tool_name="codex.workspace.command",
                arguments={
                    "command": command,
                    "cwd": payload.get("cwd", "."),
                    "write_scope": payload.get("write_scope"),
                },
                adapter_source=self.source,
            )
        return super().translate(payload)

    def sample_payload(self) -> dict:
        return {"kind": "workspace_command", "command": ["python", "-m", "pytest"], "cwd": ".", "write_scope": "."}
