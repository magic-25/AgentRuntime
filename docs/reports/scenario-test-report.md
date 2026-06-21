# Agent Runtime 场景测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
产品状态：Technical Preview  
下一门禁：Design Partner Pilot

## 结论摘要

本报告只覆盖基于用户场景的 acceptance tests。它对应 [docs/user-guide.md](/docs/user-guide.md) 中的 11 个场景，目标是验证用户文档里描述的场景能否用当前代码表达和运行。

本轮场景测试结论：11 个场景测试全部通过。

```text
...........                                                              [100%]
11 passed in 0.22s
```

这些测试已经纳入全量回归：

```text
tests/test_scenario_based_user_guide.py ...........                      [ 97%]
166 passed in 36.09s
```

需要明确的边界：

- 场景测试不替代真实 design partner feedback。
- 场景测试不验证真实 provider SDK 全量 payload。
- 场景测试不证明 hosted control plane 已经存在。
- remote executor 场景的预期结果是 `contract_beta` 且不 production-ready。

## 测试文件

| 项目 | 值 |
| --- | --- |
| 测试文件 | `tests/test_scenario_based_user_guide.py` |
| 原始输出 | `.agent-runtime/test-report-2026-06-17/scenario-based-user-guide.txt` |
| 执行命令 | `python -m pytest tests/test_scenario_based_user_guide.py -q` |
| 用例数量 | 11 |
| 结果 | 11 passed |

## 测试设计

场景测试采用用户视角，而不是模块视角。每个测试都回答三个问题：

- 用户指南中的场景能否由当前代码表达。
- 场景的核心安全或治理边界是否被验证。
- 场景的 support level 是否没有被误读或过度承诺。

测试覆盖原则：

- 对“可实际跑”的场景，测试必须执行真实 runtime、pilot 或 conformance 路径。
- 对“contract/demo 可做”的场景，测试验证 contract 行为、fail closed、redaction、registry resolution 等语义。
- 对“contract beta”的场景，测试验证它保持 beta 边界，而不是测试它成功执行生产任务。

## 场景覆盖矩阵

| ID | 用户场景 | 测试函数 | 关键断言 | 状态 |
| --- | --- | --- | --- | --- |
| SCN-001 | 本地 Python Agent Runtime | `test_scenario_local_python_agent_runtime_runs_tool_through_policy_and_audit` | tool call 成功，audit 包含 policy 和 execution event | verified |
| SCN-002 | 本地 Command Tool 治理 | `test_scenario_local_command_tool_governance_applies_env_allowlist_and_audit_chain` | env allowlist 生效，secret 不进入 stdout，audit chain valid | verified |
| SCN-003 | Staging Internal Admin Agent | `test_scenario_staging_internal_admin_agent_covers_approval_deny_observer_and_audit` | approval timeout、unknown prod deny、observer、SQLite audit verify | verified |
| SCN-004 | Code/CI Agent Governance | `test_scenario_code_ci_agent_governance_allows_only_allowlisted_commands` | allowlisted command 成功，`git commit` denied，digest-only 边界明确 | verified |
| SCN-005 | Adapter Replay / Conformance | `test_scenario_adapter_replay_and_conformance_preserve_runtime_semantics` | adapter conformance passed，capability 不被授予，runtime semantics preserved | verified |
| SCN-006 | Container Sandbox Evidence | `test_scenario_container_sandbox_evidence_uses_stable_candidate_contract` | container stable candidate，abuse checks 存在，限制包含 no absolute escape prevention | verified |
| SCN-007 | Local Agent + Cloud Runtime Control Plane | `test_scenario_local_agent_cloud_control_plane_contract_fails_closed_and_redacts_exports` | prod fail closed，run export redacted，audit forwarding 保留本地 hash chain | verified |
| SCN-008 | MCP Tool Governance | `test_scenario_mcp_tool_governance_keeps_adapter_translate_only` | MCP adapter translate-only，no capability grant | verified |
| SCN-009 | Ops Diagnostic Read-Only Agent | `test_scenario_ops_diagnostic_read_only_agent_is_allowlisted_and_audited` | 只读命令 allowlisted，未知 prod tool denied，audit chain valid | verified |
| SCN-010 | Local Codex/IDE Agent Governance | `test_scenario_local_codex_ide_governance_combines_codex_adapter_and_code_ci_boundaries` | Codex adapter stable candidate，PR 操作 denied | verified |
| SCN-011 | Remote Executor Contract Beta | `test_scenario_remote_executor_remains_contract_beta_not_production_ready` | remote 保持 contract_beta，passed=false，no production execution | verified |

