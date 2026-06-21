# Design Partner Runbook

状态：Technical Preview  
日期：2026-06-18

## 目标

本 runbook 用于和 design partner 验证 Agent Runtime 是否能治理真实 agent execution。重点不是跑通 demo，而是验证：

- agent 是否能注册进 runtime。
- runtime 是否记录 agent lifecycle。
- runtime 是否能把 agent run 和 tool call 串成同一条 trace。
- policy deny 是否阻止工具执行。
- audit 是否能复盘 agent run。
- provider 网络波动是否被 retry/backoff 处理。
- framework agent 是否能作为 optional integration 接入。

## 准备

复制 `.env.example` 到 ignored `.env`，填入轮换后的本地 key：

```bash
cp .env.example .env
```

`.env` 不提交。`.env.example` 只保留空值和默认配置项。

## 场景一：GLM Provider Agent 注册对比

运行：

```bash
python -m pytest tests/test_provider_real_agent.py::test_same_agent_unregistered_vs_registered_runtime_execution -q
```

验证点：

- 未注册 agent 可以完成业务输出，但没有 `run_id` 和 audit events。
- 注册 agent 产生 `AgentRegistered`、`AgentRunStarted`、`AgentRunFinished`。
- 注册 agent 的 tool call 进入 `runtime.call_tool()`。

## 场景二：Governed Agent Tracing

运行：

```bash
python -m pytest \
  tests/test_tracing.py::test_registered_agent_emits_agent_run_trace_parenting_tool_span \
  tests/test_tracing.py::test_registered_agent_failure_finishes_agent_run_trace_span \
  tests/test_tracing.py::test_runtime_trace_explains_allowed_tool_policy_and_auditability \
  tests/test_tracing.py::test_runtime_trace_explains_denied_tool_without_execution \
  tests/test_tracing.py::test_runtime_trace_records_strong_sandbox_isolation \
  tests/test_tracing.py::test_runtime_trace_records_approval_gate_when_required \
  -q
```

验证点：

- 注册 agent 产生 `TraceSpanStarted(span_kind=agent_run)` 和 `TraceSpanFinished(span_kind=agent_run)`。
- tool call span 和 agent run span 使用同一个 `trace_id`。
- tool call span 的 `parent_span_id` 指向 agent run span。
- policy evaluation span 记录 allow/deny 的 `decision`、`reason`、`rule_id` 和 `policy_version`。
- policy deny 时 tool span 仍然关闭，并记录拒绝原因。
- approval gate span 记录 `approved`、`reason`、`timed_out`、`rule_id` 和 `risk_level`。
- sandbox execution span 记录 `isolation_level=strong`、backend 和可用状态。
- tool span finish 记录 `audit_status=committed`。
- agent 失败时仍然记录 `AgentRunFinished(status=failed)` 和失败的 agent run span finish。

## 场景三：Registered Agent Deny Path

运行：

```bash
python -m pytest tests/test_agent_registry_contract.py::test_registered_agent_deny_path_cannot_fall_back_to_direct_execution -q
```

验证点：

- policy deny 时工具不执行。
- agent 不回落到 direct execution。
- transcript status 为 `blocked`。
- audit 包含 `RuntimeError`。

## 场景四：Provider Retry / Backoff

运行：

```bash
python -m pytest tests/test_provider_real_agent.py::test_openai_compatible_transport_retries_transient_network_errors tests/test_provider_real_agent.py::test_openai_compatible_transport_retries_429_and_5xx_then_redacts_final_error -q
```

验证点：

- TLS EOF / network error 可 retry。
- 429 / 5xx 可 retry。
- 最终错误会 redact API key。
- retry delay 使用指数 backoff。

## 场景五：LangGraph Optional Framework Agent

如果已安装 `langgraph`，运行：

```bash
python -m pytest tests/test_langgraph_agent_registration.py -q
```

验证点：

- LangGraph graph 未注册时可直接执行工具。
- 注册到 runtime 后，graph 仍负责选择 tool call。
- 工具执行进入 `runtime.call_tool()`。
- audit 记录 agent lifecycle 和 tool lifecycle。

## 场景六：完整回归

运行：

```bash
python -m pytest -q
```

当前本地证据：

```text
208 passed in 39.72s
```

## Design Partner 记录要求

记录摘要即可，不提交 secret、原始 provider response 或客户数据。

建议记录：

- agent 类型和 provider/framework。
- 是否注册到 runtime。
- policy allow/deny 结果。
- audit event sequence。
- `trace_id`、agent run span、tool call span 和 `parent_span_id` 是否能串起来。
- retry/backoff 是否触发。
- 未覆盖或失败原因。
