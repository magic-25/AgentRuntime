# Agent Runtime 测试报告

报告日期：2026-06-17  
报告状态：公开测试报告  
产品状态：Technical Preview  
下一门禁：Design Partner Pilot

## 结论摘要

本轮测试结论：当前仓库在 core regression、scenario-based acceptance、real-agent loop、真实 provider agent optional integration、platform-ready certification、adapter contract、sandbox contract、platform simulation、Code/CI reference pilot、staging internal admin pilot、audit verify 和 observer status 这些关键路径上均有新鲜证据。

本轮没有发现阻塞 Technical Preview 或 design partner pilot 准备的回归。

需要明确的边界：

- Code/CI reference pilot 当前是 `digest-only` report，不是完整 runtime audit chain。
- `remote_executor` 当前是 `contract_beta`，相关 conformance 返回 `passed=false` 是预期边界，不是回归。
- Docker smoke evidence 不证明绝对 sandbox escape prevention。
- 当前没有验证真实 provider SDK 全量 payload，也没有验证 hosted control plane；GLM/Z.AI provider integration 已提供 optional test，本轮使用 ignored `.env` 中的本地 key 执行了真实外部调用。

## 测试环境

| 项目 | 值 |
| --- | --- |
| 工作目录 | Agent Runtime 仓库根目录 |
| 日期 | 2026-06-17 |
| Python | 3.12.9 |
| pytest | 9.0.2 |
| Docker client | `Docker version 28.0.1, build 068a01e` |
| Docker server | `28.0.1` |
| 证据目录 | `.agent-runtime/test-report-2026-06-17/` |

说明：证据目录属于本地运行产物，不提交。测试报告只提交摘要、解释和可复现命令。

## 测试设计

测试设计分为十层：

1. **Regression**：使用全量 `pytest` 覆盖 core、policy、audit、adapter、sandbox、platform、pilot 等现有测试。
2. **Scenario-Based Acceptance**：把 `USER_GUIDE.md` 的 11 个场景映射成用户视角测试。
3. **Certification**：使用 `certify run` 验证 stable candidate subject 是否仍具备 evidence。
4. **Adapter Contract**：验证 adapter 是否保持 translate-only、不授予 capability、不绕过 runtime semantics。
5. **Sandbox Contract**：验证 container、sidecar、remote 三类 backend 的 support level 和边界。
6. **Runtime Evidence**：验证 Docker runtime smoke evidence 是否能生成，并解释其限制。
7. **Platform Contract**：验证 platform failure simulation 覆盖 control plane 相关失败模式。
8. **Real-Agent Loop**：验证自写 agent loop 会产生 tool call、读取结果并继续或停止。
9. **Provider-Agent Optional Integration**：验证 GLM/OpenAI-compatible provider tool-call shape 可以被 agent 解析并进入 runtime；本轮使用 ignored `.env` 中的本地 key 运行真实 provider 测试。
10. **Pilot E2E**：验证 Code/CI reference pilot 和 staging internal admin pilot 的实际可跑路径。

测试策略不是只看“命令是否返回 0”，还要解释输出语义。例如 remote backend conformance 返回 `passed=false`，但原因是 `remote.contract_beta_only`，这符合当前 support matrix。

## 需求到测试追踪矩阵