## 用例详情

### SCN-001 本地 Python Agent Runtime

**用例设计**

验证最小 Python agent runtime 场景：用户注册 Python function tool，tool call 经过 policy，再进入 audit。

**测试函数**

```text
test_scenario_local_python_agent_runtime_runs_tool_through_policy_and_audit
```

**输入与步骤**

- 创建 JSONL audit sink。
- 配置 default deny。
- 添加 `tool.invoke:echo` 和 `message.echo` 的 allow policy。
- 注册 `echo` function tool。
- 调用 `runtime.call_tool("echo")`。

**输出结果**

- `result.status == "success"`
- `result.output == {"message": "hello"}`
- audit events 包含 `PolicyEvaluated`
- audit events 包含 `ToolExecutionFinished`

**输出解释**

这证明本地 Python function tool 没有绕过 runtime，policy evaluation 和 tool execution lifecycle 都进入 audit。

**结论**

通过。

### SCN-002 本地 Command Tool 治理

**用例设计**

验证 command tool 的 env allowlist 和 audit chain。这个场景关注 agent 执行本地命令时是否能限制环境变量泄漏。

**测试函数**

```text
test_scenario_local_command_tool_governance_applies_env_allowlist_and_audit_chain
```

**输入与步骤**

- 注册 `check_status` command tool。
- 注入 `ALLOWED=yes` 和 `SECRET=must-not-leak`。
- env allowlist 只允许 `ALLOWED`。
- 执行 tool call。
- 验证 JSONL audit chain。

**输出结果**

- stdout 包含 `ALLOWED=yes`
- stdout 不包含 `must-not-leak`
- `verify_audit_chain(...).valid is True`

**输出解释**

这证明 command tool 的 env allowlist 生效，并且命令执行进入可验证 audit chain。

**结论**

通过。

### SCN-003 Staging Internal Admin Agent

**用例设计**

验证 staging admin 场景中的 read、write approval、approval timeout、unknown prod deny、observer 和 SQLite audit。

**测试函数**

```text
test_scenario_staging_internal_admin_agent_covers_approval_deny_observer_and_audit
```

**输入与步骤**

- 调用 `examples.staging_internal_admin_pilot.run_pilot(tmp_path, reset=True)`。
- 检查 read、approved write、timed out write、unknown prod tool。
- 验证 SQLite audit hash chain。
- 检查 observer counters。

**输出结果**

- `read_customer.status == "success"`
- `approved_write.status == "success"`
- `timed_out_write.status == "rejected"`
- `timed_out_write.error == "approval.timeout"`
- `unknown_prod_tool.status == "denied"`
- SQLite audit chain valid
- `approval_requests == 2`
- `approval_rejected == 1`
- `denied == 1`

**输出解释**

这证明 staging admin 场景能同时覆盖 approval、deny、observer 和 audit chain。

**结论**

通过。

### SCN-004 Code/CI Agent Governance

**用例设计**

验证 Code/CI reference pilot 只能执行 allowlisted command，并拒绝 commit 类操作。

**测试函数**

```text
test_scenario_code_ci_agent_governance_allows_only_allowlisted_commands
```

**输入与步骤**

