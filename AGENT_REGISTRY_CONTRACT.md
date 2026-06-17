# Agent Registry Contract

状态：Technical Preview  
日期：2026-06-18

## 目的

`register_agent(...)` 是 Agent Runtime 的正式 agent registration contract。它用于把一个外部 agent 纳入 runtime 治理，让 runtime 能记录 agent identity、capabilities、runtime profile 和 lifecycle events。

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

## Deny-Path Contract

注册 agent 的工具调用被 policy deny 时：

- runtime 返回 `ToolResult(status="denied")`。
- 工具函数不执行。
- agent transcript 进入 `blocked`。
- audit 记录 `ToolCallRequested`、`PolicyEvaluated`、`RuntimeError`。
- 不允许自动 fallback 到 agent 自己的 direct tool function。

## Optional Framework Agents

LangGraph 等 framework agent 应使用同一 registration contract。framework 可以负责 graph execution 和 tool-call selection，但 tool execution 必须进入 runtime。
