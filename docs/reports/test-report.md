# Agent Runtime 测试报告

报告日期：2026-06-21
报告状态：公开测试报告  
产品状态：Technical Preview  
下一门禁：Design Partner Pilot

## 结论摘要

本轮测试结论：当前仓库在 core regression、E2E smoke、complete runtime report、scenario-based acceptance、real-agent loop、governed agent tracing、真实 provider agent optional integration、platform-ready certification、adapter contract、sandbox contract、platform simulation、Code/CI reference pilot、staging internal admin pilot、audit verify 和 observer status 这些关键路径上均有新鲜证据。

本轮没有发现阻塞 Technical Preview 或 design partner pilot 准备的回归。

需要明确的边界：

- Code/CI reference pilot 当前是 `digest-only` report，不是完整 runtime audit chain。
- `remote_executor` 当前是 `contract_beta`，相关 conformance 返回 `passed=false` 是预期边界，不是回归。
- Docker smoke evidence 不证明绝对 sandbox escape prevention。
- sandbox plan violation 属于 pre-execution denial；runtime 应返回 `status=denied` 和明确的 `sandbox.*` error，而不是把它包装成成功执行的 command result。
- 当前没有验证真实 provider SDK 全量 payload，也没有验证 hosted control plane；GLM/Z.AI provider integration 已提供 optional test，本轮使用 ignored `.env` 中的本地 key 执行了真实外部调用。

## 测试环境

| 项目 | 值 |
| --- | --- |
| 工作目录 | Agent Runtime 仓库根目录 |
| 日期 | 2026-06-21 |
| Python | 3.12.9 |
| pytest | 9.0.2 |
| Docker client | `Docker version 28.0.1, build 068a01e` |
| Docker server | `28.0.1` |
| 证据目录 | `.agent-runtime/test-report-2026-06-21/` |

说明：证据目录属于本地运行产物，不提交。测试报告只提交摘要、解释和可复现命令。

## 测试设计

测试设计分为十五层：

1. **Regression**：使用全量 `pytest` 覆盖 core、policy、audit、adapter、sandbox、platform、pilot 等现有测试。
2. **Scenario-Based Acceptance**：把 `docs/user-guide.md` 的 11 个场景映射成用户视角测试。
3. **Certification**：使用 `certify run` 验证 stable candidate subject 是否仍具备 evidence。
4. **Adapter Contract**：验证 adapter 是否保持 translate-only、不授予 capability、不绕过 runtime semantics。
5. **Sandbox Contract**：验证 container、sidecar、remote 三类 backend 的 support level 和边界。
6. **Runtime Evidence**：验证 Docker runtime smoke evidence 是否能生成，并解释其限制；同时明确 contrib container backend 是 plan simulation，不执行真实 Docker container。
7. **Platform Contract**：验证 platform failure simulation 覆盖 control plane 相关失败模式。
8. **Real-Agent Loop**：验证自写 agent loop 会产生 tool call、读取结果后继续、停止或进入 blocked 状态，并覆盖复杂 production incident loop。
9. **Provider-Agent Optional Integration**：验证 GLM/OpenAI-compatible provider tool-call shape 可以被 agent 解析并进入 runtime；本轮使用 ignored `.env` 中的本地 key 运行真实 provider 测试。
10. **Governed Agent Tracing**：验证 trace 同时回答 agent 做了什么、为什么允许/拒绝、是否强隔离、是否可审计。
11. **Complete Report / Run Screenshot Artifacts**：验证多个 agent 的完整体验报告，以及单个真实 provider agent run 的运行截图 artifact。
12. **Run Process Viewer**：验证单次 run 可以从 audit/snapshot 生成完整运行过程 HTML，展示 input、agent decision、runtime governance、timeline、tool calls、trace tree 和 raw evidence。
13. **Direct vs Registered Agent Comparison**：验证同一个 agent 可以被用户以未注册 direct execution 和 registered runtime execution 两种方式运行，并能看到治理差异。
14. **Pilot E2E**：验证 Code/CI reference pilot 和 staging internal admin pilot 的实际可跑路径。
15. **E2E Smoke**：验证 clean wheel install、production incident run view、Docker sandbox runtime、complete report fake provider、Docker sandbox failure paths 和 run view browser evidence 六条端到端路径。

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
| REQ-010 | 用户指南中的场景必须有可运行 acceptance 覆盖 | TC-013 Scenario-based acceptance | `docs/reports/scenario-test-report.md`，`tests/test_scenario_based_user_guide.py`，`scenario-based-user-guide.txt` | verified |
| REQ-011 | 至少有自写 real agent loop 测试，不只测试 runtime contract | TC-014 Real-agent loop | `docs/reports/real-agent-test-report.md`，`tests/test_real_agent_scenarios.py` | verified |
| REQ-012 | 至少提供一个真实 provider agent 的可执行接入路径，且不提交 API key | TC-015 GLM/OpenAI-compatible provider agent | `docs/reports/real-agent-test-report.md`，`tests/test_provider_real_agent.py` | verified |
| REQ-013 | registered agent 在 runtime 中执行时必须能追踪 agent run span、tool call span、policy 决策、approval gate、sandbox 强隔离、audit commit 和失败路径 | TC-016 Governed agent tracing | `tests/test_tracing.py`，`docs/reference/agent-registry-contract.md` | verified |
| REQ-014 | 必须有一份完整运行体验报告，展示多个 agent 进入 runtime 后的 output、治理证据、trace 和 audit | TC-017 Complete runtime report | `docs/reports/complete-report.md`，`examples/complete_runtime_report.py`，`tests/test_complete_runtime_report.py` | verified |
| REQ-015 | 必须能生成单次 agent 在 Agent Runtime 中运行时产生的截图，展示 prompt、provider、tool call/result、policy、audit 和 trace | TC-018 Agent run screenshot | `examples/agent_run_screenshot.py`，`tests/test_agent_run_screenshot.py` | verified |
| REQ-016 | 必须能把单次 agent run 的完整运行过程可视化，展示 input、agent decision、runtime governance、timeline、tool calls、trace tree 和 raw evidence | TC-019 Run process viewer | `src/agent_runtime/run_view.py`，`tests/test_run_viewer.py`，`tests/test_cli_developer_preview.py` | verified |
| REQ-017 | 必须有复杂生产级 agent 测试对象，能在同一 run 中触发 allow、approval、sandbox、explicit deny、audit 和 trace | TC-020 Production incident agent | `src/agent_runtime/testing/production_agents.py`，`tests/test_production_incident_agent.py` | verified |
| REQ-018 | 用户必须能亲自运行同一个 agent 的未注册 direct execution 和 registered runtime execution 对比 | TC-021 Production incident registration comparison | `examples/production_incident_comparison.py`，`tests/test_production_incident_comparison_example.py` | verified |

