# Agent Runtime E2E 扩展 Spec

日期：2026-06-21

状态：待评审

阶段：OPT Product Spec / PRD

适用范围：Technical Preview 到 Design Partner Pilot 的 E2E 覆盖扩展

关联文档：[E2E_TEST_PLAN.md](../../../E2E_TEST_PLAN.md)、[E2E_TEST_REPORT.md](../../../E2E_TEST_REPORT.md)、[TEST_REPORT.md](../../../TEST_REPORT.md)

## Problem Statement

Agent Runtime 已经有 core、policy、audit、sandbox、adapter、tracing、report 和场景测试，但当前 E2E 主要覆盖 clean wheel install、production incident run view、Docker sandbox happy path 和 fake provider complete report。对开源用户和 design partner 来说，这还不能充分证明：

- 真实 provider agent 注册到 runtime 后的完整执行体验。
- 未注册 direct execution 与 registered runtime execution 的治理差异。
- policy deny、approval、sandbox failure、retry/backoff 等关键失败路径不会旁路 runtime。
- OpenAI、Anthropic、LangGraph、MCP、Codex 等主流 agent 技术栈能以可插拔方式进入 runtime。
- run view / complete report 不只是生成文件，还能被浏览器打开并展示足够的运行过程证据。
- sidecar、remote executor、staging/design partner 场景的生产化边界清晰。

本 spec 的目标是把 E2E 覆盖从 smoke 级别扩展为分层、可执行、可报告、可审计的端到端验证体系。

## Target Users

- 开源用户：希望把本地或现有 agent 接入 Agent Runtime，并确认接入后不会降低隔离、审计和策略能力。
- Design partner 工程团队：需要用真实 staging 场景验证 provider、sandbox、approval、audit、trace 和 run view。
- Runtime 维护者：需要在改动 policy、audit、sandbox、adapter、report、provider transport 时得到端到端回归信号。
- 安全/合规评审者：需要看到允许、拒绝、隔离、审计、失败闭环和密钥边界证据。

## Goals

- 建立 P0/P1/P2 三层 E2E backlog，并让每条 E2E 有 requirement ID、测试入口、依赖、验收标准和报告位置。
- P0 覆盖真实 provider、direct vs registered、policy deny、Docker sandbox failure paths、run view/browser screenshot 这些最影响信任的链路。
- P1 覆盖主流 adapter/framework、approval provider、并发 audit/trace/hash chain。
- P2 预留 sidecar backend、remote executor、真实 staging/design partner、长任务和恢复测试。
- 所有真实 provider key 只通过 ignored `.env` 或 CI secret 注入，不写入可提交 artifact。
- E2E 报告必须解释输出意义，而不仅记录命令通过。

## Non-Goals

- 不在 P0 中实现 hosted control plane 或 hosted enterprise platform。
- 不把真实 provider key 放进默认 CI。
- 不把 sidecar backend 或 remote executor 标记为 stable candidate。
- 不承诺 Docker sandbox 具备绝对 escape prevention；E2E 只证明当前配置和 runtime enforcement 生效。
- 不要求所有 adapter 在 P0 都连接真实外部服务；P1 可以先用本地 framework object、fixture 或 fake transport 验证完整 runtime path。

## Scenarios

### SC-E2E-001 真实 Provider Agent 注册运行

用户在 `.env` 中配置真实 `GLM_API_KEY` 或 `ZAI_API_KEY`，运行一个 provider-style agent。agent 通过 provider 返回 tool call，runtime 根据 registered agent metadata、capabilities 和 policy 执行工具，最终生成 output、audit、trace 和 run view。

### SC-E2E-002 Direct vs Registered 对比

同一个 agent 先以未注册 direct execution 运行，再注册到 Agent Runtime 运行。报告必须展示 direct path 做了什么、registered path 为什么允许或拒绝、是否强隔离、是否可审计，以及 registered path 在 deny 时不能 fallback 到 direct execution。

### SC-E2E-003 Docker Sandbox 失败路径

注册 sandboxed command tool，分别触发 no-network、read-only filesystem、env allowlist、timeout 和 unsupported write path。测试必须能说明失败发生在 sandbox/runtime enforcement，而不是 agent 自己绕过。

### SC-E2E-004 Run View 浏览器验收

使用生成的 HTML run view 或 complete report，在本地浏览器中打开并截图。检查页面包含 agent 说明、prompt、provider request/response summary、policy decision、approval、sandbox、audit、trace tree、raw evidence 和 JSON beauty view。

### SC-E2E-005 Adapter / Framework Agent 接入

OpenAI、Anthropic、LangGraph、MCP、Codex adapter 至少各有一条可插拔 E2E：agent/framework 产生 tool call，adapter 只负责翻译，runtime 负责 policy、approval、sandbox、audit 和 trace。

### SC-E2E-006 Approval 和并发治理

一个 E2E 覆盖 approval provider 的 approve/reject/timeout；另一个 E2E 覆盖多个 agent 并发写 audit 和 trace，验证 hash chain、trace parent/child 和 observer summary。