- 创建 allowlisted Python command。
- 运行该 command。
- 再尝试运行 `git commit`。

**输出结果**

- allowlisted command `status == "success"`
- `network_access is False`
- `commit_push_pr_denied is True`
- `audit_mode == "digest-only"`
- `git commit` 返回 `status == "denied"`
- `error == "command.denied"`
- denied command 的 `executed_commands == []`

**输出解释**

这证明 Code/CI pilot 的核心边界有效：只跑 allowlisted command，不执行 commit/push/PR 类操作。`digest-only` 是当前已知审计边界。

**结论**

通过。

### SCN-005 Adapter Replay / Conformance

**用例设计**

验证 OpenAI、Anthropic、LangGraph、MCP、Codex adapter 的 conformance，并用 Code/CI replay 验证 runtime semantics。

**测试函数**

```text
test_scenario_adapter_replay_and_conformance_preserve_runtime_semantics
```

**输入与步骤**

- 运行 `AdapterConformanceRunner().run_all()`。
- 运行 `run_replay("code-ci", adapter_ids=["openai", "langgraph", "codex"])`。

**输出结果**

- conformance passed
- adapter 集合包含 `openai`、`anthropic`、`langgraph`、`mcp`、`codex`
- replay passed
- 所有 replay path 的 `capabilities_granted == []`
- 所有 replay path 的 `runtime_semantics == "policy_audit_sandbox_preserved"`

**输出解释**

这证明 adapter 层保持 translate-only，不向 tool call 额外授予 capability，也不改变 runtime 语义。

**结论**

通过。

### SCN-006 Container Sandbox Evidence

**用例设计**

验证 container backend 的 stable candidate contract，而不是验证绝对逃逸防护。

**测试函数**

```text
test_scenario_container_sandbox_evidence_uses_stable_candidate_contract
```

**输入与步骤**

- 运行 `SandboxConformanceRunner().run_backend(backend_for_name("container"))`。
- 检查 support level、abuse checks 和 limitations。

**输出结果**

- `passed is True`
- `support_level == "stable_candidate"`
- checks 包含 `abuse.path_traversal`
- checks 包含 `abuse.credential_path`
- limitations 包含 `no_absolute_escape_prevention`

**输出解释**

这证明 container backend contract 能覆盖关键 abuse checks，同时明确不承诺绝对逃逸防护。

**结论**

通过。

### SCN-007 Local Agent + Cloud Runtime Control Plane

**用例设计**

验证当前推荐 cloud 场景的 contract 语义：本地执行保留，cloud/control plane 负责 policy、registry、audit forwarding、run export。该测试不假设 hosted control plane 已存在。

**测试函数**

```text
test_scenario_local_agent_cloud_control_plane_contract_fails_closed_and_redacts_exports
```

**输入与步骤**

- validate policy bundle。
- 模拟 prod platform unavailable。
- 模拟 audit forwarding failed。
- 导出 redacted run payload。
- 验证 registry remote disabled 和 local allowlist。

**输出结果**

- policy bundle valid。
- prod platform unavailable 返回 deny。
- `fail_closed is True`
- audit forwarding failed 时 local hash chain 保留。
- run export payload 为 `{"redacted": True}`。
- remote disabled 覆盖 local allowlist。
- local allowlist 可以启用未被 remote disabled 的 pack。

**输出解释**

这证明 cloud control plane 场景当前能以 contract 形式验证 fail closed、redaction、registry resolution 和 local hash chain 保留。

**结论**

通过。

### SCN-008 MCP Tool Governance

**用例设计**

验证 MCP adapter 不直接执行工具、不授予 capability，只做 tool call shape 翻译。

**测试函数**

```text
test_scenario_mcp_tool_governance_keeps_adapter_translate_only
```

**输入与步骤**

- 运行 `AdapterConformanceRunner().run_adapters(["mcp"])`。
- 检查 MCP support level 和 checks。

**输出结果**

