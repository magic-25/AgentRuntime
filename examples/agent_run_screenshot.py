from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from agent_runtime import AgentMetadata, RuntimeProfile
from agent_runtime.core.runtime import AgentRuntime
from agent_runtime.run_view import write_run_view_html
from agent_runtime.testing.provider_agents import OpenAICompatibleToolCallingAgent, create_glm_tool_calling_agent_from_env


class FakeOpenAICompatibleTransport:
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
                                    "arguments": json.dumps({"message": "runtime screenshot"}),
                                },
                            }
                        ]
                    }
                }
            ]
        }


PROMPT = "Call the echo tool exactly once with message 'runtime screenshot'."


def build_agent_run_screenshot(
    output_dir: str | Path = ".agent-runtime/run-screenshots",
    provider_mode: str = "real",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    audit_path = output_path / "real-provider-agent-run-audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()

    runtime = AgentRuntime.from_dict(
        {
            "version": 1,
            "default_decision": "deny",
            "audit": {"path": str(audit_path)},
            "tracing": {"enabled": True},
            "rules": [{"id": "allow-echo", "environment": "dev", "tool": "echo", "effect": "allow"}],
        }
    )

    @runtime.tool(name="echo")
    def echo(message: str) -> dict[str, str]:
        return {"message": message}

    agent = _agent(provider_mode)
    transcript = runtime.register_agent(
        "runtime-screenshot-agent",
        agent,
        actor={"id": "runtime-screenshot-agent"},
        environment="dev",
        metadata=AgentMetadata(
            agent_id="runtime-screenshot-agent",
            name="Runtime Screenshot Provider Agent",
            provider=agent.provider,
            framework="openai-compatible",
            capabilities=["tool.invoke:echo"],
            runtime_profile=RuntimeProfile(
                environment="dev",
                execution_mode="runtime_tools",
                max_tool_calls=1,
                network_access=provider_mode == "real",
            ),
        ),
    ).run(PROMPT)

    events = _read_events(audit_path)
    snapshot = {
        "artifact_type": "agent_run_screenshot",
        "provider_mode": provider_mode,
        "prompt": PROMPT,
        "agent": _agent_summary(transcript),
        "transcript": _transcript_summary(transcript),
        "tool_call": {
            "name": transcript.raw_tool_name,
            "arguments": transcript.raw_arguments,
        },
        "tool_result": _tool_result(transcript.tool_results[0]),
        "governance": _governance_summary(events),
        "trace": _trace_summary(events),
        "audit": {
            "path": str(audit_path),
            "events": [event["event_type"] for event in events],
        },
    }

    json_path = output_path / "real-provider-agent-run.json"
    html_path = output_path / "real-provider-agent-run.html"
    run_view_path = output_path / "real-provider-agent-run-view.html"
    png_path = output_path / "real-provider-agent-run.png"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_render_html(snapshot), encoding="utf-8")
    write_run_view_html(audit_path, run_view_path, snapshot=snapshot)
    _render_png(snapshot, png_path)
    return snapshot


def _agent(provider_mode: str) -> OpenAICompatibleToolCallingAgent:
    if provider_mode == "fake":
        return OpenAICompatibleToolCallingAgent(
            runtime=None,
            transport=FakeOpenAICompatibleTransport(),
            provider="fake-glm",
            model="glm-compatible-fixture",
            actor={"id": "runtime-screenshot-agent"},
            environment="dev",
        )
    if provider_mode == "real":
        return create_glm_tool_calling_agent_from_env(
            runtime=None,
            actor={"id": "runtime-screenshot-agent"},
            environment="dev",
        )
    raise ValueError("provider_mode must be 'real' or 'fake'")


