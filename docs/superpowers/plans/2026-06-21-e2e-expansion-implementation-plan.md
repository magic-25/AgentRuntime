# Agent Runtime E2E 扩展 Implementation Plan

日期：2026-06-21

状态：待执行

上游 spec：[2026-06-21-e2e-expansion-spec.md](../specs/2026-06-21-e2e-expansion-spec.md)

## Goal

按 P0 优先级补齐 Agent Runtime E2E 起步覆盖：计划矩阵、真实 provider manual gate、direct vs registered deny no fallback、Docker sandbox failure paths、run view/browser evidence 和 secret boundary。

## Files And Ownership

- Create:
  - `tests/e2e/test_docker_sandbox_failure_paths_e2e.py`
  - `tests/e2e/test_run_view_browser_evidence_e2e.py`
  - optional `examples/real_provider_registered_runtime_e2e.py`
- Modify:
  - `docs/test/e2e-test-plan.md`
  - `docs/reports/e2e-test-report.md`
  - `tests/e2e/test_production_incident_run_view_e2e.py`
  - `tests/test_e2e_readiness.py`
  - possibly `examples/complete_runtime_report.py`
- Test:
  - `tests/e2e`
  - `tests/test_e2e_readiness.py`
  - related report/run view/provider tests。

## Steps

1. Update E2E plan/report skeleton with P0/P1/P2 backlog and requirement IDs.
2. Strengthen readiness test so it checks P0/P1/P2 sections, spec link and P0 test entry names.
3. Upgrade production incident E2E to assert deny no fallback using persisted comparison data and side-effect markers.
4. Add Docker sandbox failure E2E:
   - no-network command cannot reach network.
   - read-only filesystem blocks root write.
   - env allowlist prevents secret env exposure.
   - timeout returns governed timeout result.
   - Docker unavailable remains skip.
5. Add report/browser evidence E2E:
   - generate complete report or run view.
   - assert HTML contains prompt, policy, approval/sandbox/audit/trace, raw evidence and JSON beauty view.
   - optionally generate local screenshot when browser tooling exists.
6. Add or document real provider registered runtime manual command:
   - reads `.env` / env only.
   - writes local `.agent-runtime` artifacts.
   - reports provider mode real and secret scan command.
7. Update `docs/reports/e2e-test-report.md` with new P0 outputs, explanations and residual risks.
8. Run verification and commit in focused batches.

## Reuse Strategy

- Reuse `build_production_incident_comparison` for direct vs registered E2E.
- Reuse `DockerSandboxBackend` and existing sandboxed command tool registration pattern.
- Reuse complete report and run view builders instead of adding a new renderer.
- Reuse readiness test pattern to prevent doc/test drift.
- Reuse existing optional provider testing helpers and `.env.example` rules.

## Traceability

- REQ-E2E-X-001: `docs/test/e2e-test-plan.md` P0/P1/P2 matrix and readiness test.
- REQ-E2E-X-003: manual provider command and report section.
- REQ-E2E-X-004/005: upgraded production incident E2E.
- REQ-E2E-X-006: new Docker sandbox failure E2E.
- REQ-E2E-X-007: new run view/browser evidence E2E.
- REQ-E2E-X-008: secret scan and docs/report constraints.
- REQ-E2E-X-013: updated `docs/reports/e2e-test-report.md`。

## Test Strategy

- Unit: only if implementation changes runtime helpers; otherwise not required for doc/test-only harness changes.
- Integration: use existing provider/report/sandbox integration tests.
- Contract: preserve adapter/sandbox/certification conformance.
- E2E: new and upgraded P0 E2E under `tests/e2e`。
- Manual: real provider and optional browser screenshot。
- Test data: fake provider, production incident fixture, temporary Docker workspace, ignored `.env`。

## Verification

- Command: `PYTHONPATH=src python -m pytest tests/e2e tests/test_e2e_readiness.py -q`
- Expected result: all E2E/readiness tests pass or Docker-specific tests skip with explicit unavailable reason.
- Command: `PYTHONPATH=src python -m pytest -q`
- Expected result: full suite passes.
- Command: `python -m ruff check . && python -m pyright src && python -m compileall -q src examples`
- Expected result: lint/type/compile clean.
- Command: secret scan over changed public docs and tests.
- Expected result: no real secrets.

## Release Plan

- Deployment: docs/tests only for P0 start; no package behavior change unless runtime bug found.
- Migration: none.
- Feature flag or rollout: real provider/browser remains manual.
- Observability: new E2E asserts audit/trace visibility.
- CI or blocking checks: existing CI plus expanded E2E smoke.

## Rollback Or Compatibility Notes

- Revert new E2E tests/docs if CI instability appears; runtime behavior should remain compatible.
- Docker failure E2E must keep skip behavior for hosts without Docker daemon.
- Manual provider path must not require provider SDK as core dependency.

## Handoff Package

- `from_role`: Developer Planner
- `to_role`: Developer
- `handoff_reason`: Execute P0 implementation batches.
- `input_context`: Spec、architecture、interaction、security、QA artifacts are available.
- `decisions_already_made`: P0 first; real provider manual-only; browser screenshot local/manual first; Docker preview remains preview.
- `open_questions`: Whether to make browser screenshot CI-blocking in P1.
- `expected_output`: P0 E2E tests, updated reports, verification output, commit/push.
- `acceptance_criteria`: AC-E2E-X-001 到 AC-E2E-X-010。
- `risk_notes`: Docker host variance, provider instability, secret leakage, flaky visual tooling.