- conformance passed。
- `support_level == "stable_candidate"`
- checks 包含 `translate_only`
- checks 包含 `no_capability_grant`

**输出解释**

这证明 MCP tool governance 场景的关键边界存在：MCP adapter 不给工具调用新增权限。

**结论**

通过。

### SCN-009 Ops Diagnostic Read-Only Agent

**用例设计**

验证 ops diagnostic 只读命令可 allowlist，未知 prod 操作被拒绝，并进入 audit chain。

**测试函数**

```text
test_scenario_ops_diagnostic_read_only_agent_is_allowlisted_and_audited
```

**输入与步骤**

- 注册 `ops_status` command tool。
- 配置 `ops.read` allow policy。
- 执行 `ops_status`。
- 尝试执行未知 `ops_restart`。
- 验证 JSONL audit chain。

**输出结果**

- `ops_status.status == "success"`
- stdout 包含 `status=ok`
- `ops_restart.status == "denied"`
- audit chain valid

**输出解释**

这证明 ops diagnostic 场景可以限制在 read-only allowlist 内，并且未知 prod 操作不会被允许。

**结论**

通过。

### SCN-010 Local Codex/IDE Agent Governance

**用例设计**

验证 Codex workspace adapter 的 conformance，并组合 Code/CI pilot 的 PR 操作拒绝边界。

**测试函数**

```text
test_scenario_local_codex_ide_governance_combines_codex_adapter_and_code_ci_boundaries
```

**输入与步骤**

- 运行 Codex adapter conformance。
- 尝试执行 `gh pr`。

**输出结果**

- Codex conformance passed。
- Codex support level 是 `stable_candidate`。
- checks 包含 `no_capability_grant`。
- `gh pr` 返回 `status == "denied"`。
- `error == "command.denied"`。

**输出解释**

这证明本地 Codex/IDE governance 场景可以同时验证 adapter 权限边界和 PR 操作拒绝边界。

**结论**

通过。

### SCN-011 Remote Executor Contract Beta

**用例设计**

验证 remote executor 继续保持 contract beta，不被误认为 production-ready backend。

**测试函数**

```text
test_scenario_remote_executor_remains_contract_beta_not_production_ready
```

**输入与步骤**

- 运行 remote backend sandbox conformance。
- 检查 support level、passed、failure reasons 和 limitations。

**输出结果**

- `support_level == "contract_beta"`
- `passed is False`
- failure reasons 包含 `remote.contract_beta_only`
- limitations 包含 `no_production_execution`

**输出解释**

这是一个预期失败边界测试。它证明 remote executor 没有被升级为 stable candidate 或 production-ready。

**结论**

通过。

## 未测试范围

| 范围 | 原因 |
| --- | --- |
| 真实外部 design partner 工作流 | 当前测试运行在本地仓库和本地临时目录 |
| 真实 provider SDK 全量 payload | 当前使用 conformance sample payload 和 replay fixture |
| hosted control plane | 当前没有 hosted control plane，实现的是 contract 和 simulation |
| production remote executor | 当前 remote executor 是 contract beta |
| 绝对 sandbox escape prevention | 当前测试只验证 contract 和 limitations，不验证绝对逃逸防护 |

## 总结

场景测试已经独立成套，并纳入全量回归。它把用户指南里的 11 个场景转成可运行 acceptance tests，能持续防止文档描述和代码能力漂移。

真实 agent loop 测试单独见 [docs/reports/real-agent-test-report.md](/docs/reports/real-agent-test-report.md)。场景测试验证“场景合同”，real-agent 测试验证“agent 自己产生 tool call 并根据结果继续或停止”。

下一步建议：

- 为真实 provider payload 增加 scenario fixture。
- 将 Code/CI pilot 从 digest-only report 升级到 runtime audit chain，或继续在场景报告中明确边界。
- 找一个真实 design partner repo 复用这套场景测试思路。