## 测试用例详情

### TC-001 全量回归测试

**用例设计**

全量运行 pytest，覆盖现有单元测试、集成测试、contract test、sandbox abuse test、platform release test 和 pilot test。该用例用于发现核心行为、公开 CLI、manifest、support matrix、audit、policy、sandbox、adapter、pilot 的回归。

**命令**

```bash
python -m pytest -q
```

**输出结果**

```text
224 passed in 38.97s
```

**输出解释**

`224 passed` 表示当前测试套件全部通过，且真实 GLM provider integration、formal agent registry contract、registered agent deny-path、registered agent capability/profile enforcement、governed agent tracing、complete runtime report、agent run screenshot、run process viewer、complete-report scenario context、JSON beauty view、production incident agent、production incident registration comparison、provider retry/backoff、LangGraph optional framework agent、approval 默认拒绝、agent lifecycle audit fail-closed、execution-error audit fail-closed、policy deny precedence、sandbox pre-execution denial、sandbox env 预过滤、runtime pre-backend secret-like env deny、sidecar sanitized sandbox plan、Docker env argv 防泄漏、JSONL / SQLite audit 本地并发写 hash chain、显式 opt-in Docker sandbox backend preview、Docker backend CLI conformance、adapter payload fixtures、Docker stable candidate gate 和 E2E smoke 都已验证。覆盖范围包括 adapter、audit、policy、sandbox、platform、release manifest、Code/CI pilot、staging pilot、SQLite audit、tracing、11 个基于用户指南场景的 acceptance tests、复杂 production incident agent、未注册 direct execution 与 registered runtime execution 对比、complete runtime report、single-run screenshot、带业务上下文的完整运行过程 HTML、HTML escaping regression、clean wheel install、Docker sandbox runtime/failure paths E2E、run view browser evidence、runtime governance matrix E2E，以及 provider/framework-agent tests。

**结论**

通过。

### TC-002 Platform-Ready Certification

**用例设计**

运行 certification CLI，验证 platform-ready runtime 中所有 stable candidate subject 都有 contract、support level、evidence refs 和 passed 状态。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all > .agent-runtime/test-report-2026-06-21/certify.json
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
PYTHONPATH=src python -m agent_runtime.cli.main adapter conformance --adapter all --dry-run > .agent-runtime/test-report-2026-06-21/adapter-conformance.json
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
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex > .agent-runtime/test-report-2026-06-21/adapter-replay-code-ci.json
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

