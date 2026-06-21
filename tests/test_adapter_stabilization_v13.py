import pytest

from agent_runtime_contrib.packs.adapters.anthropic import AnthropicAdapterPack
from agent_runtime_contrib.packs.adapters.codex import CodexAdapterPack
from agent_runtime_contrib.packs.adapters.langgraph import LangGraphAdapterPack
from agent_runtime_contrib.packs.adapters.mcp import MCPAdapterPack
from agent_runtime_contrib.packs.adapters.openai import OpenAIAdapterPack
from agent_runtime_contrib.packs.adapters._base import preserve_runtime_status
from agent_runtime_contrib.packs.base import AdapterTranslationError


def test_stable_candidate_adapters_translate_provider_specific_tool_call_shapes():
    openai_call = OpenAIAdapterPack().translate(
        {"type": "function_call", "call_id": "call_1", "name": "echo", "arguments": '{"value":"openai"}'}
    )
    anthropic_call = AnthropicAdapterPack().translate(
        {"type": "tool_use", "id": "toolu_1", "name": "echo", "input": {"value": "anthropic"}}
    )
    langgraph_call = LangGraphAdapterPack().translate({"tool": "echo", "input": {"value": "langgraph"}})
    mcp_call = MCPAdapterPack().translate(
        {"method": "tools/call", "params": {"name": "echo", "arguments": {"value": "mcp"}}}
    )
    codex_call = CodexAdapterPack().translate(
        {"kind": "workspace_command", "command": ["python", "-m", "pytest"], "cwd": ".", "write_scope": "."}
    )

    assert openai_call.arguments == {"value": "openai"}
    assert anthropic_call.arguments == {"value": "anthropic"}
    assert langgraph_call.arguments == {"value": "langgraph"}
    assert mcp_call.arguments == {"value": "mcp"}
    assert codex_call.tool_name == "codex.workspace.command"
    assert codex_call.arguments["command"] == ["python", "-m", "pytest"]
    assert {call.adapter_source for call in [openai_call, anthropic_call, langgraph_call, mcp_call, codex_call]} == {
        "openai",
        "anthropic",
        "langgraph",
        "mcp",
        "codex",
    }


def test_stable_candidate_adapter_metadata_and_no_capability_grants():
    packs = [OpenAIAdapterPack(), AnthropicAdapterPack(), LangGraphAdapterPack(), MCPAdapterPack(), CodexAdapterPack()]

    for pack in packs:
        call = pack.translate(pack.sample_payload())
        assert pack.metadata.support_level == "stable_candidate"
        assert call.capabilities_granted == []
        assert not hasattr(pack, "execute")


def test_mcp_discovery_does_not_grant_capabilities():
    discovery = MCPAdapterPack().discover({"tools": [{"name": "shell"}, {"name": "read_file"}]})

    assert discovery.tool_names == ["shell", "read_file"]
    assert discovery.capabilities_granted == []


def test_adapter_preserves_runtime_failure_statuses():
    for status in ["deny", "approval_required", "runtime_error", "sandbox_required"]:
        assert preserve_runtime_status(status) == status

    with pytest.raises(AdapterTranslationError, match="failure status"):
        preserve_runtime_status("success")


def test_openai_adapter_rejects_invalid_json_arguments():
    with pytest.raises(AdapterTranslationError, match="arguments"):
        OpenAIAdapterPack().translate({"name": "echo", "arguments": "{not-json"})
