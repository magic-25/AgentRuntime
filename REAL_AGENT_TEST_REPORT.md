# Agent Runtime Real Agent 测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
产品状态：Technical Preview  
下一门禁：Design Partner Pilot

## 结论摘要

本报告覆盖两类 real-agent 测试。它和 [SCENARIO_TEST_REPORT.md](SCENARIO_TEST_REPORT.md) 的区别是：

- 场景测试验证用户指南里的场景合同是否可运行。
- real-agent 测试验证 agent loop 会自己产生 tool call、拿到 runtime/pilot 结果后继续、停止或进入 blocked 状态。

本轮新增了 OpenAI-compatible provider agent 测试，用于覆盖 GLM/Z.AI 这类真实 LLM provider 的 tool-calling 形态。默认测试不调用外部 LLM provider、不需要 API key、不依赖网络；真实 GLM provider 调用作为 optional integration test，只有显式设置 `GLM_API_KEY` 或 `ZAI_API_KEY` 时才运行。

重要安全约束：

- API key 不写入可提交文件。
- 本地 key 可以写入 ignored `.env`。
- API key 不写入测试报告。
- API key 不通过命令行示例展示。
- 真实 provider 测试只读取环境变量。
- audit payload 只记录 runtime tool call，不记录 provider secret。

## 测试文件

| 项目 | 值 |
| --- | --- |
| 测试工具 | `src/agent_runtime/testing/agents.py`，`src/agent_runtime/testing/provider_agents.py` |
| 测试文件 | `tests/test_real_agent_scenarios.py`，`tests/test_provider_real_agent.py` |
| 默认执行命令 | `python -m pytest tests/test_real_agent_scenarios.py tests/test_provider_real_agent.py -q` |
| 真实 GLM provider 命令 | 设置 `GLM_API_KEY` 或 `ZAI_API_KEY` 后运行 `python -m pytest tests/test_provider_real_agent.py::test_glm_provider_agent_can_call_real_provider_when_key_is_configured -q` |
| 本地 `.env` 用例数量 | 19 passed |
| 结果 | 默认无 key 时真实 provider 测试跳过；本地 `.env` 有 key 时真实 provider 测试通过 |

## 测试输出

```text
...................                                                      [100%]
19 passed in 28.86s
```

## Agent 类型

| Agent | 作用 | 外部依赖 |
| --- | --- | --- |
| `ScriptedToolCallingAgent` | 按计划产生 runtime tool call，读取 result 后 stop 或 blocked | 无 |
| `CodeCIRealAgent` | 根据计划命令调用 Code/CI pilot，遇到 denied command 后 blocked | 无 |
| `OpsDiagnosticRealAgent` | 先调用只读诊断命令，再尝试未知写操作并记录 denied | 无 |
| `MCPStyleRealAgent` | 生成 MCP-style tool call，经 MCP adapter 翻译后进入 runtime | 无 |
| `OpenAICompatibleToolCallingAgent` | 构造 OpenAI-compatible chat/completions 请求，解析 provider 返回的 `tool_calls`，再交给 runtime 执行 | 默认无；真实 GLM integration 需要 `GLM_API_KEY` 或 `ZAI_API_KEY` |
| `LangGraphToolCallingAgent` | 执行 LangGraph graph，由 graph 选择 tool call，再对比未注册 direct execution 和注册后 runtime execution | optional `langgraph` |

## 测试 Agent 说明

这些测试 agent 不是产品内置的业务 agent，也不是面向用户长期使用的 agent 模板。它们是测试夹具，用来模拟真实生产中常见的 agent 行为，并验证 Agent Runtime 是否能接住这些行为。

| Agent | 模拟的真实角色 | 它会做什么 | 为什么需要它 |
| --- | --- | --- | --- |
| `ScriptedToolCallingAgent` | 最小工具调用 agent | 按预设步骤生成 tool call，收到 runtime result 后停止或 blocked | 验证最小 agent loop 是否必须经过 runtime，而不是直接调函数 |
| `CodeCIRealAgent` | 代码/CI agent | 按命令计划执行测试命令，遇到未授权的 `git commit` 后停止 | 验证 Code/CI agent 不会绕过 allowlist 执行写操作 |
| `OpsDiagnosticRealAgent` | 运维诊断 agent | 先调用只读状态检查，再尝试未知写操作 | 验证只读诊断和危险操作能在同一 agent run 中被区分 |
| `MCPStyleRealAgent` | MCP tool-calling agent | 生成 MCP-style payload，经 MCP adapter 翻译后进入 runtime | 验证 MCP adapter 只翻译、不授权、不执行 |
| `OpenAICompatibleToolCallingAgent` | 真实 provider tool-calling agent | 向 GLM/Z.AI 或 fake OpenAI-compatible transport 发起 chat/completions 请求，解析 `tool_calls`，再决定走 runtime 或 direct tool | 验证真实 LLM provider 产生的 tool call 是否能被 runtime 治理 |
| `LangGraphToolCallingAgent` | LangGraph framework agent | 调用已编译 LangGraph `StateGraph`，读取 graph 输出的 tool name 和 arguments | 验证 framework agent 接入 runtime registration contract |

