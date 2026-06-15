from agent_runtime.core.models import (
    AuditEvent,
    PolicyDecision,
    ToolCall,
    ToolDefinition,
    ToolResult,
)


def test_tool_call_serializes_required_fields():
    call = ToolCall(
        tool_call_id="tc_1",
        run_id="run_1",
        tool_name="lookup",
        input={"customer_id": "cus_123"},
        actor={"type": "user", "id": "alice"},
        environment="dev",
    )

    payload = call.to_dict()

    assert payload["tool_call_id"] == "tc_1"
    assert payload["run_id"] == "run_1"
    assert payload["tool_name"] == "lookup"
    assert payload["environment"] == "dev"


def test_core_models_include_preview_contract_fields():
    tool = ToolDefinition(
        name="lookup",
        description="Lookup customer",
        capabilities_required=["tool.invoke:lookup"],
    )
    decision = PolicyDecision(decision="allow", reason="matched", rule_id="dev-allow")
    result = ToolResult(tool_call_id="tc_1", output={"ok": True}, status="success")
    event = AuditEvent(event_type="ToolCallRequested", run_id="run_1", tool_call_id="tc_1")

    assert tool.name == "lookup"
    assert decision.decision == "allow"
    assert result.status == "success"
    assert event.to_dict()["event_type"] == "ToolCallRequested"
