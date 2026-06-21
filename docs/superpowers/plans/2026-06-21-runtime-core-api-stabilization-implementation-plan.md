# Runtime Core API 稳定化实现计划

状态：Approved for P0 implementation  
日期：2026-06-21

## 任务 1：模型契约

- 在 `src/agent_runtime/core/models.py` 增加 `AgentRunRequest`。
- 在 `src/agent_runtime/core/models.py` 增加 `AgentRunResult`。
- 两个模型提供 `to_dict()`。
- `AgentRunResult.output` 使用 runtime redaction 后的输出。

验收：

- 新模型可从 `agent_runtime` 顶层导入。
- 新模型进入 compatibility stable public API。

## 任务 2：运行入口

- 在 `RegisteredAgent` 增加 `run_session(prompt)`。
- 支持 `str` 和 `AgentRunRequest` 输入。
- agent 成功返回任意对象时包装为 `AgentRunResult(status="completed")`。
- agent 抛异常时返回 `AgentRunResult(status="failed", error="<ExceptionType>")`。
- 保持旧 `run(prompt)` 行为不变。

验收：

- arbitrary-output agent 测试通过。
- failing agent 测试通过。
- legacy `run` 测试通过。

## 任务 3：Runtime convenience API

- 在 `AgentRuntime` 增加 `run_agent(...)`。
- 内部调用 `register_agent(...).run_session(...)`。

验收：

- 单次注册并运行可以直接获得 `AgentRunResult`。

## 任务 4：文档同步

- 更新 `AGENT_REGISTRY_CONTRACT.md`。
- 更新 `README.md` 当前能力。
- 更新 `CHANGELOG.md`。

## 任务 5：验证

- 新增单元测试。
- 跑 targeted tests。
- 跑 `ruff check`。
- 跑 `pyright src`。
- 跑 full pytest。
