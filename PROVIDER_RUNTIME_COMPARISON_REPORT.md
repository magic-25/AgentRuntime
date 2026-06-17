# Provider Agent Runtime 对比测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
测试对象：GLM/Z.AI OpenAI-compatible provider agent  
密钥来源：ignored `.env` 或 shell 环境变量，不提交 secret

## 结论摘要

本轮对比测试验证了同一个真实 provider tool call 在三种路径下的差异：

1. **使用 Agent Runtime，policy allow**：工具执行成功，并产生 run id、policy decision、audit event 和统一 `ToolResult`。
2. **使用 Agent Runtime，policy deny**：同一个 provider tool call 被 runtime 拒绝，工具不执行，并产生 deny audit。
3. **不使用 Agent Runtime，裸函数直连**：工具能返回结果，但没有 policy、audit、run id、统一状态、adapter source 或拒绝能力。

核心结论：Agent Runtime 的价值不是“让 tool call 能跑”，而是让真实 provider agent 的 tool call 进入可治理、可拒绝、可审计、可追踪的生产链路。

## 测试文件

| 项目 | 值 |
| --- | --- |
| 测试文件 | `tests/test_provider_real_agent.py` |
| 对比测试 | `test_glm_provider_tool_call_comparison_with_and_without_runtime` |
| provider agent | `OpenAICompatibleToolCallingAgent` |
| provider | GLM/Z.AI OpenAI-compatible chat/completions |
| API key | 从 ignored `.env` 或 shell 环境变量读取 |

## 执行命令

```bash
python -m pytest tests/test_provider_real_agent.py -q
```

输出：

```text
.......                                                                  [100%]
7 passed in 15.04s
```

单独运行对比测试：

```bash
python -m pytest tests/test_provider_real_agent.py::test_glm_provider_tool_call_comparison_with_and_without_runtime -q
```

输出：

```text
.                                                                        [100%]
1 passed in 6.79s
```

## 对比摘要

脱敏摘要脚本输出如下。该输出不包含 API key。

```json
{
  "provider": "glm",
  "tool_call": {
    "name": "echo",
    "arguments": {
      "message": "runtime comparison"
    }
  },
  "with_runtime_allow": {
    "status": "success",
    "has_run_id": true,
    "output": {
      "message": "runtime comparison"
    },
    "audit_events": [
      "ToolCallRequested",
      "PolicyEvaluated",
      "ToolExecutionStarted",
      "ToolExecutionFinished"
    ]
  },
  "with_runtime_deny": {
    "status": "denied",
    "error": "default_decision",
    "output": null,
    "audit_events": [
      "ToolCallRequested",
      "PolicyEvaluated",
      "RuntimeError"
    ]
  },
  "without_runtime_direct": {
    "status_envelope": null,
    "policy_decision": null,
    "audit_events": [],
    "output": {
      "message": "runtime comparison"
    }
  }
}
```

## 详细对比

| 维度 | 使用 Agent Runtime | 不使用 Agent Runtime |
| --- | --- | --- |
| provider tool call | 支持，先解析真实 `tool_calls` | 支持，需要业务代码自己解析 |
| 执行入口 | `runtime.call_tool()` | 本地函数直接调用 |
| policy | 有，allow/deny 可配置 | 无，除非每个 agent 自己实现 |
| deny 行为 | `status=denied`，工具不执行 | 默认仍会执行 |
| audit | 有 `ToolCallRequested`、`PolicyEvaluated`、execution/error events | 无 |
| run id | 有 | 无 |
| result envelope | `ToolResult(status, output, error, run_id)` | 普通函数返回值 |
| adapter/provider source | 可记录 `adapter_source=glm` | 无统一位置 |
| 生产排障 | 可根据 audit 和 run id 复盘 | 只能靠应用自己打日志 |
| 安全边界 | provider 只产生意图，runtime 决定能否执行 | provider output 和业务执行更容易耦合 |

## 测试解释

### Runtime Allow

同一个 GLM provider tool call 进入 runtime，policy 允许 `echo` 工具执行。

结果：

- `status=success`
- 有 `run_id`
- 输出和裸函数一致
- audit 包含请求、策略评估、执行开始、执行完成

这说明 runtime 不改变正常业务输出，同时增加生产治理证据。

### Runtime Deny

同一个 GLM provider tool call 进入没有 allow rule 的 runtime。

结果：

- `status=denied`
- `error=default_decision`
- `output=null`
- audit 包含请求、策略评估、运行错误

这说明即使真实 provider 产生了工具调用，最终是否执行仍由 runtime policy 决定。

### Without Runtime

直接把 provider arguments 传给本地 `direct_echo()`。

结果：

- 输出成功
- 没有 run id
- 没有 policy decision
- 没有 audit events
- 没有统一 error/status envelope

这说明“不使用 runtime”更简单，但缺少生产环境最需要的治理和审计能力。

## 风险与限制

- 真实 provider 测试依赖网络、额度、模型可用性和 TLS 状态；本轮脱敏摘要脚本第一次遇到一次 TLS EOF，重试后成功。
- provider integration tests 已捕获 transient transport error 并转为 skip，避免 pytest traceback 展开 request headers。
- 本轮只验证 GLM/Z.AI OpenAI-compatible provider，不代表 OpenAI、Anthropic、LangGraph、MCP、Codex 的真实 payload 全量兼容。
- 裸函数直连对比是最小复现，不代表所有应用都会完全没有日志；它表达的是“不使用统一 runtime 时，需要每个 agent 自己重复实现治理能力”。

## 后续建议

1. 给 provider transport 增加可配置 retry/backoff，专门处理网络 EOF、429、5xx。
2. 收集匿名 provider payload fixture，把真实外部调用和可重复 replay 分开。
3. 增加 LangGraph optional framework agent，对比 framework graph 进入 runtime 与 framework 自执行 tool 的差异。
4. 把 provider/runtime 对比测试纳入 design partner runbook。
