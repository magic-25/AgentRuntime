from __future__ import annotations

from agent_runtime_contrib.packs.adapters._base import TranslateOnlyAdapterPack


class OpenAIAdapterPack(TranslateOnlyAdapterPack):
    source = "openai"

    def sample_payload(self) -> dict:
        return {"type": "function_call", "call_id": "call_sample", "name": "echo", "arguments": '{"value":"openai"}'}
