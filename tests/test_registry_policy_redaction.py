from agent_runtime.core.registry import ToolRegistry
from agent_runtime.policy.engine import PolicyEngine
from agent_runtime.guard.redaction import redact_secrets


def test_registry_registers_python_function_tool():
    registry = ToolRegistry()

    @registry.tool(name="echo", description="Echo input")
    def echo(value: str) -> str:
        return value

    definition = registry.get("echo")

    assert definition.name == "echo"
    assert definition.executor_kind == "in_process"
    assert registry.callable_for("echo")("hello") == "hello"


def test_policy_denies_unknown_tool_by_default():
    registry = ToolRegistry()
    engine = PolicyEngine({"default_decision": "deny", "rules": []}, registry)

    decision = engine.evaluate(tool_name="missing", environment="dev", actor={})

    assert decision.decision == "deny"
    assert decision.reason == "tool.unknown"


def test_policy_supports_allow_deny_and_require_approval():
    registry = ToolRegistry()

    @registry.tool(name="read_customer")
    def read_customer() -> dict:
        return {}

    engine = PolicyEngine(
        {
            "default_decision": "deny",
            "rules": [
                {"id": "dev-read", "environment": "dev", "tool": "read_customer", "effect": "allow"},
                {"id": "prod-read", "environment": "prod", "tool": "read_customer", "effect": "require_approval"},
                {"id": "deny-danger", "environment": "prod", "tool": "danger", "effect": "deny"},
            ],
        },
        registry,
    )

    assert engine.evaluate("read_customer", "dev", {}).decision == "allow"
    assert engine.evaluate("read_customer", "prod", {}).decision == "require_approval"
    assert engine.evaluate("danger", "prod", {}).decision == "deny"


def test_redaction_removes_common_secret_values():
    payload = {
        "api_key": "sk-test-secret-value",
        "nested": {"password": "super-secret-password"},
        "safe": "visible",
    }

    redacted = redact_secrets(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["password"] == "[REDACTED]"
    assert redacted["safe"] == "visible"