分别验证 container、Docker、sidecar、remote 四类 backend 的 support level、checks、limitations 和 expected pass/fail 行为。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run > .agent-runtime/test-report-2026-06-21/sandbox-conformance-container.json
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend docker --dry-run > .agent-runtime/test-report-2026-06-21/sandbox-conformance-docker.json
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend sidecar --dry-run > .agent-runtime/test-report-2026-06-21/sandbox-conformance-sidecar.json
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run > .agent-runtime/test-report-2026-06-21/sandbox-conformance-remote.json
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
    "container_plan_only_no_real_docker_execution",
    "container_trusted_base_required",
    "no_absolute_escape_prevention"
  ]
}
```

Docker：

```json
{
  "passed": true,
  "support_level": "preview",
  "checks": [
    "metadata_valid",
    "docker.real_execution_contract",
    "abuse.network_attempt"
  ],
  "limitations": [
    "docker_real_execution_requires_local_daemon",
    "container_trusted_base_required",
    "no_absolute_escape_prevention",
    "host_docker_security_baseline_required"
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

container plan backend 通过 stable candidate conformance。Docker sandbox backend 通过 preview real execution contract conformance，但仍依赖本地 Docker daemon 和宿主安全基线。sidecar 通过 preview contract。remote 返回 `passed=false` 是预期结果，因为 remote executor 当前只允许作为 contract beta，不应被误认为 production-ready backend。

**结论**

通过。remote 的 `passed=false` 是预期边界验证。

### TC-006 Container Sandbox Runtime Evidence

**用例设计**

运行 Docker smoke evidence，验证当前机器可以执行 container smoke，并记录 runtime 限制。

**命令**

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest > .agent-runtime/test-report-2026-06-21/sandbox-evidence-container-smoke.json
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
PYTHONPATH=src python -m agent_runtime.cli.main platform simulate --scenario all > .agent-runtime/test-report-2026-06-21/platform-simulation.json
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
  --write-scope .agent-runtime/test-report-2026-06-21 \
  --report .agent-runtime/test-report-2026-06-21/code-ci-success-report.json
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
  --write-scope .agent-runtime/test-report-2026-06-21 \
  --report .agent-runtime/test-report-2026-06-21/code-ci-deny-report.json
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
PYTHONPATH=src python examples/staging_internal_admin_pilot.py > .agent-runtime/test-report-2026-06-21/staging-admin-pilot-output.json
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
PYTHONPATH=src python -m agent_runtime.cli.main audit query --path .agent-runtime/staging-pilot/pilot-audit.db --tool-name read_customer > .agent-runtime/test-report-2026-06-21/staging-admin-audit-query-read-customer.json
PYTHONPATH=src python -m agent_runtime.cli.main audit verify --path .agent-runtime/staging-pilot/pilot-audit.db --sink sqlite > .agent-runtime/test-report-2026-06-21/staging-admin-audit-verify.json
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
PYTHONPATH=src python -m agent_runtime.cli.main observe status --path .agent-runtime/staging-pilot/observer.json > .agent-runtime/test-report-2026-06-21/staging-admin-observer-status.json
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

场景测试单独维护在 [docs/reports/scenario-test-report.md](/docs/reports/scenario-test-report.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-010 中保留追踪关系。

### TC-013B E2E Smoke

E2E smoke 测试单独维护在 [docs/reports/e2e-test-report.md](/docs/reports/e2e-test-report.md)，测试计划维护在 [docs/test/e2e-test-plan.md](/docs/test/e2e-test-plan.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在测试设计第 15 层中保留追踪关系。

### TC-014 Real-Agent Loop

Real-agent loop 测试单独维护在 [docs/reports/real-agent-test-report.md](/docs/reports/real-agent-test-report.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-011 和 REQ-017 中保留追踪关系。

### TC-015 GLM/OpenAI-Compatible Provider Agent

GLM/OpenAI-compatible provider agent 测试单独维护在 [docs/reports/real-agent-test-report.md](/docs/reports/real-agent-test-report.md)，agent registration 对比测试详见 [docs/reports/provider-runtime-comparison-report.md](/docs/reports/provider-runtime-comparison-report.md)。综合测试报告只记录它作为回归套件的一部分被纳入 `python -m pytest`，并在 REQ-012 中保留追踪关系。

回归中，fake transport 覆盖真实 provider 的 `tool_calls` response shape，验证 agent 会解析 tool name 和 arguments 后交给 runtime。真实 GLM/Z.AI 外部调用由 `tests/test_provider_real_agent.py::test_glm_provider_agent_can_call_real_provider_when_key_is_configured` 覆盖；未注册 agent vs 注册 agent 对比由 `test_same_agent_registration_comparison_with_fake_provider` 和 `test_same_agent_unregistered_vs_registered_runtime_execution` 覆盖；formal agent registry contract 和 deny-path 由 `tests/test_agent_registry_contract.py` 覆盖；LangGraph optional framework agent 由 `tests/test_langgraph_agent_registration.py` 覆盖。

### TC-016 Governed Agent Tracing

governed agent tracing 由 `tests/test_tracing.py` 覆盖。它验证 runtime 中执行的 registered agent 会产生 `agent_run` span，tool call 会继承同一个 `trace_id`，并用 `parent_span_id` 指向 agent span。

治理路径也纳入测试：policy evaluation span 记录 allow/deny 的 `decision`、`reason`、`rule_id` 和 `policy_version`；approval gate span 记录 `approved`、`reason`、`timed_out`、`rule_id` 和 `risk_level`；policy deny 时 tool span 仍然关闭并记录拒绝原因；sandbox execution span 记录 `isolation_level=strong`、backend 和可用状态；tool span finish 记录 `audit_status=committed`。失败路径中，agent 抛异常时 runtime 仍写入 `AgentRunFinished(status=failed)` 和 `TraceSpanFinished(span_kind=agent_run, status=failed)`，然后把原异常继续抛给调用方。

### TC-017 Complete Runtime Report

complete runtime report 由 `tests/test_complete_runtime_report.py` 覆盖。测试以 explicit fake provider mode 运行 `examples/complete_runtime_report.py`，用于保证 CI 稳定；用户直接运行 runner 时默认使用 ignored `.env` 中的真实 GLM/Z.AI key。该测试验证 6 个 deterministic agent scenario 都能生成完整 output：

- scripted echo agent。
- provider-style tool calling agent。
- policy deny agent。
- approval gate agent。
- sandboxed command agent。
- production incident agent。

测试断言 `complete-report.json`、`complete-report.md`、`complete-report.html` 和 `complete-report.png` 都会生成，并且每个 scenario 都包含 transcript、tool results、policy/approval/sandbox/audit governance summary、governed trace 和 audit event sequence。

### TC-018 Agent Run Screenshot

agent run screenshot 由 `tests/test_agent_run_screenshot.py` 覆盖。测试以 explicit fake provider mode 运行 `examples/agent_run_screenshot.py` 的 builder，验证单次 registered provider agent run 能生成：

- `real-provider-agent-run.json`
- `real-provider-agent-run.html`
- `real-provider-agent-run-view.html`
- `real-provider-agent-run.png`

用户直接运行 `PYTHONPATH=src python examples/agent_run_screenshot.py` 时默认使用 ignored `.env` 中的真实 GLM/Z.AI key。该 artifact 不是汇总报告，而是一条 agent run 的截图：prompt、provider、decisions、tool call、tool result、policy、audit、trace 都在同一张图里。`real-provider-agent-run-view.html` 是同一条 run 的完整过程 UI，按 input、agent decision、runtime governance、execution timeline、tool calls、trace tree 和 raw evidence 展示。

### TC-019 Run Process Viewer

run process viewer 由 `tests/test_run_viewer.py` 和 `tests/test_cli_developer_preview.py::test_cli_run_view_writes_complete_process_html` 覆盖。测试验证：

- `build_run_view_from_audit` 能从 audit JSONL 和 snapshot 还原 agent、provider、status、prompt、tool arguments、policy allow、audit committed、tool result、timeline、trace tree 和 raw events。
- `load_scenario_snapshot` 能从 complete report 中按 scenario id 合并 prompt、purpose、phases、findings 和 remediation。
- `render_run_view_html` 会生成包含 Agent Run Report、Run Overview、Agent Decision、Runtime Governance、Execution Timeline、Tool Calls、Trace Tree 和 Raw Evidence 的完整 HTML。
- JSON 字段使用 beauty view 渲染，包含缩进、HTML escaping 和 key/string/number/boolean/null token class。
- CLI `agent-runtime run view --audit ... --snapshot ... --output ...` 可以从单次 snapshot 重新生成完整运行过程 HTML。
- CLI `agent-runtime run view --audit ... --report ... --scenario ... --output ...` 可以从 complete report 重新生成带业务上下文的最终运行报告 HTML。

### TC-020 Production Incident Agent

production incident agent 由 `tests/test_production_incident_agent.py` 覆盖。它注册 `ProductionIncidentAgent` 后执行一个生产 checkout latency incident loop，并验证：

- agent phases 为 intake、investigate、diagnose、remediate、guardrail、summarize。
- 同一 run 中产生 6 次 runtime tool call。
- deployment、logs、feature flag 查询走 allow path。
- diagnostics command 走 strong sandbox，且无网络、无写挂载。
- rollback proposal 走 approval gate。
- 未授权 hotfix 被 explicit policy deny。
- audit 中记录 agent lifecycle、tool lifecycle 和 trace events，trace 中包含 agent_run、tool_call、policy_evaluation、approval_gate 和 sandbox_execution。

### TC-021 Production Incident Registration Comparison

production incident registration comparison 由 `examples/production_incident_comparison.py` 和 `tests/test_production_incident_comparison_example.py` 覆盖。它使用同一个 `ProductionIncidentAgent` 执行两次：

- 未注册 direct execution：agent 直接调用本地工具函数，不产生 audit events、trace id 或 runtime run id。
- registered runtime execution：agent 通过 `runtime.register_agent(...)` 注册后运行，tool call 进入 policy、approval、sandbox、audit 和 trace。
- direct 路径中的 `apply_hotfix` 返回 `applied`。
- registered 路径中的 `apply_hotfix` 被 `deny-hotfix` policy 拒绝。
- 运行会生成 `comparison.json`、`registered-audit.jsonl` 和 `registered-run-view.html`。

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
- complete runtime report。
- single agent run screenshot artifact。
- run process viewer。
- production incident agent。
- production incident registration comparison。
- provider-agent tool-call parsing、GLM optional integration、agent registry contract、registered deny-path、governed agent tracing、retry/backoff、LangGraph optional framework agent 和 secret boundary。
- registered agent declared capability、`max_tool_calls`、high/critical tool sandbox/approval profile enforcement。
- policy tool deny 覆盖 broad capability allow 的 precedence。
- complete report 和 single-run screenshot HTML dynamic value escaping。
- Docker backend 不在 argv 暴露 env value，且拒绝 secret-like allowlisted env key。
- runtime 在调用 sandbox backend 前拒绝 secret-like env，sidecar backend 只接收 sanitized sandbox execution plan。
- execution error path 遵守 audit fail-closed。
- approval provider approve/reject/timeout 和 concurrent runtime audit E2E。
- SQLite audit。
- tracing。

## 未测试范围与原因

| 范围 | 状态 | 原因 |
| --- | --- | --- |
| 真实 OpenAI / Anthropic / LangGraph / MCP / Codex provider payload 全量 replay | 部分覆盖 | 已有匿名 payload fixture baseline，但仍未覆盖各 provider SDK 全量变体 |
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

adapter conformance 证明 adapter contract；GLM/OpenAI-compatible provider agent 证明至少一个真实 provider tool-call 接入路径已经存在；OpenAI、Anthropic、LangGraph、MCP、Codex 已有匿名 payload fixture baseline。但它仍不能证明各 provider SDK payload 全量兼容，下一步应继续增加更多真实匿名 fixture，并纳入 adapter replay。

### P2：platform simulation 不是 hosted control plane 验证

`platform simulate --scenario all` 证明 failure semantics 可表达，但不证明 cloud service 的可用性、认证、租户隔离或运维能力。

### P2：sandbox evidence 需要宿主安全基线配合

container smoke passed 只证明本机 Docker smoke 可运行。当前 contrib `ContainerSandboxBackend` 是 container plan simulation；`DockerSandboxBackend` 是显式 opt-in 的真实 Docker execution preview。生产隔离仍需宿主侧容器基线、网络策略、secret 管理、镜像可信链和外部审计归档。

## 总结

本轮测试证明 Agent Runtime 当前适合继续推进 Technical Preview 和 Design Partner Pilot 准备。核心 runtime、adapter、sandbox、platform contract 和 pilot 示例都有可复现证据。

当前最适合继续推进的真实场景仍是：

1. Code/CI agent governance。
2. Local agent + cloud runtime control plane。
3. MCP tool governance。
4. Ops diagnostic read-only agent。

进入真实 design partner 前，最需要补齐的是真实外部 design partner 反馈、Code/CI runtime audit chain，以及更多 provider/framework 的真实 payload replay。GLM/Z.AI optional integration 已经提供第一条真实 provider 接入路径；默认 CI 仍不调用真实 provider key。
