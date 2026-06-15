from agent_runtime.core.registry import ToolRegistry
from agent_runtime.policy.engine import PolicyEngine


def test_policy_denies_unknown_capability_by_default():
    registry = ToolRegistry()

    @registry.tool(name="read_customer", capabilities_required=["tool.invoke:read_customer", "api.call:crm.GET./customers/123"])
    def read_customer() -> dict:
        return {}

    engine = PolicyEngine(
        {
            "version": 1,
            "default_decision": "deny",
            "rules": [
                {
                    "id": "allow-tool",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:read_customer"],
                }
            ],
        },
        registry,
    )

    decision = engine.evaluate("read_customer", "dev", {"id": "alice"})

    assert decision.decision == "deny"
    assert decision.reason == "capability.unknown"
    assert decision.capability == "api.call:crm.GET./customers/123"


def test_policy_allows_when_all_required_capabilities_are_allowed():
    registry = ToolRegistry()

    @registry.tool(name="read_customer", capabilities_required=["tool.invoke:read_customer", "api.call:crm.GET./customers/123"])
    def read_customer() -> dict:
        return {}

    engine = PolicyEngine(
        {
            "version": 1,
            "default_decision": "deny",
            "rules": [
                {
                    "id": "allow-dev-crm",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:read_customer", "api.call:crm.GET./customers/*"],
                }
            ],
        },
        registry,
    )

    decision = engine.evaluate("read_customer", "dev", {"id": "alice"})

    assert decision.decision == "allow"
    assert decision.rule_id == "allow-dev-crm"
    assert decision.capability == "api.call:crm.GET./customers/123"


def test_policy_deny_capability_overrides_allow():
    registry = ToolRegistry()

    @registry.tool(name="metadata", capabilities_required=["tool.invoke:metadata", "network.connect:169.254.169.254:80"])
    def metadata() -> dict:
        return {}

    engine = PolicyEngine(
        {
            "version": 1,
            "default_decision": "deny",
            "rules": [
                {"id": "allow-network", "environment": "prod", "effect": "allow", "capabilities": ["network.connect:*"]},
                {"id": "deny-metadata", "environment": "prod", "effect": "deny", "capabilities": ["network.connect:169.254.169.254:*"]},
                {"id": "allow-tool", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:metadata"]},
            ],
        },
        registry,
    )

    decision = engine.evaluate("metadata", "prod", {"id": "alice"})

    assert decision.decision == "deny"
    assert decision.rule_id == "deny-metadata"
    assert decision.capability == "network.connect:169.254.169.254:80"


def test_policy_requires_approval_for_matching_capability():
    registry = ToolRegistry()

    @registry.tool(name="write_customer", capabilities_required=["tool.invoke:write_customer", "api.call:crm.POST./customers/123"])
    def write_customer() -> dict:
        return {}

    engine = PolicyEngine(
        {
            "version": 1,
            "default_decision": "deny",
            "rules": [
                {"id": "allow-tool", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:write_customer"]},
                {
                    "id": "approve-prod-write",
                    "environment": "prod",
                    "effect": "require_approval",
                    "capabilities": ["api.call:crm.POST./customers/*"],
                },
            ],
        },
        registry,
    )

    decision = engine.evaluate("write_customer", "prod", {"id": "alice"})

    assert decision.decision == "require_approval"
    assert decision.rule_id == "approve-prod-write"
    assert decision.capability == "api.call:crm.POST./customers/123"
