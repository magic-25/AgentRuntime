# Provider Agent 注册对比测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
测试对象：同一个 GLM/Z.AI OpenAI-compatible provider agent  
密钥来源：ignored `.env` 或 shell 环境变量，不提交 secret

## 结论摘要

本轮对比测试验证的是同一个 agent 的两种运行方式：

1. **未注册到 Agent Runtime**：agent 自己请求 GLM provider，自己解析 tool call，然后直接调用本地工具函数。
2. **注册到 Agent Runtime**：同一个 agent 先通过 `runtime.register_agent(...)` 注册，然后由 registered runner 执行；agent 仍然请求 GLM provider，但工具调用必须进入 Agent Runtime。

核心结论：未注册 agent 可以完成业务输出，但执行过程不进入统一治理链路。注册 agent 的业务输出相同，但多了 agent registration、agent run lifecycle、policy、audit、run id 和统一 `ToolResult`。

## 测试文件

| 项目 | 值 |
| --- | --- |
| 测试文件 | `tests/test_provider_real_agent.py` |
| fake provider 注册对比 | `test_same_agent_registration_comparison_with_fake_provider` |
| 真实 GLM 注册对比 | `test_same_agent_unregistered_vs_registered_runtime_execution` |
| provider agent | `OpenAICompatibleToolCallingAgent` |
| runtime API | `AgentRuntime.register_agent(...)` |
| provider | GLM/Z.AI OpenAI-compatible chat/completions |
| API key | 从 ignored `.env` 或 shell 环境变量读取 |

## 测试 Agent 是什么

本报告里的测试 agent 叫 `glm-agent`，实现类是 `OpenAICompatibleToolCallingAgent`。它模拟的是一个使用真实 LLM provider 的工具调用 agent，而不是 Agent Runtime 自己内置的业务 agent。

### `glm-agent` 的职责

`glm-agent` 做四件事：

1. 向 GLM/Z.AI OpenAI-compatible chat/completions endpoint 发送 prompt 和 tool schema。
2. 等待 provider 返回 `tool_calls`。
3. 解析 tool name 和 tool arguments。
4. 根据运行模式选择执行路径：
   - 未注册时：直接调用传入的本地工具函数。
   - 注册后：把 tool call 交给 `runtime.call_tool()`。

### `glm-agent` 不负责什么

`glm-agent` 不负责生产治理：

- 不自己做统一 policy。
- 不自己写 runtime audit。
- 不自己生成 runtime run id。
- 不自己维护 agent lifecycle。
- 不自己承担 sandbox / approval / audit sink 的职责。

这些能力是 Agent Runtime 在注册后提供的。

### 为什么用 `echo` 工具

`echo` 工具不是业务重点，它只是一个低风险、可重复、可断言的工具。它让测试能专注比较两件事：

- 同一个 agent 自己跑时，执行链路是什么样。
- 同一个 agent 注册进 runtime 后，执行链路多了哪些生产治理证据。

如果换成真实 CRM、CI、运维或文件系统工具，核心差异仍然一样：未注册 agent 是自己执行，注册 agent 的工具调用进入 runtime。

## 执行命令

```bash
python -m pytest tests/test_provider_real_agent.py -q
```

输出：

```text
.........                                                                [100%]
9 passed in 25.67s
```

单独运行真实 GLM 注册对比：

```bash
python -m pytest tests/test_provider_real_agent.py::test_same_agent_unregistered_vs_registered_runtime_execution -q
```

输出：

```text
.                                                                        [100%]
1 passed in 20.01s
```

## 对比摘要

脱敏摘要脚本输出如下。该输出不包含 API key。

```json
{
  "same_agent": "glm-agent",
  "unregistered_agent_run": {
    "registration": "unregistered",
    "status": "completed",
    "decisions": [
      "request:glm",
      "tool_call:echo",
      "direct:success",
      "stop"
    ],
    "tool_result": {
      "status": "success",
      "run_id": null,
      "output": {
        "message": "agent registration comparison"
      }
    },
    "audit_events": []
  },
  "registered_agent_run": {
    "registration": "registered",
    "agent_id": "glm-agent",
    "status": "completed",
    "decisions": [
      "request:glm",
      "tool_call:echo",
      "runtime:success",
      "stop"
    ],
    "tool_result": {
      "status": "success",
      "run_id_present": true,
      "output": {
        "message": "agent registration comparison"
      }
    },
    "audit_events": [
      "AgentRegistered",
      "AgentRunStarted",
      "ToolCallRequested",
      "PolicyEvaluated",
      "ToolExecutionStarted",
      "ToolExecutionFinished",
      "AgentRunFinished"
    ]
  }
}
```