| ID | 要求 | 测试用例 | 证据 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-001 | core runtime、policy、audit、sandbox、adapter、platform 不能回归 | TC-001 全量回归测试 | `pytest.txt` | verified |
| REQ-002 | stable candidate subject 必须有 certification evidence | TC-002 Certification | `certify.json` | verified |
| REQ-003 | adapter 只翻译调用，不授予 capability | TC-003 Adapter conformance，TC-004 Adapter replay | `adapter-conformance.json`，`adapter-replay-code-ci.json` | verified |
| REQ-004 | sandbox backend support level 和限制必须清晰 | TC-005 Sandbox conformance，TC-006 Docker smoke evidence | `sandbox-conformance-*.json`，`sandbox-evidence-container-smoke.json` | verified |
| REQ-005 | platform unavailable、policy stale、audit forwarding failed 等场景可模拟 | TC-007 Platform simulation | `platform-simulation.json` | verified |
| REQ-006 | Code/CI pilot 只能执行 allowlisted command，拒绝 commit/push/PR | TC-008 Code/CI success，TC-009 Code/CI deny | `code-ci-*.json` | verified |
| REQ-007 | staging internal admin pilot 能产生 audit、observer、pilot report | TC-010 Staging admin pilot | `staging-admin-pilot-output.json` | verified |
| REQ-008 | audit hash chain 可验证 | TC-011 Audit verify | `staging-admin-audit-verify.json` | verified |
| REQ-009 | observer 能解释 approval、deny、timeout 等运行状态 | TC-012 Observer status | `staging-admin-observer-status.json` | verified |
| REQ-010 | 用户指南中的场景必须有可运行 acceptance 覆盖 | TC-013 Scenario-based acceptance | `SCENARIO_TEST_REPORT.md`，`tests/test_scenario_based_user_guide.py`，`scenario-based-user-guide.txt` | verified |
| REQ-011 | 至少有自写 real agent loop 测试，不只测试 runtime contract | TC-014 Real-agent loop | `REAL_AGENT_TEST_REPORT.md`，`tests/test_real_agent_scenarios.py` | verified |
| REQ-012 | 至少提供一个真实 provider agent 的可执行接入路径，且不提交 API key | TC-015 GLM/OpenAI-compatible provider agent | `REAL_AGENT_TEST_REPORT.md`，`tests/test_provider_real_agent.py` | verified |

## 测试用例详情

### TC-001 全量回归测试

**用例设计**

全量运行 pytest，覆盖现有单元测试、集成测试、contract test、sandbox abuse test、platform release test 和 pilot test。该用例用于发现核心行为、公开 CLI、manifest、support matrix、audit、policy、sandbox、adapter、pilot 的回归。

**命令**

```bash
python -m pytest -q > .agent-runtime/test-report-2026-06-17/pytest.txt
```

**输出结果**

```text
........................................................................ [ 45%]
........................................................................ [ 90%]
................                                                         [100%]
160 passed in 31.67s
```

**输出解释**

`160 passed` 表示当前测试套件全部通过，且真实 GLM provider integration 与 agent registration 对比测试都已使用 ignored `.env` 中的本地 API key 执行。覆盖范围包括 adapter、audit、policy、sandbox、platform、release manifest、Code/CI pilot、staging pilot、SQLite audit、tracing、11 个基于用户指南场景的 acceptance tests、4 个自写 real-agent loop tests，以及 9 个 provider-agent tests。

**结论**

通过。

### TC-002 Platform-Ready Certification

**用例设计**

运行 certification CLI，验证 platform-ready runtime 中所有 stable candidate subject 都有 contract、support level、evidence refs 和 passed 状态。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all > .agent-runtime/test-report-2026-06-17/certify.json
```

**输出结果**

```json
{
  "passed": true,
  "release": "platform_ready_runtime",
  "schema_version": 1,
  "certifications": [
    "openai_adapter",
    "anthropic_adapter",
    "langgraph_adapter",
    "mcp_adapter",
    "codex_workspace_adapter",
    "container_backend",
    "control_plane_api"
  ]
}
```

**输出解释**

报告中 7 个 stable candidate subject 均 `passed=true`。`sidecar_backend` 不在 certification 列表中，因为它当前是 preview；`remote_executor` 不在 certification 列表中，因为它当前是 contract beta。

**结论**

通过。

### TC-003 Adapter Conformance

**用例设计**

运行所有 adapter 的 conformance dry run，验证 adapter metadata、translate-only、adapter source 和 no capability grant 这些核心约束。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter all --dry-run > .agent-runtime/test-report-2026-06-17/adapter-conformance.json
```