def _read_events(audit_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _agent_summary(transcript: Any) -> dict[str, Any]:
    metadata = transcript.agent_metadata
    return {
        "agent_id": transcript.agent_id,
        "name": metadata["name"],
        "provider": metadata["provider"],
        "framework": metadata["framework"],
        "registration": transcript.registration,
    }


def _transcript_summary(transcript: Any) -> dict[str, Any]:
    return {
        "status": transcript.status,
        "decisions": list(transcript.decisions),
        "trace_id": transcript.trace_id,
        "agent_span_id": transcript.agent_span_id,
        "audit_events": list(transcript.audit_events),
        "error": transcript.error,
    }


def _tool_result(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "error": result.error,
        "run_id": result.run_id,
        "output": result.output,
    }


def _governance_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    policy = _payload_for(events, "TraceSpanFinished", "policy_evaluation")
    tool_finish = _payload_for(events, "TraceSpanFinished", "tool_call")
    return {
        "policy": {
            "decision": policy.get("decision"),
            "reason": policy.get("reason"),
            "rule_id": policy.get("rule_id"),
            "policy_version": policy.get("policy_version"),
        },
        "approval": {"status": None, "approved": None},
        "sandbox": {"isolation_level": None, "backend": None},
        "audit": {
            "status": tool_finish.get("audit_status", "committed" if events else "missing"),
            "event_count": len(events),
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
    return {
        "trace_id": next((span["trace_id"] for span in spans if span["trace_id"]), None),
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


def _render_html(snapshot: dict[str, Any]) -> str:
    governance = snapshot["governance"]
    tool_result = snapshot["tool_result"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Provider Agent Run</title>
  <style>
    body {{ margin: 0; background: #f6f7f9; color: #17202a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 44px 32px 56px; }}
    h1 {{ font-size: 38px; margin: 0 0 8px; letter-spacing: 0; }}
    .subtitle {{ color: #53616f; font-size: 17px; margin-bottom: 24px; }}
    .card {{ background: white; border: 1px solid #d9dee5; border-radius: 8px; padding: 20px; margin-bottom: 16px; }}
    .row {{ display: grid; grid-template-columns: 180px 1fr; gap: 12px; padding: 9px 0; border-top: 1px solid #edf0f3; }}
    .label {{ color: #667280; }}
    code {{ background: #eef2f6; padding: 2px 5px; border-radius: 5px; }}
    .ok {{ color: #087443; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Provider Agent Run</h1>
  <div class="subtitle">单次真实 registered agent 在 Agent Runtime 中运行产生的截图</div>
  <section class="card">
    <div class="row"><div class="label">Prompt</div><div><code>{snapshot["prompt"]}</code></div></div>
    <div class="row"><div class="label">Provider</div><div>{snapshot["agent"]["provider"]} / {snapshot["agent"]["framework"]}</div></div>
    <div class="row"><div class="label">Decisions</div><div><code>{' -> '.join(snapshot["transcript"]["decisions"])}</code></div></div>
    <div class="row"><div class="label">Tool call</div><div><code>{snapshot["tool_call"]["name"]}</code> {json.dumps(snapshot["tool_call"]["arguments"], ensure_ascii=False)}</div></div>
    <div class="row"><div class="label">Tool result</div><div class="ok">{tool_result["status"]} {json.dumps(tool_result["output"], ensure_ascii=False)}</div></div>
  </section>
  <section class="card">
    <div class="row"><div class="label">Policy</div><div><code>{governance["policy"]["decision"]}</code> / {governance["policy"]["reason"]}</div></div>
    <div class="row"><div class="label">Audit</div><div><code>{governance["audit"]["status"]}</code>, {governance["audit"]["event_count"]} events</div></div>
    <div class="row"><div class="label">Trace id</div><div><code>{snapshot["trace"]["trace_id"]}</code></div></div>
    <div class="row"><div class="label">Trace contains</div><div><code>{json.dumps(snapshot["trace"]["contains"], ensure_ascii=False)}</code></div></div>
  </section>
</main>
</body>
</html>
"""


def _render_png(snapshot: dict[str, Any], path: Path) -> None:
    width = 1400
    height = 980
    margin = 54
    image = Image.new("RGB", (width, height), "#f6f7f9")
    draw = ImageDraw.Draw(image)
    font_title = _font(46, bold=True)
    font_h2 = _font(25, bold=True)
    font_body = _font(20)
    font_small = _font(18)
    y = 48
    draw.text((margin, y), "Provider Agent Run", fill="#17202a", font=font_title)
    y += 60
    draw.text((margin, y), "single registered agent execution inside Agent Runtime", fill="#53616f", font=font_body)
    y += 58

    sections = [
        (
            "Agent Output",
            [
                f"Prompt: {snapshot['prompt']}",
                f"Provider: {snapshot['agent']['provider']} / {snapshot['agent']['framework']}",
                f"Decisions: {' -> '.join(snapshot['transcript']['decisions'])}",
                f"Tool call: {snapshot['tool_call']['name']} {json.dumps(snapshot['tool_call']['arguments'], ensure_ascii=False)}",
                f"Tool result: {snapshot['tool_result']['status']} {json.dumps(snapshot['tool_result']['output'], ensure_ascii=False)}",
            ],
        ),
        (
            "Runtime Governance",
            [
                f"Policy: {snapshot['governance']['policy']['decision']} / {snapshot['governance']['policy']['reason']}",
                f"Audit: {snapshot['governance']['audit']['status']} ({snapshot['governance']['audit']['event_count']} events)",
                f"Trace: {snapshot['trace']['trace_id']}",
                f"Trace contains: {json.dumps(snapshot['trace']['contains'], ensure_ascii=False)}",
            ],
        ),
    ]

    for title, rows in sections:
        box_height = 285 if title == "Agent Output" else 235
        draw.rounded_rectangle((margin, y, width - margin, y + box_height), radius=10, fill="#ffffff", outline="#d9dee5")
        draw.text((margin + 24, y + 20), title, fill="#17202a", font=font_h2)
        row_y = y + 66
        for row in rows:
            draw.text((margin + 24, row_y), row, fill="#2f3a45", font=font_small)
            row_y += 34
        y += box_height + 22
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
    output_path = Path(".agent-runtime/run-screenshots")
    if output_path.exists():
        shutil.rmtree(output_path)
    snapshot = build_agent_run_screenshot(output_path, provider_mode="real")
    print(
        json.dumps(
            {
                "path": str(output_path),
                "provider_mode": snapshot["provider_mode"],
                "status": snapshot["transcript"]["status"],
                "screenshot": str(output_path / "real-provider-agent-run.png"),
                "run_view": str(output_path / "real-provider-agent-run-view.html"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
