# Agent Runtime E2E 扩展 QA Plan

日期：2026-06-21

状态：待执行

上游 spec：[2026-06-21-e2e-expansion-spec.md](../specs/2026-06-21-e2e-expansion-spec.md)

## Acceptance Criteria Under Test

- AC-E2E-X-001：E2E plan 有 P0/P1/P2 matrix 和 requirement ID。
- AC-E2E-X-002：P0 新增或升级 E2E 覆盖真实 provider、direct vs registered、deny no fallback、Docker failure、browser/report evidence、secret boundary。
- AC-E2E-X-003：真实 provider manual E2E 可运行且不泄漏 key。
- AC-E2E-X-004：direct vs registered E2E 证明 registered deny 不 fallback。
- AC-E2E-X-005：Docker sandbox failure E2E 覆盖 no-network、read-only、env allowlist、timeout。
- AC-E2E-X-006：run view/browser E2E 有 HTML/screenshot evidence。
- AC-E2E-X-007：P1/P2 未实现项标记 planned/manual/deferred。
- AC-E2E-X-008 到 AC-E2E-X-010：E2E、lint、type、full tests、secret scan 通过。

## Test Matrix

| Requirement ID | Scenario | Level | Expected result | Evidence |
| --- | --- | --- | --- | --- |
| REQ-E2E-X-001 | P0/P1/P2 backlog readiness | doc/readiness | Plan/report/spec 同步 | `tests/test_e2e_readiness.py` |
| REQ-E2E-X-003 | Real provider registered runtime | manual E2E | 有 key 时 provider mode real，runtime audit/trace/report 存在 | manual report section |
| REQ-E2E-X-004 | Direct vs registered comparison | automated E2E | direct side effect 与 registered governed denial 差异明确 | `tests/e2e/test_production_incident_run_view_e2e.py` |
| REQ-E2E-X-005 | Registered deny no fallback | automated E2E | deny 后 direct-only marker 不出现 | upgraded comparison test |
| REQ-E2E-X-006 | Docker no-network/read-only/env/timeout | automated E2E with skip | Docker available 时执行并验证 failure semantics | new Docker failure test |
| REQ-E2E-X-007 | Browser/report evidence | automated/manual E2E | HTML 包含关键区域；本地可生成 screenshot | new report/browser test or manual command |
| REQ-E2E-X-008 | Secret boundary | automated scan/manual | public docs/report text 不含真实 key pattern | `rg` scan output |
| REQ-E2E-X-009 | Adapter/framework P1 | planned | 标记 planned，不伪装 verified | plan/report |
| REQ-E2E-X-012 | Sidecar/remote/staging P2 | deferred/manual | 标记 deferred/manual gate | plan/report |

## Test Data And Environment

- Data: production incident fixture、fake provider response、Docker sandbox command、complete report fixture。
- Environment: Python 3.12、pytest、optional local Docker daemon、optional `.env` provider key、optional local browser。
- Fixtures or accounts: no committed provider key；真实 provider 使用用户本地 `.env`。

## E2E Paths

- P0-AUTO-001：production incident direct vs registered deny no fallback。
- P0-AUTO-002：Docker sandbox failure paths。
- P0-AUTO-003：complete report / run view HTML evidence content。
- P0-MANUAL-001：real provider registered runtime complete report。
- P1-PLANNED-001：OpenAI/Anthropic/LangGraph/MCP/Codex adapter runtime E2E。
- P1-PLANNED-002：approval provider approve/reject/timeout。
- P1-PLANNED-003：concurrent audit/trace/observer E2E。
- P2-DEFERRED-001：sidecar、remote executor、staging/design partner、long-running recovery。

## Contract Checks

- Agent registry contract: metadata、capabilities、runtime profile、lifecycle events。
- Runtime governance contract: policy deny/allow、approval、sandbox、audit、trace。
- Docker sandbox contract: no-network、read-only、env allowlist、timeout/write deny。
- Report contract: HTML/JSON/PNG artifact includes governance evidence and avoids secrets。
- Manual gate contract: real provider key is local-only and never committed。

## Regression Scope

- Existing `tests/e2e` smoke tests must continue passing。
- Existing `tests/test_provider_real_agent.py` optional provider tests must not become mandatory CI。
- Existing complete report and run view output format must remain backward-compatible enough for current docs/tests。
- Docker backend remains preview and stable candidate gate remains unchanged。

## CI And Blocking Checks

- `PYTHONPATH=src python -m pytest tests/e2e tests/test_e2e_readiness.py -q`
- `PYTHONPATH=src python -m pytest -q`
- `python -m ruff check .`
- `python -m pyright src`
- `python -m compileall -q src examples`
- `rg -n "(api[_-]?key|apikey|secret|token|password|sk-[A-Za-z0-9]|[A-Za-z0-9]{32,}\\.[A-Za-z0-9]{10,})" <changed public files>`

## Not Tested

- Real provider E2E in default CI：不测，因为依赖真实 key、网络和 provider SLA。
- Browser pixel-perfect visual regression：P0 不测，只做内容和本地 screenshot evidence。
- Production-grade sandbox escape prevention：不测，Docker E2E 只验证 runtime enforcement 和本地 Docker execution。
- Remote executor real service：P2 deferred。

## Verification Report

- Command: 待 P0 implementation 后填写。
- Result: 待 P0 implementation 后填写。
- Evidence:
  - Screenshot or recording: P0 local artifact 或 manual report。
  - Logs or test output: pytest、ruff、pyright、secret scan。
- Residual risk: provider instability、Docker host variance、browser dependency。
