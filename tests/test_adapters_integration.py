import json

from agent_runtime import AgentRuntime
from agent_runtime.adapters.langgraph_style import LangGraphStyleAdapter
from agent_runtime.adapters.mcp_style import MCPStyleAdapter
from agent_runtime.adapters.openai_style import OpenAIStyleAdapter


def _runtime(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [
                {
                    "id": "allow-echo",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:echo"],
                }
            ],
        }
    )

    @runtime.tool(name="echo", capabilities_required=["tool.invoke:echo"])
    def echo(value: str) -> str:
        return value

    return runtime, audit_path


def test_openai_style_adapter_calls_runtime_core_and_records_source(tmp_path):
    runtime, audit_path = _runtime(tmp_path)
    adapter = OpenAIStyleAdapter(runtime)

    result = adapter.call(
        {"type": "function_call", "name": "echo", "arguments": {"value": "hello"}},
        actor={"id": "alice"},
        environment="dev",
    )

    assert result.output == "hello"
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    requested = next(event for event in events if event["event_type"] == "ToolCallRequested")
    trace_started = next(event for event in events if event["event_type"] == "TraceSpanStarted")
    assert requested["payload"]["adapter_source"] == "openai_style"
    assert trace_started["payload"]["adapter_source"] == "openai_style"


def test_langgraph_style_adapter_reuses_runtime_tool(tmp_path):
    runtime, _audit_path = _runtime(tmp_path)
    adapter = LangGraphStyleAdapter(runtime)

    result = adapter.invoke_node({"tool": "echo", "input": {"value": "from graph"}}, actor={}, environment="dev")

    assert result.output == "from graph"


def test_mcp_style_adapter_cannot_grant_capability(tmp_path):
    runtime, _audit_path = _runtime(tmp_path)
    adapter = MCPStyleAdapter(runtime)

    result = adapter.call_tool(
        {
            "name": "echo",
            "arguments": {"value": "hello"},
            "capabilities": ["network.connect:*"],
        },
        actor={},
        environment="dev",
    )

    assert result.status == "success"

    denied = adapter.call_tool(
        {
            "name": "missing",
            "arguments": {},
            "capabilities": ["tool.invoke:missing"],
        },
        actor={},
        environment="dev",
    )
    assert denied.status == "denied"
