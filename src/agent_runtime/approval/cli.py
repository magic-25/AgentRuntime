from __future__ import annotations

from agent_runtime.approval.base import ApprovalProvider
from agent_runtime.core.models import ApprovalDecision, ApprovalRequest


class CliApprovalProvider(ApprovalProvider):
    def __init__(self, input_func=input) -> None:
        self.input_func = input_func

    def request(self, request: ApprovalRequest) -> ApprovalDecision:
        answer = self.input_func(
            "\n".join(
                [
                    f"Tool: {request.tool_name}",
                    f"Risk: {request.risk_level}",
                    f"Environment: {request.environment}",
                    f"Policy rule: {request.policy_rule_id or 'unknown'}",
                    f"Input summary: {request.input_summary}",
                    "Approve? [y/N] ",
                ]
            )
        )
        approved = answer.strip().lower() in {"y", "yes"}
        return ApprovalDecision(approved=approved, reason="cli")
