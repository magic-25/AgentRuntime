from agent_runtime.approval.base import CallbackApprovalProvider
from agent_runtime.cli.main import main
from agent_runtime.core.models import ApprovalDecision
from agent_runtime.core.runtime import AgentRuntime


def test_callback_approval_provider_can_approve_reject_and_timeout():
    approved = CallbackApprovalProvider(lambda request: ApprovalDecision(approved=True, reason="ok"))
    rejected = CallbackApprovalProvider(lambda request: ApprovalDecision(approved=False, reason="no"))
    timed_out = CallbackApprovalProvider.timeout()

    request = _approval_request()

    assert approved.request(request).approved is True
    assert rejected.request(request).approved is False
    assert timed_out.request(request).timed_out is True


def test_policy_debug_cli_explains_matching_rule(tmp_path, capsys):
    config_path = tmp_path / "agent-runtime.json"
    config_path.write_text(
        """
{
  "default_decision": "deny",
  "tools": {
    "echo": {"capabilities_required": ["tool.invoke:echo"]}
  },
  "rules": [
    {"id": "allow-echo", "environment": "staging", "effect": "allow", "capabilities": ["tool.invoke:echo"]}
  ]
}
""",
        encoding="utf-8",
    )

    exit_code = main(["policy", "debug", "--path", str(config_path), "--tool", "echo", "--environment", "staging"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "allow" in output
    assert "allow-echo" in output
    assert "tool.invoke:echo" in output


def _approval_request():
    from agent_runtime.core.models import ApprovalRequest

    return ApprovalRequest(
        approval_id="appr_1",
        run_id="run_1",
        tool_call_id="tc_1",
        actor={},
        environment="prod",
        tool_name="echo",
        reason="test",
        input_summary={},
    )
