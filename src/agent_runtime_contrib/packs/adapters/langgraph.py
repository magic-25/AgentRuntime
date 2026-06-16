from __future__ import annotations

from agent_runtime_contrib.packs.adapters._base import TranslateOnlyAdapterPack


class LangGraphAdapterPack(TranslateOnlyAdapterPack):
    source = "langgraph"
    payload_tool_field = "tool"
    payload_arguments_field = "input"