**输出结果**

```json
{
  "dry_run": true,
  "report": {
    "passed": true,
    "failure_reasons": [],
    "adapters": {
      "openai": {"support_level": "stable_candidate"},
      "anthropic": {"support_level": "stable_candidate"},
      "langgraph": {"support_level": "stable_candidate"},
      "mcp": {"support_level": "stable_candidate"},
      "codex": {"support_level": "stable_candidate"}
    }
  }
}
```

每个 adapter 的 checks 均包含：

```text
metadata_valid
translate_only
adapter_source
no_capability_grant
```

**输出解释**

`passed=true` 且 `failure_reasons=[]` 表示 adapter contract 检查通过。`no_capability_grant` 是关键项，说明 adapter 没有给 tool call 额外授予 capability。

**结论**

通过。

### TC-004 Code/CI Adapter Replay

**用例设计**

用 Code/CI 场景回放 OpenAI、LangGraph、Codex adapter，验证 provider-specific tool call shape 转换后仍保持 runtime semantics。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex > .agent-runtime/test-report-2026-06-17/adapter-replay-code-ci.json
```

**输出结果**

```json
{
  "passed": true,
  "scenario": "code-ci",
  "paths": [
    {
      "adapter": "openai",
      "capabilities_granted": [],
      "runtime_semantics": "policy_audit_sandbox_preserved"
    },
    {
      "adapter": "langgraph",
      "capabilities_granted": [],
      "runtime_semantics": "policy_audit_sandbox_preserved"
    },
    {
      "adapter": "codex",
      "capabilities_granted": [],
      "runtime_semantics": "policy_audit_sandbox_preserved"
    }
  ]
}
```

**输出解释**

三条 replay path 都没有授予 capability，且 runtime semantics 均保持 `policy_audit_sandbox_preserved`。这说明 adapter replay 没有绕过 runtime 的 policy、audit、sandbox 语义。

**结论**

通过。

### TC-005 Sandbox Conformance

**用例设计**

分别验证 container、sidecar、remote 三类 backend 的 support level、checks、limitations 和 expected pass/fail 行为。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run > .agent-runtime/test-report-2026-06-17/sandbox-conformance-container.json
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend sidecar --dry-run > .agent-runtime/test-report-2026-06-17/sandbox-conformance-sidecar.json
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run > .agent-runtime/test-report-2026-06-17/sandbox-conformance-remote.json
```

**输出结果**

container：

```json
{
  "passed": true,
  "support_level": "stable_candidate",
  "checks": [
    "metadata_valid",
    "abuse.path_traversal",
    "abuse.credential_path",
    "abuse.network_attempt",
    "abuse.output_flood"
  ],
  "limitations": [
    "container_trusted_base_required",
    "no_absolute_escape_prevention"
  ]
}
```

sidecar：

```json
{
  "passed": true,
  "support_level": "preview",
  "checks": [
    "metadata_valid",
    "sidecar.request_response"
  ],
  "limitations": [
    "minimal_sidecar_contract_only",
    "no_production_scheduler"
  ]
}
```

remote：

```json
{
  "passed": false,
  "support_level": "contract_beta",
  "failure_reasons": [
    "remote.contract_beta_only"
  ],
  "limitations": [
    "contract_beta_only",
    "no_production_execution"
  ]
}
```

**输出解释**

container 通过 stable candidate conformance。sidecar 通过 preview contract。remote 返回 `passed=false` 是预期结果，因为 remote executor 当前只允许作为 contract beta，不应被误认为 production-ready backend。

**结论**

通过。remote 的 `passed=false` 是预期边界验证。

### TC-006 Container Sandbox Runtime Evidence

**用例设计**

