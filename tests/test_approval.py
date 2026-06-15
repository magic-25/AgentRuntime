from agent_runtime.approval.cli import CliApprovalProvider
from agent_runtime.core.models import ApprovalRequest


def test_cli_approval_provider_approves_yes_input():
    provider = CliApprovalProvider(input_func=lambda _: "yes")

    decision = provider.request(_request())

    assert decision.approved is True


def test_cli_approval_provider_rejects_default_input():
    provider = CliApprovalProvider(input_func=lambda _: "")

    decision = provider.request(_request())

    assert decision.approved is False


def test_cli_approval_prompt_includes_risk_context():
    prompts: list[str] = []
    provider = CliApprovalProvider(input_func=lambda prompt: prompts.append(prompt) or "yes")

    provider.request(
        ApprovalRequest(
            approval_id="appr_1",
            run_id="run_1",
            tool_call_id="tc_1",
            actor={"id": "alice"},
            environment="prod",
            tool_name="danger",
            reason="requires approval",
            input_summary={"path": "/tmp/report.txt"},
            policy_rule_id="prod-danger",
            risk_level="high",
        )
    )

    prompt = prompts[0]
    assert "danger" in prompt
    assert "high" in prompt
    assert "prod" in prompt
    assert "/tmp/report.txt" in prompt
    assert "prod-danger" in prompt


def _request() -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="appr_1",
        run_id="run_1",
        tool_call_id="tc_1",
        actor={"id": "alice"},
        environment="prod",
        tool_name="danger",
        reason="requires approval",
        input_summary={},
        policy_rule_id="rule_1",
        risk_level="medium",
    )
