# Agent Registry Contract

状态：Technical Preview  
日期：2026-06-18

## 目的

`register_agent(...)` 是 Agent Runtime 的正式 agent registration contract。它用于把一个外部 agent 纳入 runtime 治理，让 runtime 能记录 agent identity、capabilities、runtime profile、lifecycle events 和可选 tracing span。

注册 agent 后，provider 或 framework 仍然可以负责生成 tool call，但工具执行必须进入 `runtime.call_tool()`。

## Contract

```python
from agent_runtime import AgentMetadata, AgentRuntime, RuntimeProfile

registered_agent = runtime.register_agent(
    agent_id="glm-agent",
    agent=agent,
    actor={"id": "glm-agent"},
    environment="dev",
    metadata=AgentMetadata(
        agent_id="glm-agent",
        name="GLM tool caller",
        provider="glm",
        framework="openai-compatible",
        version="test",
        capabilities=["tool.invoke:echo"],
        runtime_profile=RuntimeProfile(
            environment="dev",
            execution_mode="runtime_tools",
            max_tool_calls=1,
            network_access=True,
        ),
    ),
)
```

## Agent Metadata

| 字段 | 含义 |
| --- | --- |
| `agent_id` | runtime 内的 agent 唯一标识 |
| `name` | 面向人类的 agent 名称 |
| `provider` | agent 背后的 provider，例如 `glm`、`openai`、`local` |
| `framework` | agent 技术栈，例如 `openai-compatible`、`langgraph` |
| `version` | agent 或测试夹具版本 |
| `description` | agent 描述 |
| `capabilities` | agent 预期会请求的能力，例如 `tool.invoke:echo` |
| `runtime_profile` | runtime 执行约束 |
| `lifecycle_events` | runtime 必须记录的 agent lifecycle events |

## Runtime Profile

| 字段 | 含义 |
| --- | --- |
| `environment` | 执行环境，例如 `dev`、`staging`、`prod` |
| `execution_mode` | 执行模式，当前使用 `runtime_tools` |
| `max_tool_calls` | 单次 agent run 的预期最大工具调用数 |
| `network_access` | agent/provider 是否需要网络 |
| `sandbox_required` | 是否要求 sandbox backend |
| `approval_required` | 是否要求 approval gate |

## Lifecycle Events

注册 agent 的一次运行应至少产生：

```text
AgentRegistered
AgentRunStarted
ToolCallRequested
PolicyEvaluated
ToolExecutionStarted
ToolExecutionFinished
AgentRunFinished
```

如果 policy deny，`ToolExecutionFinished` 不应出现，应该出现 `RuntimeError`，并且 agent 不能回落到 direct execution。

## Tracing Contract

当 runtime 配置 `tracing.enabled=true` 时，注册 agent 的一次运行还应产生 governed trace。它回答两个问题：

1. agent 做了什么。
2. runtime 为什么允许、为什么拒绝、是否强隔离、是否可审计。

最小 trace tree：

```text
TraceSpanStarted(span_kind=agent_run)
  TraceSpanStarted(span_kind=tool_call)
    TraceSpanStarted(span_kind=policy_evaluation)
    TraceSpanFinished(span_kind=policy_evaluation)
    TraceSpanStarted(span_kind=approval_gate)
    TraceSpanFinished(span_kind=approval_gate)
    TraceSpanStarted(span_kind=sandbox_execution)
    TraceSpanFinished(span_kind=sandbox_execution)
  TraceSpanFinished(span_kind=tool_call)
TraceSpanFinished(span_kind=agent_run)
```

`approval_gate` 只在 `require_approval` path 出现。`sandbox_execution` 只在 sandboxed tool path 出现。

trace 关系必须满足：

- agent-run span 和该 agent run 内的 tool-call span 使用同一个 `trace_id`。
- tool-call span 使用自己的 `span_id`。
- tool-call span payload 包含 `agent_id`。
- tool-call span payload 的 `parent_span_id` 指向 agent-run span 的 `span_id`。
- policy-evaluation span 的 `parent_span_id` 指向 tool-call span，并记录 `decision`、`reason`、`rule_id`、`capability` 和 `policy_version`。
- policy deny 时 tool-call span 也必须被关闭，payload 记录 `status=denied`、`decision=deny`、`reason` 和 `audit_status=committed`。
- approval-gate span 的 `parent_span_id` 指向 tool-call span，并记录 `approved`、`reason`、`timed_out`、`rule_id` 和 `risk_level`。
- sandbox-execution span 的 `parent_span_id` 指向 tool-call span，并记录 `isolation_level=strong`、`backend`、`available` 和 `status`。
- 成功 tool-call span finish payload 必须包含 `audit_status=committed`，用于说明该运行片段已经写入 audit sink。
- agent transcript 暴露 `trace_id` 和 `agent_span_id`，用于把业务输出、audit events 和 tracing 串起来。
- 如果 agent 自身抛出异常，runtime 仍然记录 `AgentRunFinished(status=failed)` 和 `TraceSpanFinished(span_kind=agent_run, status=failed)`，然后把原异常继续抛给调用方。

这个 contract 的目的不是替代 audit，而是让 observer、tracing backend 或 design partner runbook 能还原：

```text
registered_agent.run()
  -> provider/framework selects tool call
  -> runtime.call_tool()
  -> policy evaluation
  -> approval gate if required
  -> sandbox enforcement if required
  -> audit commit
  -> executor
```

## Deny-Path Contract

注册 agent 的工具调用被 policy deny 时：

- runtime 返回 `ToolResult(status="denied")`。
- 工具函数不执行。
- agent transcript 进入 `blocked`。
- audit 记录 `ToolCallRequested`、`PolicyEvaluated`、`RuntimeError`。
- 不允许自动 fallback 到 agent 自己的 direct tool function。

## Optional Framework Agents

LangGraph 等 framework agent 应使用同一 registration contract。framework 可以负责 graph execution 和 tool-call selection，但 tool execution 必须进入 runtime。