运行 Docker smoke evidence，验证当前机器可以执行 container smoke，并记录 runtime 限制。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest > .agent-runtime/test-report-2026-06-17/sandbox-evidence-container-smoke.json
```

**输出结果**

```json
{
  "backend": "docker",
  "client_version": "Docker version 28.0.1, build 068a01e",
  "daemon_available": true,
  "runtime_present": true,
  "server_version": "28.0.1",
  "smoke_ran": true,
  "smoke_passed": true,
  "smoke_output": "agent-runtime-smoke",
  "limitations": [
    "container_trusted_base_required",
    "no_absolute_escape_prevention",
    "smoke_does_not_prove_escape_resistance"
  ]
}
```

**输出解释**

Docker client 和 daemon 可用，smoke 已运行且通过。输出中的 limitations 明确说明该证据只证明 smoke 能运行，不证明绝对逃逸防护。

**结论**

通过。

### TC-007 Platform Simulation

**用例设计**

运行 platform simulation，验证 cloud/control-plane 相关失败模式在 contract 层可被表达。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main platform simulate --scenario all > .agent-runtime/test-report-2026-06-17/platform-simulation.json
```

**输出结果**

```json
{
  "passed": true,
  "requested_scenario": "all",
  "scenarios": [
    "platform_unavailable",
    "policy_stale",
    "audit_forwarding_failed",
    "registry_mismatch",
    "disabled_remotely"
  ]
}
```

**输出解释**

simulation 覆盖 platform unavailable、policy stale、audit forwarding failed 等关键 failure mode。它证明 contract 可以表达这些情况，但不等同于已经有 hosted control plane。

**结论**

通过。

### TC-008 Code/CI Pilot Allowlisted Command

**用例设计**

使用当前仓库作为 staging repo，只允许执行一条测试命令，验证 Code/CI reference pilot 的 allowlist 和 report 行为。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main pilot code-ci \
  --repo . \
  --command "python -m pytest tests/test_code_ci_pilot.py" \
  --allow-command "python -m pytest tests/test_code_ci_pilot.py" \
  --write-scope .agent-runtime/test-report-2026-06-17 \
  --report .agent-runtime/test-report-2026-06-17/code-ci-success-report.json
```

**输出结果**

```json
{
  "status": "success",
  "dirty_workspace_status": "clean",
  "network_access": false,
  "commit_push_pr_denied": true,
  "credential_paths_denied": true,
  "audit_mode": "digest-only",
  "audit_verify_status": "not_run",
  "executed_commands": [
    ["python", "-m", "pytest", "tests/test_code_ci_pilot.py"]
  ],
  "diff_summary": "3 passed in 0.12s"
}
```

**输出解释**

allowlisted command 成功执行，repo 状态 clean，commit/push/PR 仍被声明为 denied。`audit_mode=digest-only` 表示该 pilot 当前不是完整 runtime audit chain。

**结论**

通过，但 audit 边界需要在 design partner 场景中明确。

### TC-009 Code/CI Pilot Denied Command

**用例设计**

执行 `git commit`，验证 Code/CI pilot 能拒绝 commit 类命令，且不会执行 denied command。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main pilot code-ci \
  --repo . \
  --command "git commit" \
  --write-scope .agent-runtime/test-report-2026-06-17 \
  --report .agent-runtime/test-report-2026-06-17/code-ci-deny-report.json
```

**输出结果**

```json
{
  "status": "denied",
  "error": "command.denied",
  "executed_commands": [],
  "commit_push_pr_denied": true,
  "dirty_workspace_status": "clean"
}
```

**输出解释**

`executed_commands=[]` 说明被拒绝的命令没有执行。`command.denied` 是预期错误。

**结论**

通过。

### TC-010 Staging Internal Admin Pilot

**用例设计**

运行 staging internal admin pilot，覆盖 read allow、write approval、approval timeout、unknown prod tool deny、command env allowlist、observer 和 SQLite audit 生成。

**命令**

