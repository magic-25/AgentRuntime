import pytest

from agent_runtime_contrib.packs.adapters.anthropic import AnthropicAdapterPack
from agent_runtime_contrib.packs.adapters.codex import CodexAdapterPack
from agent_runtime_contrib.packs.adapters.langgraph import LangGraphAdapterPack
from agent_runtime_contrib.packs.adapters.mcp import MCPAdapterPack
from agent_runtime_contrib.packs.adapters.openai import OpenAIAdapterPack
from agent_runtime_contrib.packs.base import AdapterTranslationError


def test_openai_adapter_pack_translates_payload_without_granting_capability():
    pack = OpenAIAdapterPack()

    call = pack.translate(
        {
            "name": "echo",
            "arguments": {"value": "hello"},
            "capabilities": ["network.connect:*"],
        }
    )

    assert call.tool_name == "echo"
    assert call.arguments == {"value": "hello"}
    assert call.adapter_source == "openai"
    assert call.capabilities_granted == []


def test_langgraph_and_mcp_adapter_packs_translate_existing_payload_shapes():
    graph_call = LangGraphAdapterPack().translate({"tool": "echo", "input": {"value": "graph"}})
    mcp_call = MCPAdapterPack().translate({"name": "echo", "arguments": {"value": "mcp"}})

    assert graph_call.tool_name == "echo"
    assert graph_call.arguments == {"value": "graph"}
    assert graph_call.adapter_source == "langgraph"
    assert mcp_call.tool_name == "echo"
    assert mcp_call.arguments == {"value": "mcp"}
    assert mcp_call.adapter_source == "mcp"


def test_adapter_pack_rejects_payload_without_tool_name():
    with pytest.raises(AdapterTranslationError, match="tool name"):
        OpenAIAdapterPack().translate({"arguments": {}})


def test_anthropic_and_codex_packs_are_stable_candidate_adapters():
    anthropic = AnthropicAdapterPack()
    codex = CodexAdapterPack()

    assert anthropic.metadata.pack_id == "anthropic"
    assert codex.metadata.pack_id == "codex"
    assert anthropic.metadata.support_level == "stable_candidate"
    assert codex.metadata.support_level == "stable_candidate"
