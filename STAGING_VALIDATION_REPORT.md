# Staging Validation Report

本报告记录当前仓库可复现的 staging/design partner surrogate 验证。它不代表外部 design partner 已签收，也不包含真实客户数据。

## 场景

测试 agent：`ProductionIncidentAgent`

职责：

- 读取生产服务部署状态。
- 检查错误日志和 feature flag。
- 在 sandboxed diagnostics 中运行诊断命令。
- 提出 rollback。
- 尝试执行未授权 hotfix。

验证目标：

- 对比同一个 agent 未注册到 runtime 和注册到 runtime 后的行为差异。
- 证明 runtime 能解释 agent 做了什么。
- 证明 policy/approval/sandbox/audit/trace 能解释为什么允许、为什么拒绝、是否强隔离、是否可审计。

## 命令

```bash
PYTHONPATH=src python examples/production_incident_comparison.py
```

## 输出

```text
Production Incident Agent comparison generated.
direct status: completed hotfix_applied=True
registered status: completed_with_denial hotfix_blocked=True
comparison json: .agent-runtime/production-incident-comparison/comparison.json
registered audit: .agent-runtime/production-incident-comparison/registered-audit.jsonl
registered run view: .agent-runtime/production-incident-comparison/registered-run-view.html
```

## 解释

未注册 direct execution：

- agent 可以直接调用本地工具。
- `apply_hotfix` 被执行，结果为 `hotfix_applied=True`。
- 不产生 runtime audit events。
- 不产生 runtime trace。

注册到 Agent Runtime：

- agent 通过 registry contract 注册。
- 所有工具调用进入 policy、approval、sandbox、audit 和 trace。
- diagnostics 进入 sandboxed command path。
- `apply_hotfix` 被 policy 拒绝，结果为 `hotfix_blocked=True`。
- 输出包含 comparison JSON、registered audit JSONL 和 registered run view HTML。

## 当前结论

该 surrogate staging 场景通过，证明当前 runtime preview 能完整展示一次复杂 agent 运行过程，并能阻止未授权高风险动作。

仍需外部 design partner：

- 用真实仓库、真实 staging service 或真实内部 automation 场景复跑 runbook。
- 记录 operator 是否能读懂 run view。
- 记录 policy denial 是否足够可解释。
- 记录 sandbox backend 是否符合宿主安全基线。
- 记录 audit export 是否满足团队审计流程。
