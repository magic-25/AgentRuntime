from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from agent_runtime import AgentMetadata, RuntimeProfile
from agent_runtime.approval.base import StaticApprovalProvider
from agent_runtime.core.models import ToolResult
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.execution.base import ProcessResult
from agent_runtime.execution.sandbox import SandboxExecutor
from agent_runtime.testing.provider_agents import OpenAICompatibleToolCallingAgent, create_glm_tool_calling_agent_from_env


@dataclass(frozen=True)
class ReportTranscript:
    status: str
    decisions: list[str]
    tool_results: list[ToolResult] = field(default_factory=list)
    error: str | None = None


class RuntimeToolAgent:
    def __init__(self, tool_name: str, tool_input: dict[str, Any]) -> None:
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.runtime: AgentRuntime | None = None
        self.actor: dict[str, Any] = {}
        self.environment = "dev"

    def run(self, prompt: str) -> ReportTranscript:
        if self.runtime is None:
            raise RuntimeError("runtime.required")
        decisions = [f"prompt:{prompt}", f"call:{self.tool_name}"]
        result = self.runtime.call_tool(
            self.tool_name,
            dict(self.tool_input),
            actor=self.actor,
            environment=self.environment,
        )
        if result.status == "success":
            decisions.append("stop")
            return ReportTranscript(status="completed", decisions=decisions, tool_results=[result])
        decisions.append(f"blocked:{result.error or result.status}")
        return ReportTranscript(status="blocked", decisions=decisions, tool_results=[result], error=result.error)


class FakeOpenAICompatibleTransport:
    def __init__(self, message: str) -> None:
        self.message = message

    def complete(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "echo",
                                    "arguments": json.dumps({"message": self.message}),
                                },
                            }
                        ]
                    }
                }
            ]
        }


class CompleteReportSandbox(SandboxExecutor):
    backend_name = "complete-report-sandbox"
    available = True

    def execute(self, spec):
        return ProcessResult(exit_code=0, stdout="sandbox command completed", stderr="")


