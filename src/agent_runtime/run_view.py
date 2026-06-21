from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any


def build_run_view_from_audit(audit_path: str | Path, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(audit_path)
    events = _read_jsonl(path)
    snapshot = snapshot or {}
    trace_tree = _build_trace_tree(events)
    tool_calls = _build_tool_calls(events)
    return {
        "title": "Agent Runtime Run Viewer",
        "subtitle": "完整运行过程可视化：agent 做了什么，runtime 为什么允许/拒绝，证据在哪里。",
        "audit_path": str(path),
        "overview": _overview(events, snapshot, trace_tree),
        "input": {"prompt": snapshot.get("prompt")},
        "agent_context": _agent_context(snapshot),
        "agent_decision": _agent_decision(snapshot, tool_calls),
        "governance": _governance(events, snapshot),
        "timeline": _timeline(events),
        "tool_calls": tool_calls,
        "trace_tree": trace_tree,
        "raw_events": events,
    }


def render_run_view_html(view: dict[str, Any]) -> str:
    overview = view["overview"]
    governance = view["governance"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{_text(view["title"])}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --ink: #17202a;
      --muted: #5e6b78;
      --line: #d9e0e7;
      --panel: #ffffff;
      --accent: #0f766e;
      --danger: #b42318;
      --code: #eef3f7;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 40px 28px 64px; }}
    h1 {{ margin: 0 0 8px; font-size: 34px; letter-spacing: 0; }}
    h2 {{ margin: 0 0 14px; font-size: 20px; letter-spacing: 0; }}
    h3 {{ margin: 18px 0 8px; font-size: 16px; letter-spacing: 0; }}
    .subtitle {{ color: var(--muted); font-size: 16px; margin-bottom: 22px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }}
    .metric, section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    .metric {{ padding: 14px 16px; min-height: 88px; }}
    .metric-label {{ color: var(--muted); font-size: 13px; margin-bottom: 7px; }}
    .metric-value {{ font-size: 16px; font-weight: 650; overflow-wrap: anywhere; }}
    section {{ padding: 18px 20px; margin: 14px 0; }}
    .explanation-section {{ border-color: #c9d7ef; }}
    .explanation-text {{ margin: 0 0 14px; line-height: 1.65; color: #2f3a45; }}
    .report-section {{ border-color: #b8d7d0; }}
    .row {{ display: grid; grid-template-columns: 190px minmax(0, 1fr); gap: 14px; padding: 9px 0; border-top: 1px solid #edf1f5; }}
    .row:first-of-type {{ border-top: 0; }}
    .label {{ color: var(--muted); }}
    code, pre {{ background: var(--code); border-radius: 6px; }}
    code {{ padding: 2px 5px; }}
    pre {{ padding: 12px; overflow: auto; white-space: pre-wrap; }}
    .json-beauty {{ margin: 0; line-height: 1.48; font-size: 13px; border: 1px solid #dce5ec; background: #fbfdff; }}
    .json-key {{ color: #0f5b8c; font-weight: 650; }}
    .json-string {{ color: #087443; }}
    .json-number {{ color: #8b4e00; }}
    .json-boolean {{ color: #7c3aed; font-weight: 650; }}
    .json-null {{ color: #687789; font-style: italic; }}
    .json-punctuation {{ color: #6b7785; }}
    .ok {{ color: var(--accent); font-weight: 700; }}
    .deny {{ color: var(--danger); font-weight: 700; }}
    .timeline {{ list-style: none; padding: 0; margin: 0; }}
    .timeline li {{ display: grid; grid-template-columns: 34px 210px minmax(0, 1fr); gap: 10px; padding: 8px 0; border-top: 1px solid #edf1f5; }}
    .timeline li:first-child {{ border-top: 0; }}
    .index {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
    .event-type {{ font-weight: 650; overflow-wrap: anywhere; }}
    .muted {{ color: var(--muted); }}
    .pills {{ display: flex; flex-wrap: wrap; gap: 7px; }}
    .pill {{ display: inline-flex; align-items: center; min-height: 28px; padding: 3px 9px; border: 1px solid #c7d8e2; border-radius: 999px; background: #f7fbfd; font-size: 13px; }}
    .decision-list {{ margin: 0; padding-left: 20px; }}
    .decision-list li {{ padding: 3px 0; }}
    .tree ul {{ list-style: none; margin: 8px 0 0 22px; padding-left: 14px; border-left: 1px solid var(--line); }}
    .tree li {{ margin: 8px 0; }}
    .span-title {{ font-weight: 650; }}
    details {{ border-top: 1px solid #edf1f5; padding-top: 10px; margin-top: 10px; }}
    summary {{ cursor: pointer; font-weight: 650; }}
    @media (max-width: 760px) {{
      main {{ padding: 28px 16px 48px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .row, .timeline li {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main>
  <h1>{_text(view["title"])}</h1>
  <div class="subtitle">{_text(view["subtitle"])}</div>

  <div class="grid">
    {_metric("Agent", overview.get("agent_id"))}
    {_metric("Status", overview.get("status"), _status_class(overview.get("status")))}
    {_metric("Prompt", view["input"].get("prompt"))}
    {_metric("Trace", overview.get("trace_id"))}
  </div>

  <section class="explanation-section">
    <h2>这个 Agent 是做什么的</h2>
    {_agent_explanation_html(view)}
  </section>

  <section class="report-section">
    <h2>Agent Run Report</h2>
    {_row("Prompt", _code(view["input"].get("prompt")))}
    {_row("Purpose", _inline(view["agent_context"].get("purpose")))}
    {_row("Agent Phases", _phase_list(view["agent_context"].get("phases") or []))}
    {_row("Decisions", _decision_list(view["agent_decision"].get("decisions") or []))}
    {_row("Findings", _json_block(view["agent_context"].get("findings") or {}))}
    {_row("Remediation", _json_block(view["agent_context"].get("remediation") or {}))}
  </section>

  <section>
    <h2>Run Overview</h2>
    {_row("Provider", _inline(overview.get("provider")))}
    {_row("Framework", _inline(overview.get("framework")))}
    {_row("Registration", _inline(overview.get("registration")))}
    {_row("Audit Path", _inline(view.get("audit_path")))}
    {_row("Duration", _inline(_duration(overview.get("duration_ms"))))}
  </section>

  <section>
    <h2>Agent Decision</h2>
    {_row("Tool", _inline(view["agent_decision"].get("tool_name")))}
    {_row("Arguments", _json_block(view["agent_decision"].get("arguments")))}
    {_row("Decision Chain", _code(" -> ".join(view["agent_decision"].get("decisions") or [])))}
  </section>

  <section>
    <h2>Runtime Governance</h2>
    <p class="muted">为什么允许/拒绝、是否强隔离、是否可审计。</p>
    {_row("Policy", _policy_summary(governance["policy"]))}
    {_row("Approval", _json_block(governance["approval"]))}
    {_row("Sandbox", _json_block(governance["sandbox"]))}
    {_row("Audit", _json_block(governance["audit"]))}
  </section>

  <section>
    <h2>Execution Timeline</h2>
    <ol class="timeline">
      {''.join(_timeline_item(step) for step in view["timeline"])}
    </ol>
  </section>

  <section>
    <h2>Tool Calls</h2>
    {''.join(_tool_call_html(tool_call) for tool_call in view["tool_calls"]) or '<p class="muted">No tool calls recorded.</p>'}
  </section>

  <section>
    <h2>Trace Tree</h2>
    <div class="tree">
      {''.join(_span_node_html(node) for node in view["trace_tree"]) or '<p class="muted">No trace spans recorded.</p>'}
    </div>
  </section>

  <section>
    <h2>Raw Evidence</h2>
    <details>
      <summary>Show audit JSONL events</summary>
      {_json_block(view["raw_events"])}
    </details>
  </section>
</main>
</body>
</html>
"""


def write_run_view_html(
    audit_path: str | Path,
    output_path: str | Path,
    snapshot: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    snapshot_payload = _load_snapshot(snapshot)
    view = build_run_view_from_audit(audit_path, snapshot=snapshot_payload)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_run_view_html(view), encoding="utf-8")
    return {"path": str(output), "event_count": len(view["raw_events"]), "trace_id": view["overview"].get("trace_id")}


def load_scenario_snapshot(report_path: str | Path, scenario_id: str) -> dict[str, Any]:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    for scenario in report.get("scenarios", []):
        if scenario.get("id") == scenario_id:
            return scenario
    raise ValueError(f"scenario not found in report: {scenario_id}")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_snapshot(snapshot: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if snapshot is None or isinstance(snapshot, dict):
        return snapshot
    return json.loads(Path(snapshot).read_text(encoding="utf-8"))


def _agent_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    transcript = snapshot.get("transcript", {})
    agent = snapshot.get("agent", {})
    return {
        "name": agent.get("name") or snapshot.get("title"),
        "framework": agent.get("framework"),
        "purpose": snapshot.get("purpose"),
        "phases": list(transcript.get("phases", [])),
        "findings": transcript.get("findings", {}),
        "remediation": transcript.get("remediation", {}),
    }


def _overview(events: list[dict[str, Any]], snapshot: dict[str, Any], trace_tree: list[dict[str, Any]]) -> dict[str, Any]:
    agent = snapshot.get("agent", {})
    transcript = snapshot.get("transcript", {})
    agent_registered = _first_event(events, "AgentRegistered")
    agent_finished = _first_event(events, "AgentRunFinished")
    metadata = agent_registered.get("payload", {}).get("metadata", {}) if agent_registered else {}
    root_span = trace_tree[0] if trace_tree else {}
    return {
        "agent_id": agent.get("agent_id") or metadata.get("agent_id") or agent_finished.get("payload", {}).get("agent_id"),
        "provider": agent.get("provider") or metadata.get("provider"),
        "framework": agent.get("framework") or metadata.get("framework"),
        "registration": agent.get("registration") or ("registered" if agent_registered else None),
        "status": transcript.get("status") or agent_finished.get("payload", {}).get("status") or root_span.get("status"),
        "trace_id": transcript.get("trace_id") or root_span.get("trace_id"),
        "duration_ms": root_span.get("duration_ms"),
    }


def _agent_decision(snapshot: dict[str, Any], tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot_tool = snapshot.get("tool_call", {})
    first_tool = tool_calls[0] if tool_calls else {}
    return {
        "tool_name": snapshot_tool.get("name") or first_tool.get("tool_name"),
        "arguments": snapshot_tool.get("arguments") or first_tool.get("input"),
        "decisions": snapshot.get("transcript", {}).get("decisions", []),
    }


def _governance(events: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    if snapshot.get("governance"):
        return snapshot["governance"]
    policy = _first_payload(events, "TraceSpanFinished", "policy_evaluation")
    approval = _first_payload(events, "TraceSpanFinished", "approval_gate")
    sandbox = _first_payload(events, "TraceSpanFinished", "sandbox_execution")
    tool_finish = _first_payload(events, "TraceSpanFinished", "tool_call")
    return {
        "policy": {
            "decision": policy.get("decision"),
            "reason": policy.get("reason"),
            "rule_id": policy.get("rule_id"),
            "policy_version": policy.get("policy_version"),
        },
        "approval": {
            "status": approval.get("status"),
            "approved": approval.get("approved"),
            "reason": approval.get("reason"),
            "timed_out": approval.get("timed_out"),
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
    }


def _timeline(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": index + 1,
            "event_type": event.get("event_type"),
            "tool_name": event.get("tool_name"),
            "trace_id": event.get("trace_id"),
            "span_id": event.get("span_id"),
            "summary": _event_summary(event),
        }
        for index, event in enumerate(events)
    ]


def _event_summary(event: dict[str, Any]) -> str:
    payload = event.get("payload", {})
    event_type = event.get("event_type")
    if event_type == "TraceSpanStarted":
        return f"{payload.get('span_kind')} started"
    if event_type == "TraceSpanFinished":
        return f"{payload.get('span_kind')} finished status={payload.get('status')}"
    if event_type == "ToolCallRequested":
        return f"{event.get('tool_name')} input={_json(payload.get('input'))}"
    if event_type == "PolicyEvaluated":
        return f"{payload.get('decision')} rule={payload.get('rule_id')}"
    if event_type == "ToolExecutionFinished":
        return f"{payload.get('status')} output={_json(payload.get('output'))}"
    if event_type == "AgentRunFinished":
        return f"{payload.get('status')} tool_count={payload.get('tool_count')}"
    return _json({key: payload.get(key) for key in ("agent_id", "environment", "status") if key in payload})


def _build_tool_calls(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for event in events:
        tool_call_id = event.get("tool_call_id")
        if not tool_call_id:
            continue
        if tool_call_id not in grouped:
            grouped[tool_call_id] = {
                "tool_call_id": tool_call_id,
                "run_id": event.get("run_id"),
                "tool_name": event.get("tool_name"),
                "input": None,
                "policy": {},
                "approval": {},
                "sandbox": {},
                "result": {},
                "trace": {},
            }
            order.append(tool_call_id)
        tool_call = grouped[tool_call_id]
        payload = event.get("payload", {})
        event_type = event.get("event_type")
        if event_type == "ToolCallRequested":
            tool_call["input"] = payload.get("input")
            tool_call["trace"]["trace_id"] = event.get("trace_id")
            tool_call["trace"]["span_id"] = event.get("span_id")
        elif event_type == "PolicyEvaluated":
            tool_call["policy"] = {
                "decision": payload.get("decision"),
                "rule_id": payload.get("rule_id"),
                "policy_version": payload.get("policy_version"),
            }
        elif event_type == "ToolExecutionFinished":
            tool_call["result"] = {"status": payload.get("status"), "output": payload.get("output")}
        elif event_type == "TraceSpanFinished" and payload.get("span_kind") == "tool_call":
            tool_call["result"].setdefault("status", payload.get("status"))
            tool_call["policy"].setdefault("decision", payload.get("decision"))
            tool_call["policy"].setdefault("reason", payload.get("reason"))
            tool_call["trace"].update({"duration_ms": payload.get("duration_ms"), "audit_status": payload.get("audit_status")})
        elif event_type == "TraceSpanFinished" and payload.get("span_kind") == "approval_gate":
            tool_call["approval"] = {
                "status": payload.get("status"),
                "approved": payload.get("approved"),
                "reason": payload.get("reason"),
                "timed_out": payload.get("timed_out"),
            }
        elif event_type == "TraceSpanFinished" and payload.get("span_kind") == "sandbox_execution":
            tool_call["sandbox"] = {
                "status": payload.get("status"),
                "isolation_level": payload.get("isolation_level"),
                "backend": payload.get("backend"),
                "available": payload.get("available"),
            }
    return [grouped[tool_call_id] for tool_call_id in order]


def _build_trace_tree(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: dict[tuple[str, str], dict[str, Any]] = {}
    order: list[tuple[str, str]] = []
    for event in events:
        if not str(event.get("event_type", "")).startswith("TraceSpan"):
            continue
        trace_id = event.get("trace_id")
        span_id = event.get("span_id")
        if not trace_id or not span_id:
            continue
        key = (trace_id, span_id)
        payload = event.get("payload", {})
        if key not in spans:
            spans[key] = {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": payload.get("parent_span_id"),
                "span_kind": payload.get("span_kind"),
                "status": payload.get("status"),
                "started_at": payload.get("started_at"),
                "finished_at": None,
                "duration_ms": None,
                "tool_name": event.get("tool_name"),
                "details": {},
                "children": [],
            }
            order.append(key)
        node = spans[key]
        node["parent_span_id"] = node.get("parent_span_id") or payload.get("parent_span_id")
        node["span_kind"] = node.get("span_kind") or payload.get("span_kind")
        node["tool_name"] = node.get("tool_name") or event.get("tool_name")
        node["status"] = payload.get("status") or node.get("status")
        node["started_at"] = payload.get("started_at") or node.get("started_at")
        node["finished_at"] = payload.get("finished_at") or node.get("finished_at")
        node["duration_ms"] = payload.get("duration_ms", node.get("duration_ms"))
        node["details"].update({key: value for key, value in payload.items() if key not in {"metadata"}})

    by_span_id = {node["span_id"]: node for node in spans.values()}
    roots: list[dict[str, Any]] = []
    for key in order:
        node = spans[key]
        parent = by_span_id.get(node.get("parent_span_id"))
        if parent and parent is not node:
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def _first_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    return next((event for event in events if event.get("event_type") == event_type), {})


def _first_payload(events: list[dict[str, Any]], event_type: str, span_kind: str) -> dict[str, Any]:
    for event in events:
        payload = event.get("payload", {})
        if event.get("event_type") == event_type and payload.get("span_kind") == span_kind:
            return payload
    return {}


def _metric(label: str, value: Any, class_name: str = "") -> str:
    class_attr = f' {class_name}' if class_name else ""
    return f'<div class="metric"><div class="metric-label">{_text(label)}</div><div class="metric-value{class_attr}">{_text(_display(value))}</div></div>'


def _row(label: str, value: str) -> str:
    return f'<div class="row"><div class="label">{_text(label)}</div><div>{value}</div></div>'


def _agent_explanation_html(view: dict[str, Any]) -> str:
    context = view["agent_context"]
    name = context.get("name") or view["overview"].get("agent_id")
    framework = context.get("framework") or view["overview"].get("framework")
    purpose = context.get("purpose")
    if name == "Production Incident Agent":
        explanation = (
            "Production Incident Agent 模拟生产 incident 排障场景里的 SRE/ops agent。"
            "它接收 checkout-api 延迟故障任务，按阶段读取 deployment 状态、错误日志、feature flag，"
            "在强隔离 sandbox 里执行 diagnostics，然后提出 rollback，并尝试一个未授权 hotfix 来验证 runtime 会拒绝高风险写操作。"
        )
        why = (
            "为什么用它测试 runtime：它不是单步 echo agent，而是在同一次 run 中组合 allow、approval、sandbox、explicit deny、audit 和 trace，"
            "更接近生产 agent 会遇到的治理路径。"
        )
    else:
        explanation = f"{_display(name)} 是一个 {_display(framework)} agent，用于展示一次 runtime-governed agent run。"
        why = _display(purpose)
    return (
        f'<p class="explanation-text">{_text(explanation)}</p>'
        f'{_row("Agent", _inline(name))}'
        f'{_row("Framework", _inline(framework))}'
        f'{_row("Purpose", _inline(purpose))}'
        f'{_row("为什么用它测试 runtime", _inline(why))}'
    )


def _phase_list(phases: list[str]) -> str:
    if not phases:
        return _inline(None)
    return '<div class="pills">' + "".join(f'<span class="pill">{_text(phase)}</span>' for phase in phases) + "</div>"


def _decision_list(decisions: list[str]) -> str:
    if not decisions:
        return _inline(None)
    return '<ol class="decision-list">' + "".join(f"<li>{_text(decision)}</li>" for decision in decisions) + "</ol>"


def _timeline_item(step: dict[str, Any]) -> str:
    return (
        "<li>"
        f'<div class="index">{step["index"]:02d}</div>'
        f'<div class="event-type">{_text(step["event_type"])}</div>'
        f'<div><span>{_text(step["summary"])}</span>'
        f'<div class="muted">{_text(step.get("tool_name") or step.get("span_id") or "")}</div></div>'
        "</li>"
    )


def _tool_call_html(tool_call: dict[str, Any]) -> str:
    return (
        f'<h3>{_text(tool_call.get("tool_name"))}</h3>'
        f'{_row("Input", _json_block(tool_call.get("input")))}'
        f'{_row("Policy", _json_block(tool_call.get("policy")))}'
        f'{_row("Approval", _json_block(tool_call.get("approval")))}'
        f'{_row("Sandbox", _json_block(tool_call.get("sandbox")))}'
        f'{_row("Result", _json_block(tool_call.get("result")))}'
        f'{_row("Trace", _json_block(tool_call.get("trace")))}'
    )


def _span_node_html(node: dict[str, Any]) -> str:
    status = node.get("status")
    children = "".join(_span_node_html(child) for child in node.get("children", []))
    child_block = f"<ul>{children}</ul>" if children else ""
    return (
        "<li>"
        f'<div class="span-title">{_text(node.get("span_kind"))} '
        f'<span class="{_status_class(status)}">{_text(status)}</span></div>'
        f'<div class="muted">{_text(node.get("span_id"))} · {_text(_duration(node.get("duration_ms")))} · {_text(node.get("tool_name") or "")}</div>'
        f"{child_block}"
        "</li>"
    )


def _policy_summary(policy: dict[str, Any]) -> str:
    decision = policy.get("decision")
    return f'<code class="{_status_class(decision)}">{_text(_display(decision))}</code> / {_text(_display(policy.get("reason")))} / rule={_text(_display(policy.get("rule_id")))}'


def _json_block(value: Any) -> str:
    return f'<pre class="json-beauty">{_json_value_html(value, 0)}</pre>'


def _code(value: Any) -> str:
    return f"<code>{_text(_display(value))}</code>"


def _inline(value: Any) -> str:
    return f"<span>{_text(_display(value))}</span>"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_value_html(value: Any, level: int) -> str:
    indent = "  " * level
    child_indent = "  " * (level + 1)
    if isinstance(value, dict):
        if not value:
            return '<span class="json-punctuation">{}</span>'
        rows = []
        for key in sorted(value):
            rows.append(
                f'{child_indent}<span class="json-key">{_text(json.dumps(str(key), ensure_ascii=False))}</span>'
                f'<span class="json-punctuation">: </span>{_json_value_html(value[key], level + 1)}'
            )
        return '<span class="json-punctuation">{</span>\n' + ",\n".join(rows) + f'\n{indent}<span class="json-punctuation">}}</span>'
    if isinstance(value, list):
        if not value:
            return '<span class="json-punctuation">[]</span>'
        rows = [f"{child_indent}{_json_value_html(item, level + 1)}" for item in value]
        return '<span class="json-punctuation">[</span>\n' + ",\n".join(rows) + f'\n{indent}<span class="json-punctuation">]</span>'
    if isinstance(value, str):
        return f'<span class="json-string">{_text(json.dumps(value, ensure_ascii=False))}</span>'
    if isinstance(value, bool):
        return f'<span class="json-boolean">{str(value).lower()}</span>'
    if value is None:
        return '<span class="json-null">null</span>'
    if isinstance(value, int | float):
        return f'<span class="json-number">{_text(json.dumps(value, ensure_ascii=False))}</span>'
    return f'<span class="json-string">{_text(json.dumps(str(value), ensure_ascii=False))}</span>'


def _text(value: Any) -> str:
    return escape(_display(value), quote=True)


def _display(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _duration(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value} ms"


def _status_class(status: Any) -> str:
    if status in {"success", "completed", "allow", "approved"}:
        return "ok"
    if status in {"failed", "denied", "deny", "rejected"}:
        return "deny"
    return ""
