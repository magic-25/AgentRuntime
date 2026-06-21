import json
from pathlib import Path

from agent_runtime_contrib.packs.adapters import (
    AnthropicAdapterPack,
    CodexAdapterPack,
    LangGraphAdapterPack,
    MCPAdapterPack,
    OpenAIAdapterPack,
)


ADAPTERS = {
    "anthropic": AnthropicAdapterPack,
    "codex": CodexAdapterPack,
    "langgraph": LangGraphAdapterPack,
    "mcp": MCPAdapterPack,
    "openai": OpenAIAdapterPack,
}


def test_adapter_payload_fixtures_cover_primary_stacks():
    fixture_dir = Path("tests/fixtures/adapter_payloads")
    fixture_paths = sorted(fixture_dir.glob("*.json"))

    assert {path.stem for path in fixture_paths} == set(ADAPTERS)

    for path in fixture_paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        adapter_id = fixture["adapter"]
        translated = ADAPTERS[adapter_id]().translate(fixture["payload"])

        assert translated.tool_name == fixture["expected"]["tool_name"]
        assert translated.arguments == fixture["expected"]["arguments"]
        assert translated.adapter_source == adapter_id
        assert translated.capabilities_granted == []