def build_complete_report(
    output_dir: str | Path = ".agent-runtime/complete-report",
    provider_mode: str = "real",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    scenarios = [
        _run_scripted_echo(output_path),
        _run_provider_tool_call(output_path, provider_mode=provider_mode),
        _run_policy_deny(output_path),
        _run_approval_gate(output_path),
        _run_sandboxed_command(output_path),
    ]
    report = {
        "report_type": "complete_runtime_report",
        "product": "Agent Runtime",
        "status": "Technical Preview",
        "summary": {
            "scenario_count": len(scenarios),
            "provider_mode": provider_mode,
            "questions_answered": [
                "agent做了什么",
                "为什么允许、为什么拒绝、是否经过approval、是否强隔离、是否可审计",
            ],
            "agents": [scenario["agent"]["name"] for scenario in scenarios],
        },
        "scenarios": scenarios,
    }
    (output_path / "complete-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_path / "complete-report.md").write_text(_render_markdown(report), encoding="utf-8")
    (output_path / "complete-report.html").write_text(_render_html(report), encoding="utf-8")
    _render_png(report, output_path / "complete-report.png")
    return report


def _run_scripted_echo(output_path: Path) -> dict[str, Any]:
    runtime, audit_path = _runtime(
        output_path,
        "scripted_echo",
        [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    agent = RuntimeToolAgent("echo", {"message": "hello from scripted agent"})
    transcript = runtime.register_agent(
        "scripted-echo-agent",
        agent,
        actor={"id": "scripted-echo-agent"},
        environment="dev",
        metadata=_metadata(
            "scripted-echo-agent",
            "Scripted Echo Agent",
            provider="local",
            framework="scripted-python",
            capabilities=["tool.invoke:echo"],
        ),
    ).run("echo once")
    return _scenario(
        "scripted_echo",
        "Scripted Echo Agent",
        "Shows the smallest successful runtime-governed tool call.",
        "echo once",
        transcript,
        audit_path,
    )


def _run_provider_tool_call(output_path: Path, provider_mode: str) -> dict[str, Any]:
    runtime, audit_path = _runtime(
        output_path,
        "provider_tool_call",
        [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    if provider_mode == "fake":
        agent = OpenAICompatibleToolCallingAgent(
            runtime=None,
            transport=FakeOpenAICompatibleTransport("hello from provider-style agent"),
            provider="fake-glm",
            model="glm-compatible-fixture",
            actor={"id": "provider-agent"},
            environment="dev",
        )
        provider_name = "fake-glm"
    elif provider_mode == "real":
        agent = create_glm_tool_calling_agent_from_env(
            runtime=None,
            actor={"id": "provider-agent"},
            environment="dev",
        )
        provider_name = agent.provider
    else:
        raise ValueError("provider_mode must be 'real' or 'fake'")
    transcript = runtime.register_agent(
        "provider-agent",
        agent,
        actor={"id": "provider-agent"},
        environment="dev",
        metadata=_metadata(
            "provider-agent",
            "Provider Tool Calling Agent",
            provider=provider_name,
            framework="openai-compatible",
            capabilities=["tool.invoke:echo"],
        ),
    ).run("Call the echo tool exactly once with message 'hello from real provider agent'.")
    return _scenario(
        "provider_tool_call",
        "Provider Tool Calling Agent",
        "Shows provider-style tool selection with runtime-governed execution.",
        "call echo using provider tool call",
        transcript,
        audit_path,
    )


def _run_policy_deny(output_path: Path) -> dict[str, Any]:
    runtime, audit_path = _runtime(output_path, "policy_deny", [])

    @runtime.tool(name="delete_record", risk_level="high")
    def delete_record(record_id: str) -> dict[str, str]:
        return {"deleted": record_id}

    agent = RuntimeToolAgent("delete_record", {"record_id": "customer-123"})
    transcript = runtime.register_agent(
        "policy-deny-agent",
        agent,
        actor={"id": "policy-deny-agent"},
        environment="dev",
        metadata=_metadata(
            "policy-deny-agent",
            "Policy Deny Agent",
            provider="local",
            framework="scripted-python",
            capabilities=["tool.invoke:delete_record"],
        ),
    ).run("try deleting a protected record")
    return _scenario(
        "policy_deny",
        "Policy Deny Agent",
        "Shows denied tool execution and the policy reason in the governed trace.",
        "try deleting a protected record",
        transcript,
        audit_path,
    )


def _run_approval_gate(output_path: Path) -> dict[str, Any]:
    runtime, audit_path = _runtime(
        output_path,
        "approval_gate",
        [{"id": "approve-echo", "environment": "prod", "tool": "echo", "effect": "require_approval"}],
        approval_provider=StaticApprovalProvider(approved=True, reason="approved-for-complete-report"),
    )

    @runtime.tool(name="echo", risk_level="high")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    agent = RuntimeToolAgent("echo", {"message": "approved production action"})
    transcript = runtime.register_agent(
        "approval-agent",
        agent,
        actor={"id": "approval-agent"},
        environment="prod",
        metadata=_metadata(
            "approval-agent",
            "Approval Gate Agent",
            provider="local",
            framework="scripted-python",
            capabilities=["tool.invoke:echo"],
            environment="prod",
            approval_required=True,
        ),
    ).run("run high-risk echo with approval")
    return _scenario(
        "approval_gate",
        "Approval Gate Agent",
        "Shows approval-gated execution and approval evidence in the trace.",
        "run high-risk echo with approval",
        transcript,
        audit_path,
    )


def _run_sandboxed_command(output_path: Path) -> dict[str, Any]:
    runtime, audit_path = _runtime(
        output_path,
        "sandboxed_command",
        [
            {"id": "allow-tool", "environment": "prod", "effect": "allow", "capabilities": ["tool.invoke:*"]},
            {"id": "allow-command", "environment": "prod", "effect": "allow", "capabilities": ["command.execute:*"]},
        ],
        sandbox_executor=CompleteReportSandbox(),
    )
    runtime.sandboxed_command_tool(
        name="sandboxed_status",
        argv=["python", "-c", "print('sandbox command completed')"],
        cwd=str(output_path),
        risk_level="high",
        capabilities_required=["tool.invoke:sandboxed_status", "command.execute:python"],
        network_access=False,
        read_paths=[str(output_path)],
        write_paths=[],
    )

    agent = RuntimeToolAgent("sandboxed_status", {})
    transcript = runtime.register_agent(
        "sandbox-agent",
        agent,
        actor={"id": "sandbox-agent"},
        environment="prod",
        metadata=_metadata(
            "sandbox-agent",
            "Sandboxed Command Agent",
            provider="local",
            framework="scripted-python",
            capabilities=["tool.invoke:sandboxed_status", "command.execute:python"],
            environment="prod",
            sandbox_required=True,
        ),
    ).run("run sandboxed status command")
    return _scenario(
        "sandboxed_command",
        "Sandboxed Command Agent",
        "Shows strong sandbox isolation evidence for a command tool.",
        "run sandboxed status command",
        transcript,
        audit_path,
    )


def _runtime(
    output_path: Path,
    name: str,
    rules: list[dict[str, Any]],
    approval_provider: StaticApprovalProvider | None = None,
    sandbox_executor: SandboxExecutor | None = None,
) -> tuple[AgentRuntime, Path]:
    audit_path = output_path / f"{name}-audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": rules,
        },
        approval_provider=approval_provider,
        sandbox_executor=sandbox_executor,
    )
    return runtime, audit_path


def _metadata(
    agent_id: str,
    name: str,
    provider: str,
    framework: str,
    capabilities: list[str],
    environment: str = "dev",
    sandbox_required: bool = False,
    approval_required: bool = False,
) -> AgentMetadata:
    return AgentMetadata(
        agent_id=agent_id,
        name=name,
        provider=provider,
        framework=framework,
        capabilities=capabilities,
        runtime_profile=RuntimeProfile(
            environment=environment,
            execution_mode="runtime_tools",
            max_tool_calls=1,
            sandbox_required=sandbox_required,
            approval_required=approval_required,
        ),
    )


def _scenario(
    scenario_id: str,
    title: str,
    purpose: str,
    prompt: str,
    transcript: Any,
    audit_path: Path,
) -> dict[str, Any]:
    events = _read_events(audit_path)
    tool_results = [_tool_result(result) for result in getattr(transcript, "tool_results", [])]
    return {
        "id": scenario_id,
        "title": title,
        "purpose": purpose,
        "agent": _agent_summary(transcript, fallback_name=title),
        "prompt": prompt,
        "transcript": _transcript_summary(transcript),
        "tool_results": tool_results,
        "governance": _governance_summary(events, tool_results),
        "trace": _trace_summary(events),
        "audit": {
            "path": str(audit_path),
            "events": [event["event_type"] for event in events],
        },
    }


def _read_events(audit_path: Path) -> list[dict[str, Any]]:
    if not audit_path.exists():
        return []
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _agent_summary(transcript: Any, fallback_name: str) -> dict[str, Any]:
    metadata = getattr(transcript, "agent_metadata", {}) or {}
    return {
        "agent_id": getattr(transcript, "agent_id", None) or metadata.get("agent_id"),
        "name": metadata.get("name", fallback_name),
        "provider": metadata.get("provider", getattr(transcript, "provider", "local")),
        "framework": metadata.get("framework", "scripted-python"),
        "registration": getattr(transcript, "registration", "registered"),
    }


def _transcript_summary(transcript: Any) -> dict[str, Any]:
    summary = {
        "status": getattr(transcript, "status", "unknown"),
        "decisions": list(getattr(transcript, "decisions", [])),
        "error": getattr(transcript, "error", None),
        "trace_id": getattr(transcript, "trace_id", None),
        "agent_span_id": getattr(transcript, "agent_span_id", None),
    }
    raw_tool_name = getattr(transcript, "raw_tool_name", None)
    if raw_tool_name is not None:
        summary["raw_tool_name"] = raw_tool_name
        summary["raw_arguments"] = getattr(transcript, "raw_arguments", {})
    return summary


def _tool_result(result: ToolResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "error": result.error,
        "run_id": result.run_id,
        "output": result.output,
    }


def _governance_summary(events: list[dict[str, Any]], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    policy = _payload_for(events, "TraceSpanFinished", "policy_evaluation")
    approval = _payload_for(events, "TraceSpanFinished", "approval_gate")
    sandbox = _payload_for(events, "TraceSpanFinished", "sandbox_execution")
    tool_finish = _payload_for(events, "TraceSpanFinished", "tool_call")
    event_types = [event["event_type"] for event in events]
    return {
        "policy": {
            "decision": policy.get("decision"),
            "reason": policy.get("reason"),
            "rule_id": policy.get("rule_id"),
            "policy_version": policy.get("policy_version"),
        },
        "approval": {
            "approved": approval.get("approved"),
            "reason": approval.get("reason"),
            "timed_out": approval.get("timed_out"),
            "status": approval.get("status"),
        },
        "sandbox": {
            "isolation_level": sandbox.get("isolation_level"),
            "backend": sandbox.get("backend"),
            "available": sandbox.get("available"),
            "status": sandbox.get("status"),
        },
        "audit": {
            "status": tool_finish.get("audit_status", "committed" if events else "missing"),
            "event_count": len(events),
        },
        "execution": {
            "tool_executed": "ToolExecutionStarted" in event_types,
            "final_status": tool_results[0]["status"] if tool_results else None,
            "final_error": tool_results[0]["error"] if tool_results else None,
        },
    }


def _trace_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    spans = [
        {
            "event_type": event["event_type"],
            "span_kind": event.get("payload", {}).get("span_kind"),
            "trace_id": event.get("trace_id"),
            "span_id": event.get("span_id"),
            "parent_span_id": event.get("payload", {}).get("parent_span_id"),
            "status": event.get("payload", {}).get("status"),
        }
        for event in events
        if event["event_type"].startswith("TraceSpan")
    ]
    span_kinds = {span["span_kind"] for span in spans}
    trace_id = next((span["trace_id"] for span in spans if span["trace_id"]), None)
    return {
        "trace_id": trace_id,
        "contains": {
            "agent_run": "agent_run" in span_kinds,
            "tool_call": "tool_call" in span_kinds,
            "policy_evaluation": "policy_evaluation" in span_kinds,
            "approval_gate": "approval_gate" in span_kinds,
            "sandbox_execution": "sandbox_execution" in span_kinds,
        },
        "spans": spans,
    }


def _payload_for(events: list[dict[str, Any]], event_type: str, span_kind: str) -> dict[str, Any]:
    for event in events:
        payload = event.get("payload", {})
        if event["event_type"] == event_type and payload.get("span_kind") == span_kind:
            return payload
    return {}


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Agent Runtime Complete Report",
        "",
        "本报告展示多个 agent 放进 Agent Runtime 后的完整输出体验。它不是测试明细，而是回答两个产品问题：",
        "",
        "1. agent 做了什么。",
        "2. runtime 为什么允许、为什么拒绝、是否强隔离、是否可审计。",
        "",
        "## Summary",
        "",
        f"- Scenario count: {report['summary']['scenario_count']}",
        f"- Provider mode: {report['summary']['provider_mode']}",
        f"- Agents: {', '.join(report['summary']['agents'])}",
        "",
    ]
    for scenario in report["scenarios"]:
        lines.extend(_render_scenario_markdown(scenario))
    return "\n".join(lines) + "\n"


def _render_scenario_markdown(scenario: dict[str, Any]) -> list[str]:
    result = scenario["tool_results"][0]
    governance = scenario["governance"]
    trace = scenario["trace"]
    return [
        f"## {scenario['title']}",
        "",
        scenario["purpose"],
        "",
        f"- Agent: `{scenario['agent']['agent_id']}` ({scenario['agent']['framework']})",
        f"- Prompt: `{scenario['prompt']}`",
        f"- Transcript status: `{scenario['transcript']['status']}`",
        f"- Decisions: `{', '.join(scenario['transcript']['decisions'])}`",
        f"- Tool result: `{result['status']}`",
        f"- Tool output: `{json.dumps(result['output'], ensure_ascii=False)}`",
        "",
        "### Governance Output",
        "",
        f"- Policy: `{governance['policy']['decision']}` / `{governance['policy']['reason']}`",
        f"- Approval: `{governance['approval']['status']}`",
        f"- Sandbox: `{governance['sandbox']['isolation_level']}` via `{governance['sandbox']['backend']}`",
        f"- Audit: `{governance['audit']['status']}` with `{governance['audit']['event_count']}` events",
        "",
        "### Governed Trace",
        "",
        f"- Trace id: `{trace['trace_id']}`",
        f"- Contains: `{json.dumps(trace['contains'], ensure_ascii=False)}`",
        "",
    ]


def _render_html(report: dict[str, Any]) -> str:
    scenario_cards = "\n".join(_scenario_html(scenario) for scenario in report["scenarios"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Agent Runtime Complete Report</title>
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #17202a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 44px 32px 56px; }}
    h1 {{ font-size: 38px; margin: 0 0 10px; letter-spacing: 0; }}
    .subtitle {{ color: #53616f; font-size: 17px; margin-bottom: 26px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 24px; }}
    .metric, .card {{ background: white; border: 1px solid #d9dee5; border-radius: 8px; box-shadow: 0 1px 2px rgba(16,24,40,.04); }}
    .metric {{ padding: 16px; }}
    .metric strong {{ display: block; font-size: 26px; margin-bottom: 4px; }}
    .metric span {{ color: #596775; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .card {{ padding: 18px; }}
    .card h2 {{ font-size: 20px; margin: 0 0 8px; }}
    .purpose {{ color: #596775; min-height: 42px; }}
    .row {{ display: grid; grid-template-columns: 145px 1fr; gap: 10px; padding: 7px 0; border-top: 1px solid #edf0f3; }}
    .label {{ color: #667280; }}
    code {{ background: #eef2f6; padding: 2px 5px; border-radius: 5px; }}
    .status-success, .status-completed {{ color: #087443; font-weight: 700; }}
    .status-denied, .status-blocked {{ color: #b42318; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Agent Runtime Complete Report</h1>
  <div class="subtitle">真实 provider + governed trace + policy / approval / sandbox / audit output</div>
  <section class="summary">
    <div class="metric"><strong>{report["summary"]["scenario_count"]}</strong><span>agent scenarios</span></div>
    <div class="metric"><strong>{report["summary"]["provider_mode"]}</strong><span>provider mode</span></div>
    <div class="metric"><strong>governed</strong><span>trace model</span></div>
  </section>
  <section class="grid">
    {scenario_cards}
  </section>
</main>
</body>
</html>
"""


def _scenario_html(scenario: dict[str, Any]) -> str:
    result = scenario["tool_results"][0]
    governance = scenario["governance"]
    trace = scenario["trace"]
    status_class = f"status-{scenario['transcript']['status']}"
    output = json.dumps(result["output"], ensure_ascii=False)
    return f"""
<article class="card">
  <h2>{scenario["title"]}</h2>
  <p class="purpose">{scenario["purpose"]}</p>
  <div class="row"><div class="label">Agent</div><div><code>{scenario["agent"]["agent_id"]}</code> / {scenario["agent"]["framework"]}</div></div>
  <div class="row"><div class="label">Transcript</div><div class="{status_class}">{scenario["transcript"]["status"]}</div></div>
  <div class="row"><div class="label">Tool result</div><div><code>{result["status"]}</code> {output}</div></div>
  <div class="row"><div class="label">Policy</div><div><code>{governance["policy"]["decision"]}</code> / {governance["policy"]["reason"]}</div></div>
  <div class="row"><div class="label">Approval</div><div><code>{governance["approval"]["status"]}</code></div></div>
  <div class="row"><div class="label">Sandbox</div><div><code>{governance["sandbox"]["isolation_level"]}</code> / {governance["sandbox"]["backend"]}</div></div>
  <div class="row"><div class="label">Audit</div><div><code>{governance["audit"]["status"]}</code>, {governance["audit"]["event_count"]} events</div></div>
  <div class="row"><div class="label">Trace</div><div><code>{trace["trace_id"]}</code></div></div>
</article>
"""


def _render_png(report: dict[str, Any], path: Path) -> None:
    width = 1500
    card_height = 235
    margin = 44
    gap = 18
    height = 250 + len(report["scenarios"]) * (card_height + gap)
    image = Image.new("RGB", (width, height), "#f6f7f9")
    draw = ImageDraw.Draw(image)
    font_title = _font(42, bold=True)
    font_h2 = _font(25, bold=True)
    font_body = _font(19)
    font_small = _font(16)

    y = 38
    draw.text((margin, y), "Agent Runtime Complete Report", fill="#17202a", font=font_title)
    y += 58
    draw.text(
        (margin, y),
        f"{report['summary']['scenario_count']} scenarios | provider={report['summary']['provider_mode']} | governed trace",
        fill="#53616f",
        font=font_body,
    )
    y += 54

    for scenario in report["scenarios"]:
        draw.rounded_rectangle((margin, y, width - margin, y + card_height), radius=10, fill="#ffffff", outline="#d9dee5")
        draw.text((margin + 24, y + 18), scenario["title"], fill="#17202a", font=font_h2)
        draw.text((margin + 24, y + 55), scenario["purpose"], fill="#596775", font=font_small)
        result = scenario["tool_results"][0]
        governance = scenario["governance"]
        rows = [
            f"Agent: {scenario['agent']['agent_id']} ({scenario['agent']['framework']})",
            f"Transcript: {scenario['transcript']['status']} | Tool: {result['status']}",
            f"Policy: {governance['policy']['decision']} / {governance['policy']['reason']}",
            f"Approval: {governance['approval']['status']} | Sandbox: {governance['sandbox']['isolation_level']} via {governance['sandbox']['backend']}",
            f"Audit: {governance['audit']['status']} ({governance['audit']['event_count']} events)",
            f"Trace: {scenario['trace']['trace_id']}",
        ]
        row_y = y + 90
        for row in rows:
            draw.text((margin + 24, row_y), row, fill="#2f3a45", font=font_small)
            row_y += 22
        y += card_height + gap
    image.save(path)


def _font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for candidate in candidates:
        font_path = Path(candidate)
        if font_path.exists():
            try:
                return ImageFont.truetype(
                    str(font_path),
                    size=size,
                    index=1 if bold and font_path.suffix == ".ttc" else 0,
                )
            except OSError:
                continue
    return ImageFont.load_default()


def main() -> None:
    output_path = Path(".agent-runtime/complete-report")
    if output_path.exists():
        shutil.rmtree(output_path)
    report = build_complete_report(output_path, provider_mode="real")
    print(
        json.dumps(
            {
                "path": str(output_path),
                "scenario_count": report["summary"]["scenario_count"],
                "provider_mode": report["summary"]["provider_mode"],
                "screenshot": str(output_path / "complete-report.png"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