### `OpenAICompatibleToolCallingAgent` 的具体行为

这个 agent 是当前最接近真实生产 agent 的测试对象。它有两种运行方式：

- **未注册模式**：agent 请求 GLM provider，解析 provider 返回的 `tool_calls`，然后直接调用本地工具函数，例如 `direct_echo()`。
- **注册模式**：agent 先通过 `runtime.register_agent("glm-agent", agent, ...)` 注册，然后仍然请求 GLM provider，但工具调用必须进入 `runtime.call_tool()`。

它不会把 API key 写进 audit、报告或可提交文件。真实 provider 测试只从 shell 环境或 ignored `.env` 读取 key。

### 为什么测试 agent 不做复杂业务

本轮测试故意选择 `echo`、Code/CI command、ops status 这类小工具，不是因为真实业务简单，而是为了把验证焦点放在 runtime 边界上：

- agent 是否真的产生 tool call。
- tool call 是否进入 runtime。
- policy 是否能 allow/deny。
- audit 是否能记录 agent lifecycle 和 tool lifecycle。
- provider key 是否不会泄漏。
- 未注册 agent 和注册 agent 的执行过程是否可区分。

## 用例矩阵

| ID | 用例 | 测试函数 | 关键验证 | 状态 |
| --- | --- | --- | --- | --- |
| RAG-001 | Scripted tool-calling agent | `test_scripted_tool_calling_agent_runs_loop_through_runtime_and_stops` | agent 决定调用 `echo`，runtime 执行，audit 记录 policy/execution，agent stop | verified |
| RAG-002 | Code/CI real agent | `test_code_ci_real_agent_runs_allowed_test_and_stops_on_denied_commit` | agent 先跑 allowlisted command，再遇到 `git commit` 被 blocked | verified |
| RAG-003 | Ops diagnostic real agent | `test_ops_diagnostic_real_agent_runs_readonly_command_and_records_denied_write` | agent 调用只读命令成功，再调用未知写操作 denied | verified |
| RAG-004 | MCP-style real agent | `test_mcp_style_real_agent_translates_tool_call_before_runtime_execution` | agent 生成 MCP payload，经 adapter 翻译进入 runtime，adapter 不授予 capability | verified |
| RAG-005 | GLM/OpenAI-compatible provider agent | `test_openai_compatible_provider_agent_executes_model_tool_call_through_runtime` | provider 返回真实 tool-call shape，agent 解析后通过 runtime 执行 `echo` | verified |
| RAG-006 | Provider no-tool-call boundary | `test_openai_compatible_provider_agent_blocks_when_model_returns_no_tool_call` | provider 未返回 tool call 时 agent blocked，不绕过 runtime | verified |
| RAG-007 | GLM secret boundary | `test_glm_provider_agent_factory_requires_api_key` | 未设置环境变量时拒绝构造真实 provider agent，不使用硬编码 secret | verified |
| RAG-008 | Ignored `.env` loading | `test_glm_provider_agent_factory_reads_ignored_dotenv_file` | factory 可读取 ignored `.env`，不要求把 key export 到 shell | verified |
| RAG-009 | Provider error redaction | `test_openai_compatible_transport_redacts_api_key_from_provider_errors` | provider HTTP error detail 中如果出现 API key，异常消息会替换成 `[REDACTED]` | verified |
| RAG-010 | Real GLM provider integration | `test_glm_provider_agent_can_call_real_provider_when_key_is_configured` | 设置 `GLM_API_KEY` 或 `ZAI_API_KEY` 后，请真实 provider 产生 tool call 并进入 runtime | optional |
| RAG-011 | Fake provider agent registration comparison | `test_same_agent_registration_comparison_with_fake_provider` | 同一个 agent 未注册时直连工具，注册后进入 runtime lifecycle/audit | verified |
| RAG-012 | Real GLM agent registration comparison | `test_same_agent_unregistered_vs_registered_runtime_execution` | 同一个真实 GLM agent 未注册运行 vs 注册到 Agent Runtime 后运行 | verified with local `.env` |
| RAG-013 | Agent registry contract | `test_register_agent_records_formal_metadata_profile_capabilities_and_lifecycle` | `AgentMetadata`、`RuntimeProfile`、capabilities、lifecycle events 进入 audit | verified |
| RAG-014 | Registered agent deny path | `test_registered_agent_deny_path_cannot_fall_back_to_direct_execution` | policy deny 时工具不执行，注册 agent 不回落 direct execution | verified |
| RAG-015 | Provider retry/backoff | `test_openai_compatible_transport_retries_transient_network_errors`，`test_openai_compatible_transport_retries_429_and_5xx_then_redacts_final_error` | EOF、429、5xx 使用 backoff retry，最终错误 redacts key | verified |
| RAG-016 | LangGraph optional framework agent | `test_langgraph_agent_compares_unregistered_and_registered_runtime_execution` | LangGraph graph 未注册直连工具，注册后进入 runtime lifecycle/audit | verified |

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

