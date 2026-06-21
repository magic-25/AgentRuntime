# Runtime Core API 稳定化 Spec

状态：Approved for P0 implementation  
日期：2026-06-21  
阶段：Technical Preview -> Design Partner Pilot

## 背景

项目最初目标是做一个通用的 agent runtime：agent 可以来自不同 provider、framework 或本地代码，但工具调用、policy、approval、sandbox、audit 和 tracing 必须进入同一个 runtime 治理链路。

当前项目已经补齐了大量测试报告、complete report 和运行可视化，但 core API 仍有一个明显短板：`register_agent(...).run()` 默认假设 agent 返回本项目测试 agent 的 transcript 对象。这会让开源用户误以为只有特定示例 agent 才能被 runtime 接管，不利于“通用 runtime”定位。

## 目标

1. 定义稳定的 agent execution session 结果契约。
2. 允许任意 Python agent 返回 `dict`、`str`、dataclass、framework transcript 或自定义对象。
3. 注册 agent 的运行结果必须统一暴露：
   - agent identity
   - metadata
   - status
   - output
   - tool results
   - trace id
   - agent span id
   - audit event list
   - error summary
4. 保持既有 `registered_agent.run(...)` 行为兼容。
5. 为后续其他语言 runtime 预留 JSON-friendly contract。

## 非目标

- 不在本阶段实现 hosted control plane。
- 不在本阶段实现多语言 SDK。
- 不改变 policy engine、approval gate、sandbox backend 的已有语义。
- 不移除现有 provider / framework agent 示例。

## 用户故事

### US-1：普通 Python agent 接入

作为开源用户，我有一个只返回 `dict` 的 agent。我希望它注册到 runtime 后能得到统一的 `AgentRunResult`，而不是必须实现项目内部 transcript 类型。

验收：

- `registered_agent.run_session("...")` 返回 `AgentRunResult`。
- `AgentRunResult.output` 保留原始 agent 输出。
- `AgentRunResult.status == "completed"`。
- audit 记录 `AgentRegistered`、`AgentRunStarted`、`AgentRunFinished`。

### US-2：已有示例 agent 兼容

作为现有项目使用者，我希望 `registered_agent.run(...)` 仍然返回原来的 transcript，不破坏测试、报告和对比文档。

验收：

- 现有 `registered_agent.run(...)` 测试保持通过。
- transcript 继续带有 `registration`、`agent_id`、`agent_metadata`、`trace_id`、`agent_span_id` 和 `audit_events`。

### US-3：失败运行可审计

作为 runtime operator，我希望 agent 自身抛异常时，runtime 仍然能生成一个失败的 session result，用于 runbook 和 UI 展示。

验收：

- `run_session(...)` 不把 agent 异常直接抛出给调用方。
- 返回 `AgentRunResult(status="failed", error="<ExceptionType>")`。
- audit/tracing 仍然记录 failed agent run finish。
- 旧 `run(...)` 继续把原异常抛出，维持兼容。

## Contract

新增公共模型：

```python
AgentRunRequest
AgentRunResult
```

新增公共方法：

```python
registered_agent.run_session(prompt: str | AgentRunRequest) -> AgentRunResult
runtime.run_agent(...) -> AgentRunResult
```

`run_session` 是推荐的新入口；`run` 是兼容入口。

## JSON 兼容性

`AgentRunResult.to_dict()` 必须返回可序列化结构的最佳努力表示，用于：

- complete report
- run view
- CLI export
- 未来 sidecar / remote executor
- 未来其他语言 SDK contract

## 安全与审计边界

- `run_session` 不绕过 `runtime.call_tool()`。
- policy deny 时仍然不能回落到 direct execution。
- agent 输出进入 result 前必须经过 runtime redaction。
- error 只暴露异常类型，不默认暴露可能含敏感信息的完整 traceback。

## P0 验收

- 增加 `AgentRunRequest` / `AgentRunResult`。
- `agent_runtime.__init__` 导出新模型。
- `compatibility.stable_public_api()` 能解析新模型。
- `RegisteredAgent.run_session(...)` 支持 arbitrary output。
- `AgentRuntime.run_agent(...)` 返回 `AgentRunResult`。
- 测试覆盖成功、失败、工具调用和旧 API 兼容。