```bash
PYTHONPATH=src python examples/staging_internal_admin_pilot.py > .agent-runtime/test-report-2026-06-17/staging-admin-pilot-output.json
```

**输出结果**

```json
{
  "audit_path": ".agent-runtime/staging-pilot/pilot-audit.db",
  "observer_path": ".agent-runtime/staging-pilot/observer.json",
  "report_path": ".agent-runtime/staging-pilot/pilot-report.json"
}
```

**输出解释**

pilot 生成 SQLite audit、observer status 和 pilot report。该用例提供一个比单纯 unit test 更接近 staging workflow 的证据。

**结论**

通过。

### TC-011 Audit Query And Verify

**用例设计**

对 staging pilot 产生的 SQLite audit 执行 query 和 verify。query 用于检查具体事件，verify 用于验证 hash chain。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/staging-pilot/pilot-audit.db --tool-name read_customer > .agent-runtime/test-report-2026-06-17/staging-admin-audit-query-read-customer.json
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite > .agent-runtime/test-report-2026-06-17/staging-admin-audit-verify.json
```

**输出结果**

query 输出为逐行 JSON 事件流，前几类事件包括：

```text
ToolCallRequested
PolicyEvaluated
TraceSpanStarted
ToolExecutionStarted
ToolExecutionFinished
```

verify 输出：

```json
{
  "checked_events": 27,
  "error": null,
  "index": null,
  "valid": true
}
```

**输出解释**

query 证明 read_customer 的 tool call 进入 audit，并记录 policy decision、trace span 和 execution lifecycle。verify 证明 27 条事件的 hash chain 有效。

**结论**

通过。

### TC-012 Observer Status

**用例设计**

读取 staging pilot 的 observer status，验证运行指标能反映 approval、deny、timeout 和 audit failure。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main observe status --path .agent-runtime/staging-pilot/observer.json > .agent-runtime/test-report-2026-06-17/staging-admin-observer-status.json
```

**输出结果**

```json
{
  "tool_calls": 5,
  "approval_requests": 2,
  "approval_rejected": 1,
  "denied": 1,
  "timeouts": 1,
  "failures": 2,
  "failure_rate": 0.4,
  "reject_rate": 0.2,
  "timeout_rate": 0.2,
  "audit_write_failures": 0,
  "audit_fail_closed": 0
}
```

**输出解释**

observer 反映 staging pilot 中出现了 5 次 tool call、2 次 approval request、1 次 approval rejection、1 次 deny 和 1 次 timeout。`audit_write_failures=0` 说明本轮没有 audit 写入失败。

**结论**

通过。

### TC-013 Scenario-Based Acceptance

