import json
import sys

from agent_runtime.audit.verify import verify_audit_chain
from agent_runtime.control_plane.platform import (
    AppendOnlyAuditForwarder,
    PlatformPolicyBundle,
    PlatformRegistryContract,
    RunExporter,
    evaluate_platform_policy_state,
    validate_policy_bundle,
)
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime_contrib.adapter_conformance import AdapterConformanceRunner
from agent_runtime_contrib.pilot.code_ci import CodeCIPilot
from agent_runtime_contrib.sandbox_conformance import SandboxConformanceRunner, backend_for_name


def _audit_events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_scenario_local_python_agent_runtime_runs_tool_through_policy_and_audit(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [
                {
                    "id": "dev-echo",
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

    result = runtime.call_tool("echo", {"message": "hello"}, actor={"id": "dev-user"}, environment="dev")

    assert result.status == "success"
    assert result.output == {"message": "hello"}
    event_types = [event["event_type"] for event in _audit_events(audit_path)]
    assert "PolicyEvaluated" in event_types
    assert "ToolExecutionFinished" in event_types


def test_scenario_local_command_tool_governance_applies_env_allowlist_and_audit_chain(tmp_path):
    audit_path = tmp_path / "audit.jsonl"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "rules": [
                {
                    "id": "dev-command",
                    "environment": "dev",
                    "effect": "allow",
                    "capabilities": ["tool.invoke:check_status", "command.execute:python"],
                }
            ],
        }
    )
    runtime.command_tool(
        name="check_status",
        argv=[
            sys.executable,
            "-c",
            "import os; print('ALLOWED=' + os.environ.get('ALLOWED', '')); print('SECRET=' + os.environ.get('SECRET', ''))",
        ],
        cwd=tmp_path,
        env={"ALLOWED": "yes", "SECRET": "must-not-leak"},
        env_allowlist=["ALLOWED"],
        timeout_ms=2000,
        stdout_limit_bytes=128,
        stderr_limit_bytes=128,
        capabilities_required=["tool.invoke:check_status", "command.execute:python"],
    )

    result = runtime.call_tool("check_status", {}, actor={"id": "dev-user"}, environment="dev")

    assert result.status == "success"
    assert "ALLOWED=yes" in result.output["stdout"]
    assert "must-not-leak" not in result.output["stdout"]
    assert verify_audit_chain(audit_path, sink="jsonl").valid is True


def test_scenario_staging_internal_admin_agent_covers_approval_deny_observer_and_audit(tmp_path):
    from examples.staging_internal_admin_pilot import run_pilot

    result = run_pilot(tmp_path, reset=True)

    assert result["read_customer"].status == "success"
    assert result["approved_write"].status == "success"
    assert result["timed_out_write"].status == "rejected"
    assert result["timed_out_write"].error == "approval.timeout"
    assert result["unknown_prod_tool"].status == "denied"
    assert verify_audit_chain(result["audit_path"], sink="sqlite").valid is True
    observer = json.loads(result["observer_path"].read_text(encoding="utf-8"))
    assert observer["approval_requests"] == 2
    assert observer["approval_rejected"] == 1
    assert observer["denied"] == 1


def test_scenario_code_ci_agent_governance_allows_only_allowlisted_commands(tmp_path):
    command = [sys.executable, "-c", "print('scenario-ok')"]
    success_report = tmp_path / "code-ci-success.json"
    deny_report = tmp_path / "code-ci-deny.json"
    pilot = CodeCIPilot(allowed_commands=[command])

    success = pilot.run(repo_path=tmp_path, command=command, write_scope=tmp_path, report_path=success_report)
    denied = pilot.run(repo_path=tmp_path, command=["git", "commit"], write_scope=tmp_path, report_path=deny_report)

    assert success.status == "success"
    assert success.network_access is False
    assert success.commit_push_pr_denied is True
    assert success.audit_mode == "digest-only"
    assert denied.status == "denied"
    assert denied.error == "command.denied"
    assert denied.executed_commands == []


def test_scenario_adapter_replay_and_conformance_preserve_runtime_semantics():
    runner = AdapterConformanceRunner()

    conformance = runner.run_all()
    replay = runner.run_replay("code-ci", adapter_ids=["openai", "langgraph", "codex"])

    assert conformance.passed is True
    assert {"openai", "anthropic", "langgraph", "mcp", "codex"} <= set(conformance.adapters)
    assert replay.passed is True
    assert all(path["capabilities_granted"] == [] for path in replay.paths)
    assert all(path["runtime_semantics"] == "policy_audit_sandbox_preserved" for path in replay.paths)


def test_scenario_container_sandbox_evidence_uses_stable_candidate_contract():
    report = SandboxConformanceRunner().run_backend(backend_for_name("container"))

    assert report.passed is True
    assert report.support_level == "stable_candidate"
    assert "abuse.path_traversal" in report.checks
    assert "abuse.credential_path" in report.checks
    assert "no_absolute_escape_prevention" in report.limitations


def test_scenario_local_agent_cloud_control_plane_contract_fails_closed_and_redacts_exports():
    bundle = validate_policy_bundle(
        PlatformPolicyBundle(
            bundle_id="bundle-code-ci",
            version=1,
            policy_config={"version": 1, "default_decision": "deny", "rules": []},
        )
    )
    prod_unavailable = evaluate_platform_policy_state(
        environment="prod",
        platform_available=False,
        policy_stale=False,
    )
    forwarded = AppendOnlyAuditForwarder(fail_forwarding=True).forward(
        event={"event_type": "ToolCalled"},
        local_hash_chain=["hash-1", "hash-2"],
    )
    exported = RunExporter().export_run("run-1", {"prompt": "secret", "token": "abc"}, include_full_payload=False)
    registry = PlatformRegistryContract(remote_disabled=["openai"], local_allowlist=["openai", "mcp"])

    assert bundle.bundle_id == "bundle-code-ci"
    assert prod_unavailable.decision == "deny"
    assert prod_unavailable.fail_closed is True
    assert forwarded.forwarded is False
    assert forwarded.local_hash_chain == ["hash-1", "hash-2"]
    assert exported["payload"] == {"redacted": True}
    assert registry.resolve("openai").reason == "disabled_remotely"
    assert registry.resolve("mcp").enabled is True


def test_scenario_mcp_tool_governance_keeps_adapter_translate_only():
    report = AdapterConformanceRunner().run_adapters(["mcp"])

    assert report.passed is True
    assert report.adapters["mcp"]["support_level"] == "stable_candidate"
    assert "translate_only" in report.adapters["mcp"]["checks"]
    assert "no_capability_grant" in report.adapters["mcp"]["checks"]


def test_scenario_ops_diagnostic_read_only_agent_is_allowlisted_and_audited(tmp_path):
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

    allowed = runtime.call_tool("ops_status", {}, actor={"id": "sre"}, environment="staging")
    denied = runtime.call_tool("ops_restart", {}, actor={"id": "sre"}, environment="prod")

    assert allowed.status == "success"
    assert "status=ok" in allowed.output["stdout"]
    assert denied.status == "denied"
    assert verify_audit_chain(audit_path, sink="jsonl").valid is True


def test_scenario_local_codex_ide_governance_combines_codex_adapter_and_code_ci_boundaries(tmp_path):
    codex = AdapterConformanceRunner().run_adapters(["codex"])
    pilot = CodeCIPilot(allowed_commands=[])
    denied = pilot.run(repo_path=tmp_path, command=["gh", "pr"], write_scope=tmp_path)

    assert codex.passed is True
    assert codex.adapters["codex"]["support_level"] == "stable_candidate"
    assert "no_capability_grant" in codex.adapters["codex"]["checks"]
    assert denied.status == "denied"
    assert denied.error == "command.denied"
    assert denied.commit_push_pr_denied is True


def test_scenario_remote_executor_remains_contract_beta_not_production_ready():
    report = SandboxConformanceRunner().run_backend(backend_for_name("remote"))

    assert report.support_level == "contract_beta"
    assert report.passed is False
    assert "remote.contract_beta_only" in report.failure_reasons
    assert "no_production_execution" in report.limitations