### RAG-005 GLM/OpenAI-Compatible Provider Agent

**用例设计**

构造一个 OpenAI-compatible provider agent。agent 向 chat/completions transport 发送带 `tools` 和 `tool_choice=auto` 的请求，收到 provider 形态的 `tool_calls` 后解析 tool name 和 arguments，再调用 `runtime.call_tool`。

默认测试使用 fake transport，不调用外部网络。fake transport 返回的 payload 使用真实 OpenAI-compatible tool-call 结构：

- `choices[0].message.tool_calls[0].function.name`
- `choices[0].message.tool_calls[0].function.arguments`

**输出结果**

- transcript status：`completed`
- provider：`glm`
- model：`glm-5.2`
- raw tool name：`echo`
- raw arguments：`{"message": "hello from provider"}`
- tool result status：`success`
- decisions：`["request:glm", "tool_call:echo", "runtime:success", "stop"]`

**输出解释**

这证明测试不再只是自写 loop：agent 的输入边界已经换成真实 provider 的 tool-call response shape。runtime 仍然负责执行、policy、audit 和 result，而 provider agent 不直接调用本地函数。

**结论**

通过。

### RAG-006 Provider No-Tool-Call Boundary

**用例设计**

provider 返回普通文本，不返回 `tool_calls`。agent 必须进入 blocked 状态，不能自己猜测工具调用，也不能绕过 runtime。

**输出结果**

- transcript status：`blocked`
- error：`provider.no_tool_call`
- tool results：`[]`
- decisions：`["request:glm", "blocked:provider.no_tool_call"]`

**输出解释**

这证明 provider 没有给出明确 tool call 时，agent 不会私自执行工具。

**结论**

通过。

### RAG-007 GLM Secret Boundary

**用例设计**

清除 `GLM_API_KEY` 和 `ZAI_API_KEY` 后创建 GLM provider agent。

**输出结果**

- 抛出 `ProviderAgentError`
- 错误信息要求设置 `GLM_API_KEY` 或 `ZAI_API_KEY`

**输出解释**

这证明真实 provider agent 不接受硬编码 key，也不会从仓库文件读取 secret。

**结论**

通过。

### RAG-008 Ignored `.env` Loading

**用例设计**

在临时目录创建 `.env`，写入 `GLM_API_KEY`、`GLM_BASE_URL` 和 `GLM_MODEL`。factory 在没有 shell 环境变量时读取该 `.env`。

**输出结果**

- transport api key：来自 `.env`
- transport base url：来自 `.env`
- model：来自 `.env`

**输出解释**

这证明真实 provider integration 可以使用仓库根目录的 ignored `.env`，而不要求用户把 key export 到 shell。`.env.example` 可提交，真实 `.env` 被 `.gitignore` 排除。

**结论**

通过。

### RAG-009 Provider Error Redaction

**用例设计**

模拟真实 provider HTTP error body 中错误地包含 API key 的情况。transport 抛出的 `ProviderAgentError` 必须移除 key，只保留 `[REDACTED]`。

**输出结果**

- 异常类型：`ProviderAgentError`
- 异常字符串不包含原始 API key
- 异常字符串包含 `[REDACTED]`

**输出解释**

这证明 provider integration 即使遇到上游错误，也不会把本地 key 泄露到 pytest 输出、日志摘要或调用方异常消息里。

**结论**

通过。

### RAG-010 Real GLM Provider Integration

**用例设计**

