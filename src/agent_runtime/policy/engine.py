from __future__ import annotations

from typing import Any

from agent_runtime.core.models import PolicyDecision
from agent_runtime.core.registry import ToolRegistry


class PolicyEngine:
    def __init__(self, config: dict[str, Any], registry: ToolRegistry) -> None:
        self.config = config
        self.registry = registry

    def evaluate(self, tool_name: str, environment: str, actor: dict[str, Any]) -> PolicyDecision:
        if not self.registry.has(tool_name):
            return PolicyDecision(
                decision="deny",
                reason="tool.unknown",
                environment=environment,
                actor=actor,
            )

        definition = self.registry.get(tool_name)
        required_capabilities = definition.capabilities_required or [f"tool.invoke:{tool_name}"]
        capability_rules = [
            rule for rule in self.config.get("rules", []) if "capabilities" in rule and self._environment_matches(rule, environment)
        ]
        if capability_rules:
            return self._evaluate_capabilities(required_capabilities, capability_rules, environment, actor)

        matching_rules = [
            rule for rule in self.config.get("rules", []) if rule.get("tool") == tool_name and self._environment_matches(rule, environment)
        ]
        for rule in matching_rules:
            if rule.get("effect") == "deny":
                return self._decision(rule, environment, actor)

        for effect in ("require_approval", "allow"):
            for rule in matching_rules:
                if rule.get("effect") == effect:
                    return self._decision(rule, environment, actor)

        return PolicyDecision(
            decision=self.config.get("default_decision", "deny"),
            reason="default_decision",
            environment=environment,
            actor=actor,
        )

    def _evaluate_capabilities(
        self,
        required_capabilities: list[str],
        rules: list[dict[str, Any]],
        environment: str,
        actor: dict[str, Any],
    ) -> PolicyDecision:
        final_allow: PolicyDecision | None = None
        final_approval: PolicyDecision | None = None

        for capability in required_capabilities:
            deny_rule = self._first_matching_capability_rule(rules, capability, "deny")
            if deny_rule is not None:
                return self._decision(deny_rule, environment, actor, capability=capability)

            approval_rule = self._first_matching_capability_rule(rules, capability, "require_approval")
            if approval_rule is not None:
                final_approval = self._decision(approval_rule, environment, actor, capability=capability)
                continue

            allow_rule = self._first_matching_capability_rule(rules, capability, "allow")
            if allow_rule is None:
                return PolicyDecision(
                    decision="deny",
                    reason="capability.unknown",
                    capability=capability,
                    environment=environment,
                    actor=actor,
                )
            final_allow = self._decision(allow_rule, environment, actor, capability=capability)

        return final_approval or final_allow or PolicyDecision(
            decision=self.config.get("default_decision", "deny"),
            reason="default_decision",
            environment=environment,
            actor=actor,
        )

    def _first_matching_capability_rule(
        self,
        rules: list[dict[str, Any]],
        capability: str,
        effect: str,
    ) -> dict[str, Any] | None:
        for rule in rules:
            if rule.get("effect") != effect:
                continue
            if any(_capability_matches(pattern, capability) for pattern in rule.get("capabilities", [])):
                return rule
        return None

    def _decision(
        self,
        rule: dict[str, Any],
        environment: str,
        actor: dict[str, Any],
        capability: str | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision=rule["effect"],
            reason="matched_rule",
            rule_id=rule.get("id"),
            capability=capability,
            environment=environment,
            actor=actor,
        )

    def _environment_matches(self, rule: dict[str, Any], environment: str) -> bool:
        return rule.get("environment", environment) == environment


def _capability_matches(pattern: str, capability: str) -> bool:
    if pattern == capability:
        return True
    if pattern.endswith("*"):
        return capability.startswith(pattern[:-1])
    return False
