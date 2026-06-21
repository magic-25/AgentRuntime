from __future__ import annotations

from agent_runtime_contrib.packs.adapters._base import TranslateOnlyAdapterPack


class AnthropicAdapterPack(TranslateOnlyAdapterPack):
    source = "anthropic"
    payload_arguments_field = "input"

    def sample_payload(self) -> dict:
        return {"type": "tool_use", "id": "toolu_sample", "name": "echo", "input": {"value": "anthropic"}}
