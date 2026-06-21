import threading

from agent_runtime.approval.base import StaticApprovalProvider, TimeoutApprovalProvider
from agent_runtime.audit.verify import verify_audit_chain
from agent_runtime.core.models import RuntimeProfile
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.observer.memory import InMemoryObserver


def _approval_runtime(tmp_path, approval_provider):
    observer = InMemoryObserver()
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"sink": "sqlite", "path": str(tmp_path / "approval.db")},
            "rules": [{"id": "approve-risk", "environment": "prod", "tool": "restart", "effect": "require_approval"}],
        },
        approval_provider=approval_provider,
        observer=observer,
    )

    @runtime.tool(name="restart", risk_level="high")
    def restart() -> str:
        return "restarted"

    return runtime, observer


def test_e2e_approval_provider_approve_reject_and_timeout_paths(tmp_path):
    approved_runtime, approved_observer = _approval_runtime(tmp_path / "approved", StaticApprovalProvider(True, "approved"))
    rejected_runtime, rejected_observer = _approval_runtime(tmp_path / "rejected", StaticApprovalProvider(False, "rejected"))
    timeout_runtime, timeout_observer = _approval_runtime(tmp_path / "timeout", TimeoutApprovalProvider())

    approved = approved_runtime.call_tool("restart", {}, actor={"id": "operator"}, environment="prod")
    rejected = rejected_runtime.call_tool("restart", {}, actor={"id": "operator"}, environment="prod")
    timeout = timeout_runtime.call_tool("restart", {}, actor={"id": "operator"}, environment="prod")

    assert approved.status == "success"
    assert approved.output == "restarted"
    assert approved_observer.status()["approval_requests"] == 1
    assert rejected.status == "rejected"
    assert rejected.error == "rejected"
    assert rejected_observer.status()["approval_rejected"] == 1
    assert timeout.status == "rejected"
    assert timeout.error == "approval.timeout"
    assert timeout_observer.status()["timeouts"] == 1


def test_e2e_concurrent_runtime_calls_keep_sqlite_audit_chain_valid(tmp_path):
    audit_path = tmp_path / "concurrent.db"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"sink": "sqlite", "path": str(audit_path)},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(value: int) -> dict[str, int]:
        return {"value": value}

    barrier = threading.Barrier(6)
    results = []

    def call_tool(index: int) -> None:
        barrier.wait(timeout=2)
        results.append(runtime.call_tool("echo", {"value": index}, actor={"id": "runner"}, environment="dev"))

    threads = [threading.Thread(target=call_tool, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert sorted(result.output["value"] for result in results) == list(range(6))
    verification = verify_audit_chain(audit_path, sink="sqlite")
    assert verification.valid is True
    assert verification.checked_events >= 18


def test_e2e_concurrent_registered_agents_keep_context_and_audit_events_isolated(tmp_path):
    audit_path = tmp_path / "registered-concurrent.db"
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"sink": "sqlite", "path": str(audit_path)},
            "rules": [
                {"id": "allow-tool-a", "environment": "dev", "tool": "tool_a", "effect": "allow"},
                {"id": "allow-tool-b", "environment": "dev", "tool": "tool_b", "effect": "allow"},
            ],
        }
    )

    @runtime.tool(name="tool_a")
    def tool_a() -> str:
        return "A"

    @runtime.tool(name="tool_b")
    def tool_b() -> str:
        return "B"

    agent_b_context_set = threading.Event()
    agent_a_finished = threading.Event()
    results = {}

    class AgentA:
        def run(self, prompt: str) -> dict[str, str | None]:
            agent_b_context_set.wait(timeout=2)
            result = self.runtime.call_tool("tool_a", {}, actor=self.actor, environment=self.environment)
            agent_a_finished.set()
            return {"tool_status": result.status, "tool_error": result.error}

    class AgentB:
        def run(self, prompt: str) -> dict[str, str | None]:
            agent_b_context_set.set()
            agent_a_finished.wait(timeout=2)
            result = self.runtime.call_tool("tool_b", {}, actor=self.actor, environment=self.environment)
            return {"tool_status": result.status, "tool_error": result.error}

    registered_a = runtime.register_agent(
        "agent-a",
        AgentA(),
        actor={"id": "runner"},
        environment="dev",
        metadata={
            "capabilities": ["tool.invoke:tool_a"],
            "runtime_profile": RuntimeProfile(environment="dev", max_tool_calls=1),
        },
    )
    registered_b = runtime.register_agent(
        "agent-b",
        AgentB(),
        actor={"id": "runner"},
        environment="dev",
        metadata={
            "capabilities": ["tool.invoke:tool_b"],
            "runtime_profile": RuntimeProfile(environment="dev", max_tool_calls=1),
        },
    )

    def run_agent(name, registered) -> None:
        results[name] = registered.run_session("go")

    threads = [
        threading.Thread(target=run_agent, args=("a", registered_a)),
        threading.Thread(target=run_agent, args=("b", registered_b)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert results["a"].status == "completed"
    assert results["a"].output == {"tool_status": "success", "tool_error": None}
    assert results["b"].status == "completed"
    assert results["b"].output == {"tool_status": "success", "tool_error": None}
    assert results["a"].audit_events.count("AgentRunStarted") == 1
    assert results["a"].audit_events.count("ToolExecutionFinished") == 1
    assert results["a"].audit_events.count("AgentRunFinished") == 1
    assert results["b"].audit_events.count("AgentRunStarted") == 1
    assert results["b"].audit_events.count("ToolExecutionFinished") == 1
    assert results["b"].audit_events.count("AgentRunFinished") == 1

    verification = verify_audit_chain(audit_path, sink="sqlite")
    assert verification.valid is True