场景测试单独维护在 [SCENARIO_TEST_REPORT.md](SCENARIO_TEST_REPORT.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-010 中保留追踪关系。

### TC-014 Real-Agent Loop

Real-agent loop 测试单独维护在 [REAL_AGENT_TEST_REPORT.md](REAL_AGENT_TEST_REPORT.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-011 中保留追踪关系。

### TC-015 GLM/OpenAI-Compatible Provider Agent

GLM/OpenAI-compatible provider agent 测试单独维护在 [REAL_AGENT_TEST_REPORT.md](REAL_AGENT_TEST_REPORT.md)，agent registration 对比测试详见 [PROVIDER_RUNTIME_COMPARISON_REPORT.md](PROVIDER_RUNTIME_COMPARISON_REPORT.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-012 中保留追踪关系。

回归中，fake transport 覆盖真实 provider 的 `tool_calls` response shape，验证 agent 会解析 tool name 和 arguments 后交给 runtime。真实 GLM/Z.AI 外部调用由 `tests/test_provider_real_agent.py::test_glm_provider_agent_can_call_real_provider_when_key_is_configured` 覆盖；未注册 agent vs 注册 agent 对比由 `test_same_agent_registration_comparison_with_fake_provider` 和 `test_same_agent_unregistered_vs_registered_runtime_execution` 覆盖。

## 回归范围说明

本轮回归覆盖：

- adapter conformance 与 replay。
- approval provider 与 approval timeout。
- audit write failure policy。
- audit tamper evidence 与 verify。
- capability policy。
- CLI init、validate、doctor、query、conformance、certify、pilot、sandbox、platform。
- Code/CI reference pilot。
- contrib pack registry 和 dependency boundary。
- control plane prelude。
- observer metrics。
- platform integration 和 platform-ready manifest。
- policy/audit hardening。
- production pilot report。
- sandbox abuse、conformance、hardening、runtime evidence、sidecar、support matrix。
- scenario-based user guide acceptance。
- provider-agent tool-call parsing、GLM optional integration、agent registration comparison 和 secret boundary。
- SQLite audit。
- tracing。

## 未测试范围与原因

| 范围 | 状态 | 原因 |
| --- | --- | --- |
| 真实 OpenAI / Anthropic / LangGraph / MCP / Codex provider payload 全量 replay | 部分覆盖 | 当前新增 GLM/OpenAI-compatible provider agent optional integration，但尚未收集多 provider 匿名 payload fixture |
| 真实 GLM/Z.AI provider 外部调用 | 已测试 | 本轮使用 ignored `.env` 中的本地 key 运行；secret 不进入可提交文件或公开报告 |
| hosted control plane | 未测试 | 当前项目不自带 hosted control plane |
| enterprise console / RBAC UI | 未测试 | 当前明确 unsupported |
| remote executor production execution | 未测试 | 当前 remote executor 是 contract beta |
| 多租户 hosted execution pool | 未测试 | 当前不提供 hosted execution pool |
| sandbox 绝对逃逸防护 | 未测试 | Docker smoke evidence 不证明绝对 escape prevention |
| 外部 design partner 真实反馈 | 未测试 | 当前是本地/staging 证据，不是外部用户反馈 |

## 风险与建议

### P1：Code/CI pilot audit 模式需要明确

Code/CI reference pilot 当前 `audit_mode=digest-only`，不能替代 runtime SQLite/JSONL audit chain。进入真实 design partner 前，应二选一：

- 将 Code/CI pilot 接入 runtime audit sink。
- 在用户文档和 pilot plan 中明确 digest-only report 的边界。

### P1：真实 provider payload replay 仍需扩展

adapter conformance 证明 adapter contract；新增的 GLM/OpenAI-compatible provider agent 证明至少一个真实 provider tool-call 接入路径已经存在。但它仍不能证明 OpenAI、Anthropic、LangGraph、MCP、Codex 等真实 provider SDK payload 全量兼容。下一步应收集匿名真实 payload fixture，并纳入 adapter replay。

### P2：platform simulation 不是 hosted control plane 验证

`platform simulate --scenario all` 证明 failure semantics 可表达，但不证明 cloud service 的可用性、认证、租户隔离或运维能力。

### P2：sandbox evidence 需要宿主安全基线配合

container smoke passed 只证明本机 Docker smoke 可运行。生产隔离仍需宿主侧容器基线、网络策略、secret 管理、镜像可信链和外部审计归档。

## 总结

本轮测试证明 Agent Runtime 当前适合继续推进 Technical Preview 和 Design Partner Pilot 准备。核心 runtime、adapter、sandbox、platform contract 和 pilot 示例都有可复现证据。

当前最适合继续推进的真实场景仍是：

1. Code/CI agent governance。
2. Local agent + cloud runtime control plane。
3. MCP tool governance。
4. Ops diagnostic read-only agent。

进入真实 design partner 前，最需要补齐的是 Code/CI runtime audit chain，以及更多 provider/framework 的真实 payload replay。GLM/Z.AI optional integration 已经提供第一条真实 provider 接入路径，但仍需要用轮换后的本地 key 跑一次真实外部调用并记录不含 secret 的摘要证据。