### SC-E2E-007 Sidecar / Remote / Staging 生产边界

sidecar backend 使用本地 sidecar process；remote executor 使用本地测试服务或 mock server；staging/design partner 按 runbook 复跑并产出外部验收报告。P2 不要求默认 CI 全部运行，但必须有可复现命令和门禁说明。

## Requirements

| ID | Requirement | Priority | Source |
| --- | --- | --- | --- |
| REQ-E2E-X-001 | E2E backlog 必须按 P0/P1/P2 分层，并写入 `E2E_TEST_PLAN.md`。 | must | user |
| REQ-E2E-X-002 | 每条 E2E 必须有测试入口、依赖、CI/manual 状态、验收标准和报告位置。 | must | QA |
| REQ-E2E-X-003 | P0 必须包含真实 provider agent 的 registered runtime execution。 | must | user |
| REQ-E2E-X-004 | P0 必须包含同一 agent 的 direct execution vs registered runtime execution 对比。 | must | user |
| REQ-E2E-X-005 | registered agent 在 policy deny 时不得 fallback 到 direct execution。 | must | security |
| REQ-E2E-X-006 | P0 必须覆盖 Docker sandbox no-network、read-only filesystem、env allowlist、timeout 和 write path deny。 | must | security |
| REQ-E2E-X-007 | P0 必须提供 run view 或 complete report 的浏览器截图/HTML 验收。 | must | product |
| REQ-E2E-X-008 | P0 必须保证真实 API key 不进入 git、报告 artifact、audit payload 或截图文本。 | must | security |
| REQ-E2E-X-009 | P1 必须覆盖 OpenAI、Anthropic、LangGraph、MCP、Codex adapter/framework 的 runtime E2E。 | should | user |
| REQ-E2E-X-010 | P1 必须覆盖 approval provider approve/reject/timeout 的 E2E。 | should | product |
| REQ-E2E-X-011 | P1 必须覆盖并发 agent 的 audit hash chain、trace 和 observer summary。 | should | reliability |
| REQ-E2E-X-012 | P2 必须预留 sidecar backend、remote executor、staging/design partner、长任务/中断恢复 E2E。 | should | roadmap |
| REQ-E2E-X-013 | 所有 E2E 结果必须更新 `E2E_TEST_REPORT.md`，解释用例设计、命令、输出结果、输出解释和结论。 | must | QA |
| REQ-E2E-X-014 | 默认 CI 只运行无密钥、可稳定复现的 automated E2E；真实 provider 和 staging 走 manual gate。 | must | CI |
| REQ-E2E-X-015 | E2E readiness test 必须阻止计划、测试文件和报告索引漂移。 | must | QA |

## Non-Functional Requirements

- Performance：默认 E2E 集合目标在本地 2 分钟内完成；真实 provider 和 staging manual gate 不计入默认 CI 时间。
- Reliability：依赖 Docker daemon、外部 provider 或网络的用例必须区分功能失败和环境不可用，环境不可用时给出明确 skip 或 manual blocked 原因。
- Security and privacy：所有密钥只通过 ignored `.env`、环境变量或 CI secret 注入；报告必须扫描并确认无真实 key。
- Accessibility：run view / complete report 浏览器验收至少检查主内容可见、文本不遮挡、JSON beauty view 可读；完整无障碍审计不属于 P0。
- Compatibility：Python 3.12 是默认验证版本；adapter/framework E2E 不得把可选依赖变成 core runtime 必装依赖。
- Observability：每条 runtime E2E 必须验证 audit 和 trace；涉及 sandbox 的 E2E 必须验证 sandbox enforcement evidence。

## Acceptance Criteria

- AC-E2E-X-001：`E2E_TEST_PLAN.md` 增加 P0/P1/P2 matrix，并包含本 spec 的 requirement ID。
- AC-E2E-X-002：P0 新增或升级自动化/手工 E2E 测试入口，覆盖 REQ-E2E-X-003 到 REQ-E2E-X-008。
- AC-E2E-X-003：真实 provider manual E2E 可在 `.env` 有 key 时运行，报告显示 `provider_mode == "real"`，且 artifact 不包含 key。
- AC-E2E-X-004：direct vs registered E2E 证明 registered deny 不会 fallback direct execution。
- AC-E2E-X-005：Docker sandbox failure E2E 至少覆盖 no-network、read-only、env allowlist、timeout 四类行为。
- AC-E2E-X-006：run view/browser E2E 生成可提交的截图路径说明或本地 artifact，并在报告中解释页面能看到的内容。
- AC-E2E-X-007：P1/P2 尚未实现的 E2E 必须在计划和报告中标记为 planned/manual/deferred，而不是伪装成 verified。
- AC-E2E-X-008：`PYTHONPATH=src python -m pytest tests/e2e tests/test_e2e_readiness.py -q` 通过。
- AC-E2E-X-009：`python -m ruff check .`、`python -m pyright src`、`PYTHONPATH=src python -m pytest -q` 通过。
- AC-E2E-X-010：新增或更新的公开文档不包含真实密钥、客户数据或本地私有假设。

