import json
import sys

from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.testing.agents import (
    CodeCIRealAgent,
    MCPStyleRealAgent,
    OpsDiagnosticRealAgent,
    ScriptedToolCallingAgent,
)
from agent_runtime_contrib.packs.adapters.mcp import MCPAdapterPack
from agent_runtime_contrib.pilot.code_ci import CodeCIPilot


def _audit_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_scripted_tool_calling_agent_runs_loop_through_runtime_and_stops(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [
                {
                    "id": "allow-echo",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:echo", "message.echo"],
                }
            ],
        }
    )

    @runtime.tool(name="echo", capabilities_required=["tool.invoke:echo", "message.echo"])
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    agent = ScriptedToolCallingAgent(
        runtime=runtime,
        actor={"id": "agent-1"},
        environment="dev",
        steps=[{"tool": "echo", "input": {"message": "hello"}}],
    )

    transcript = agent.run()

    assert transcript.status == "completed"
    assert transcript.tool_results[0].output == {"message": "hello"}
    assert transcript.decisions == ["call:echo", "stop"]
    event_types = [event["event_type"] for event in _audit_events(audit_path)]
    assert "PolicyEvaluated" in event_types
    assert "ToolExecutionFinished" in event_types


def test_code_ci_real_agent_runs_allowed_test_and_stops_on_denied_commit(tmp_path):
    command = [sys.executable, "-c", "print('agent-ci-ok')"]
    pilot = CodeCIPilot(allowed_commands=[command])
    agent = CodeCIRealAgent(repo_path=tmp_path, pilot=pilot, write_scope=tmp_path)

    transcript = agent.run([command, ["git", "commit"]])

    assert transcript.status == "blocked"
    assert transcript.decisions == ["run:python", "blocked:command.denied"]
    assert transcript.pilot_reports[0].status == "success"
    assert transcript.pilot_reports[1].status == "denied"
    assert transcript.pilot_reports[1].executed_commands == []


def test_ops_diagnostic_real_agent_runs_readonly_command_and_records_denied_write(tmp_path):
    audit_path = tmp_path / "ops-audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [
                {
                    "id": "ops-readonly",
                    "environment": "staging",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:ops_status", "ops.read"],
                }
            ],
        }
    )
    runtime.command_tool(
        name="ops_status",
        argv=[sys.executable, "-c", "print('status=ok')"],
        cwd=tmp_path,
        timeout_ms=2000,
        stdout_limit_bytes=64,
        stderr_limit_bytes=64,
        capabilities_required=["tool.invoke:ops_status", "ops.read"],
    )

    agent = OpsDiagnosticRealAgent(runtime=runtime, actor={"id": "ops-agent"}, environment="staging")

    transcript = agent.run()

    assert transcript.status == "completed_with_denial"
    assert transcript.tool_results[0].status == "success"
    assert transcript.tool_results[1].status == "denied"
    assert transcript.decisions == ["call:ops_status", "call:ops_restart", "stop"]


def test_mcp_style_real_agent_translates_tool_call_before_runtime_execution(tmp_path):
    audit_path = tmp_path / "mcp-audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [{"id": "allow-mcp", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: str) -> dict[str, str]:
        return {"value": value}

    agent = MCPStyleRealAgent(
        runtime=runtime,
        adapter=MCPAdapterPack(),
        actor={"id": "mcp-agent"},
        environment="dev",
    )

    transcript = agent.run()

    assert transcript.status == "completed"
    assert transcript.adapter_source == "mcp"
    assert transcript.capabilities_granted == []
    assert transcript.tool_results[0].status == "success"
    assert transcript.decisions == ["translate:mcp", "call:echo", "stop"]