当本地环境或 ignored `.env` 设置了 `GLM_API_KEY` 或 `ZAI_API_KEY` 时，测试会调用真实 GLM/Z.AI OpenAI-compatible chat/completions endpoint。prompt 要求模型只调用一次 `echo` tool，随后 agent 把 provider 返回的 tool call 交给 runtime 执行。

**默认输出结果**

- 未设置 key 时：`skipped`
- 设置 key 后：期望 transcript status 为 `completed`，raw tool name 为 `echo`，runtime tool result 为 `success`

**输出解释**

这是当前最接近真实 provider agent 的可执行验证。它不是默认 CI 的硬依赖，因为外部 API 会引入网络、额度、模型版本和服务可用性不确定性。

**运行方式**

不要把 key 写入可提交文件。推荐复制 `.env.example` 到 ignored `.env` 后运行：

```bash
cp .env.example .env
python -m pytest tests/test_provider_real_agent.py::test_glm_provider_agent_can_call_real_provider_when_key_is_configured -q
```

如果使用不同 endpoint 或模型，可以设置：

```bash
export GLM_BASE_URL="https://api.z.ai/api/paas/v4"
export GLM_MODEL="glm-5.2"
```

**结论**

默认跳过；具备 key 时可执行。

### RAG-011 Fake Provider Agent Registration Comparison

**用例设计**

使用 fake OpenAI-compatible provider response，构造同一个 `OpenAICompatibleToolCallingAgent`，分别执行：

- 未注册：agent 直接调用本地 `direct_echo()`。
- 已注册：`runtime.register_agent("glm-agent", agent, ...)` 后由 registered runner 执行。

**输出结果**

- unregistered：`registration=unregistered`，decisions 为 `request:glm -> tool_call:echo -> direct:success -> stop`，没有 `run_id`，没有 audit events。
- registered：`registration=registered`，`agent_id=glm-agent`，decisions 为 `request:glm -> tool_call:echo -> runtime:success -> stop`，有 `run_id`，audit events 包含 `AgentRegistered`、`AgentRunStarted`、`ToolCallRequested`、`PolicyEvaluated`、`ToolExecutionStarted`、`ToolExecutionFinished`、`AgentRunFinished`。

**输出解释**

这证明即使不调用真实 provider，默认测试也能验证“同一个 agent 未注册 vs 注册”的核心 runtime 语义。

详细报告见 [PROVIDER_RUNTIME_COMPARISON_REPORT.md](PROVIDER_RUNTIME_COMPARISON_REPORT.md)。

**结论**

通过。

### RAG-012 Real GLM Agent Registration Comparison

**用例设计**

使用真实 GLM provider。构造同一个 `glm-agent`，分别执行：

- 未注册：agent 请求 GLM，解析 tool call，然后直接调用本地函数。
- 已注册：同一个 agent 通过 `runtime.register_agent(...)` 注册，之后由 registered runner 执行，tool call 进入 `runtime.call_tool()`。

**输出结果**

- unregistered：业务输出成功，但 `run_id=null`，`audit_events=[]`。
- registered：业务输出成功，`run_id` 存在，audit events 包含 agent lifecycle 和 tool execution lifecycle。

**输出解释**

这比单独比较 tool call 更贴近真实生产使用方式：对比对象是同一个 agent 的完整执行过程，而不是单个 tool call。

详细报告见 [PROVIDER_RUNTIME_COMPARISON_REPORT.md](PROVIDER_RUNTIME_COMPARISON_REPORT.md)。

**结论**

通过。

## 未覆盖范围

| 范围 | 原因 |
| --- | --- |
| 真实 OpenAI / Anthropic API 调用 | 默认测试不能依赖 API key 和网络；当前只提供 GLM/Z.AI optional integration |
| 更多 LangGraph graph pattern | 当前只验证单节点 StateGraph 选择一个 tool call |
| 真实 MCP server 进程 | 当前使用 MCP-style payload 和 adapter，后续可加轻量 MCP server fixture |
| AutoGen / CrewAI / 其他开源 agent 框架 | 依赖重且版本波动，适合作为 optional integration suite |
| hosted cloud agent runtime | 当前没有 hosted control plane 或 hosted executor |

## 后续建议

1. 增加匿名化真实 provider payload fixture，覆盖 OpenAI、Anthropic、GLM、Codex 等更多 shape。
2. 增加轻量 MCP server fixture，验证真实 MCP request/response。
3. 增加更多 LangGraph graph pattern，例如多节点、条件边和多工具选择。
4. 将 Code/CI real agent 的 digest-only pilot report 升级为 runtime audit chain，或持续明确该边界。
