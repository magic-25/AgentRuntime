# Agent Runtime Real Agent 测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
产品状态：Technical Preview  
下一门禁：Design Partner Pilot

## 结论摘要

本报告覆盖自写 real agent loop 测试。它和 [SCENARIO_TEST_REPORT.md](SCENARIO_TEST_REPORT.md) 的区别是：

- 场景测试验证用户指南里的场景合同是否可运行。
- real-agent 测试验证 agent loop 会自己产生 tool call、拿到 runtime/pilot 结果后继续、停止或进入 blocked 状态。

本轮 real-agent 测试不调用外部 LLM provider，不需要 API key，不依赖网络，也不引入 LangGraph、AutoGen、CrewAI 等额外框架。它用于补齐“不是只测 runtime contract，而是至少有 agent-in-the-loop”的验证层。

## 测试文件

| 项目 | 值 |
| --- | --- |
| 测试工具 | `src/agent_runtime/testing/agents.py` |
| 测试文件 | `tests/test_real_agent_scenarios.py` |
| 执行命令 | `python -m pytest tests/test_real_agent_scenarios.py -q` |
| 用例数量 | 4 |
| 结果 | 4 passed |

## 测试输出

```text
....                                                                     [100%]
4 passed in 0.10s
```

## Agent 类型

| Agent | 作用 | 外部依赖 |
| --- | --- | --- |
| `ScriptedToolCallingAgent` | 按计划产生 runtime tool call，读取 result 后 stop 或 blocked | 无 |
| `CodeCIRealAgent` | 根据计划命令调用 Code/CI pilot，遇到 denied command 后 blocked | 无 |
| `OpsDiagnosticRealAgent` | 先调用只读诊断命令，再尝试未知写操作并记录 denied | 无 |
| `MCPStyleRealAgent` | 生成 MCP-style tool call，经 MCP adapter 翻译后进入 runtime | 无 |

## 用例矩阵

| ID | 用例 | 测试函数 | 关键验证 | 状态 |
| --- | --- | --- | --- | --- |
| RAG-001 | Scripted tool-calling agent | `test_scripted_tool_calling_agent_runs_loop_through_runtime_and_stops` | agent 决定调用 `echo`，runtime 执行，audit 记录 policy/execution，agent stop | verified |
| RAG-002 | Code/CI real agent | `test_code_ci_real_agent_runs_allowed_test_and_stops_on_denied_commit` | agent 先跑 allowlisted command，再遇到 `git commit` 被 blocked | verified |
| RAG-003 | Ops diagnostic real agent | `test_ops_diagnostic_real_agent_runs_readonly_command_and_records_denied_write` | agent 调用只读命令成功，再调用未知写操作 denied | verified |
| RAG-004 | MCP-style real agent | `test_mcp_style_real_agent_translates_tool_call_before_runtime_execution` | agent 生成 MCP payload，经 adapter 翻译进入 runtime，adapter 不授予 capability | verified |

## 用例详情

### RAG-001 Scripted Tool-Calling Agent

**用例设计**

构造一个最小 agent loop。agent 的计划里只有一步：调用 `echo` tool。agent 不直接调用函数，而是通过 `runtime.call_tool` 进入 policy/audit/executor 链路。

**输出结果**

- transcript status：`completed`
- decisions：`["call:echo", "stop"]`
- tool result output：`{"message": "hello"}`
- audit events 包含 `PolicyEvaluated`
- audit events 包含 `ToolExecutionFinished`

**输出解释**

这证明 agent loop 不是绕过 runtime 调用函数，而是通过 runtime 产生可审计 tool call。

**结论**

通过。

### RAG-002 Code/CI Real Agent

**用例设计**

构造一个会执行命令计划的 Code/CI agent。第一步运行 allowlisted Python command，第二步尝试 `git commit`。

**输出结果**

- transcript status：`blocked`
- decisions：`["run:python", "blocked:command.denied"]`
- 第一个 pilot report：`success`
- 第二个 pilot report：`denied`
- denied command 的 `executed_commands == []`

**输出解释**

这证明 agent 能根据 pilot 返回的 denied 结果停止，不继续执行危险命令。

**结论**

通过。

### RAG-003 Ops Diagnostic Real Agent

**用例设计**

构造一个 ops diagnostic agent。它先调用 allowlisted 只读命令 `ops_status`，再尝试未知操作 `ops_restart`。

**输出结果**

- transcript status：`completed_with_denial`
- 第一个 tool result：`success`
- 第二个 tool result：`denied`
- decisions：`["call:ops_status", "call:ops_restart", "stop"]`

**输出解释**

这证明 ops agent 可以在同一 loop 中看到成功和 denied 结果，并把 denied 当作场景内可解释结果，而不是绕过 runtime。

**结论**

通过。

### RAG-004 MCP-Style Real Agent

**用例设计**

构造一个 MCP-style agent。agent 先生成 MCP tool call payload，再通过 `MCPAdapterPack` 翻译成 runtime tool call，最后进入 runtime 执行。

**输出结果**

- transcript status：`completed`
- adapter source：`mcp`
- capabilities granted：`[]`
- tool result status：`success`
- decisions：`["translate:mcp", "call:echo", "stop"]`

**输出解释**

这证明 MCP-style agent 的调用经过 adapter 翻译，adapter 没有授予 capability，也没有直接执行工具。

**结论**

通过。

## 未覆盖范围

| 范围 | 原因 |
| --- | --- |
| 真实 OpenAI / Anthropic API 调用 | 默认测试不能依赖 API key 和网络 |
| 真实 LangGraph graph execution | 当前先避免引入重依赖，后续可做 optional test extra |
| 真实 MCP server 进程 | 当前使用 MCP-style payload 和 adapter，后续可加轻量 MCP server fixture |
| AutoGen / CrewAI / 其他开源 agent 框架 | 依赖重且版本波动，适合作为 optional integration suite |
| hosted cloud agent runtime | 当前没有 hosted control plane 或 hosted executor |

## 后续建议

1. 增加匿名化真实 provider payload fixture。
2. 增加 optional LangGraph real graph test，不进默认 core test。
3. 增加轻量 MCP server fixture，验证真实 MCP request/response。
4. 将 Code/CI real agent 的 digest-only pilot report 升级为 runtime audit chain，或持续明确该边界。