## 执行过程对比

| 阶段 | 未注册 agent | 注册到 Agent Runtime 的 agent |
| --- | --- | --- |
| agent identity | 业务代码自己约定 | runtime 记录 `agent_id=glm-agent` |
| agent lifecycle | 无统一 lifecycle | `AgentRegistered`、`AgentRunStarted`、`AgentRunFinished` |
| provider request | agent 直接请求 GLM | 同一个 agent 直接请求 GLM |
| tool call parsing | agent 自己解析 | 同一个 agent 自己解析 |
| tool execution | agent 直接调用本地函数 | agent 调用进入 `runtime.call_tool()` |
| policy | 无统一 policy | `PolicyEvaluated` |
| audit | 无统一 audit | agent lifecycle + tool call audit |
| result | 本地函数返回值包装成 direct result | runtime 返回 `ToolResult` |
| run id | 无 | 有 |
| deny 能力 | 需要 agent 自己实现 | runtime policy 可拒绝 |

## 测试解释

### 未注册 Agent

同一个 `glm-agent` 不注册到 runtime。执行过程是：

```text
agent -> GLM provider -> tool_call:echo -> direct_echo()
```

结果：

- `registration=unregistered`
- `status=completed`
- decisions 为 `request:glm -> tool_call:echo -> direct:success -> stop`
- tool result 没有 `run_id`
- `audit_events=[]`

这说明 agent 自己运行时可以完成业务输出，但生产系统看不到统一的 agent lifecycle、policy 和 audit 证据。

### 注册到 Agent Runtime

同一个 `glm-agent` 通过 `runtime.register_agent(...)` 注册。执行过程是：

```text
runtime.register_agent(glm-agent)
registered_agent.run()
agent -> GLM provider -> tool_call:echo -> runtime.call_tool()
```

结果：

- `registration=registered`
- `agent_id=glm-agent`
- `status=completed`
- decisions 为 `request:glm -> tool_call:echo -> runtime:success -> stop`
- tool result 有 `run_id`
- audit events 包含：
  - `AgentRegistered`
  - `AgentRunStarted`
  - `ToolCallRequested`
  - `PolicyEvaluated`
  - `ToolExecutionStarted`
  - `ToolExecutionFinished`
  - `AgentRunFinished`

这说明注册 agent 后，provider 仍然负责生成 tool call，但执行权、审计和治理边界进入 runtime。

## 为什么这比 tool-call 级对比更准确

之前的对比是“同一个 tool call 走 runtime / 不走 runtime”。这能证明 policy 和 audit，但不够贴近真实使用方式。

这次对比是“同一个 agent 整体执行是否注册到 runtime”。它更准确地回答：

- agent 自己跑时发生了什么。
- agent 注册后 runtime 能看到什么。
- runtime 如何把 agent lifecycle 和 tool execution 串起来。
- 业务输出相同时，生产治理证据有什么差别。

## 风险与限制

- 当前 `register_agent(...)` 是最小 runtime registration API，用于证明 agent lifecycle 和 tool governance，还不是完整 hosted agent registry。
- 真实 provider 测试依赖网络、额度、模型可用性和 TLS 状态。
- provider integration tests 已捕获 transient transport error 并转为 skip，避免 pytest traceback 展开 request headers。
- 本轮只验证 GLM/Z.AI OpenAI-compatible provider，不代表 OpenAI、Anthropic、LangGraph、MCP、Codex 的真实 payload 全量兼容。

## 后续建议

1. 把 `register_agent(...)` 升级为正式 agent registry contract，定义 agent metadata、capabilities、runtime profile 和 lifecycle events。
2. 增加 registered agent deny-path 测试，证明注册 agent 在 policy deny 时无法直接落回 direct execution。
3. 给 provider transport 增加可配置 retry/backoff，专门处理网络 EOF、429、5xx。
4. 增加 LangGraph optional framework agent，对比 graph agent 未注册运行与注册运行的差异。
5. 把 agent registration comparison 纳入 design partner runbook。