## Prototype Need

- Required：conditional
- Reason：run view / complete report 是可视化验收表面，需要截图或 HTML browser evidence。
- Expected fidelity：existing pattern reference。P0 不要求重新设计 UI，只要求验证现有 HTML 报告能展示完整运行过程。

## Constraints

- `.env`、`.agent-runtime/` 和 draft/local/private 文档不得提交。
- 默认 CI 不应依赖真实 API key、外部 provider SLA 或持久 Docker container。
- 可选生态依赖必须保持 optional，不进入 core runtime 默认安装路径。
- Docker E2E 可以使用短命 `--rm` 容器；若需要人工观察，必须作为 debug/manual 模式，不影响默认测试。
- E2E 报告必须使用中文；英文术语可保留为必要专有名词。

## P0 Implementation Scope

P0 是本轮 loop 的优先落地范围：

1. 扩展 `E2E_TEST_PLAN.md`，新增 P0/P1/P2 backlog。
2. 增加真实 provider manual E2E 的脚本或测试入口，明确 `.env` key、输出 artifact 和 secret scan。
3. 增强 direct vs registered E2E，显式验证 deny 不 fallback。
4. 增加 Docker sandbox failure paths E2E。
5. 增加 run view / complete report browser 或截图验收。
6. 更新 `E2E_TEST_REPORT.md`，记录新增 P0 证据。
7. 保留 P1/P2 为 planned/deferred，并补 readiness guard 防止计划漂移。

## P1 Implementation Scope

P1 在 P0 通过后推进：

- OpenAI、Anthropic、LangGraph、MCP、Codex adapter/framework runtime E2E。
- approval provider approve/reject/timeout E2E。
- 并发 agent audit hash chain、trace tree、observer summary E2E。
- provider retry/backoff 的 EOF、429、5xx 端到端验证。

## P2 Implementation Scope

P2 在 design partner 或 runtime backend 更成熟后推进：

- sidecar backend 真实进程 E2E。
- remote executor 本地测试服务 E2E。
- staging/design partner runbook 外部验收。
- 长任务、取消、中断恢复、资源压力和性能 E2E。

## Risks And Open Questions

| Risk or question | Impact | Owner | Status |
| --- | --- | --- | --- |
| 真实 provider 调用可能因网络、额度、provider 响应变化而不稳定。 | high | QA / Developer | 作为 manual gate，不进入默认 CI |
| Docker sandbox failure path 可能依赖宿主 Docker 行为。 | medium | Developer | 测试中区分 unavailable、unsupported 和 runtime failure |
| 浏览器截图自动化可能增加依赖和 CI 不稳定性。 | medium | QA | P0 优先本地可复现；CI 可先做 HTML 内容检查 |
| P1 adapter/framework E2E 可能引入大量 optional dependency。 | medium | Architect | 必须保持 optional extras 或 fixture/fake runtime path |
| staging/design partner 缺少真实外部环境。 | high | Product | P2 manual gate，先保留 runbook 和证据格式 |

## Change Control

- P0 范围变化需要同步更新本 spec、`E2E_TEST_PLAN.md` 和 `E2E_TEST_REPORT.md`。
- P1/P2 从 planned 进入 implementation 前，需要补对应 architecture brief、QA plan 和风险门禁。
- 任何新增真实 provider、Docker、sidecar、remote executor 行为必须经过 security/expert gate。

## Handoff Package

- `from_role`: Product Manager / QA
- `to_role`: Architect
- `handoff_reason`: 将 E2E 扩展需求转成 architecture brief、security gate 和 QA plan。
- `input_context`: 当前 E2E 只有 4 条 automated smoke 和 1 条 manual provider gate；用户要求补齐真实 provider、adapter/framework、sandbox failure、run view、approval、并发、sidecar、remote、staging 等 E2E。
- `decisions_already_made`: P0/P1/P2 分层；P0 先落地信任关键路径；真实 provider 和 staging 不进入默认 CI；可选生态依赖不进入 core runtime。
- `open_questions`: browser screenshot 是否需要进入 CI；P1 adapter/framework 是否优先 fake transport 还是真实 SDK；remote executor P2 用本地 fake service 还是真实 remote service。
- `expected_output`: architecture brief、security/expert gate、QA plan、implementation plan。
- `acceptance_criteria`: 本 spec 中 AC-E2E-X-001 到 AC-E2E-X-010。
- `risk_notes`: 密钥泄漏、Docker sandbox 误读、真实 provider 不稳定、optional dependency 膨胀。

## Spec Self-Review

- Placeholder scan：无 `TBD`、`TODO` 或空白模板项。
- Internal consistency：P0/P1/P2 范围与 requirements、acceptance criteria 一致。
- Scope check：完整 E2E backlog 较大，已拆为 P0 当前实现、P1/P2 后续推进。
- Ambiguity check：默认 CI、manual gate、optional dependency、secret boundary 和 Docker sandbox 边界均已明确。
