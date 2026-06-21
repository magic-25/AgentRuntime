# Agent Runtime E2E 扩展 Interaction Spec

日期：2026-06-21

状态：待实现

上游 spec：[2026-06-21-e2e-expansion-spec.md](../specs/2026-06-21-e2e-expansion-spec.md)

## User Flow

1. 用户运行 E2E command 或 example。
2. runtime 执行 agent 场景并生成 audit、trace、run view 或 complete report。
3. 用户打开 HTML 报告或查看 screenshot。
4. 用户检查 agent 做了什么、为什么允许或拒绝、是否经过 sandbox、是否可审计。
5. 用户根据报告确认该场景通过、手工阻塞或需要修复。

## Screens Or Surfaces

- Run view HTML：单次 registered agent run 的完整运行过程。
- Complete report HTML：多个 agent scenario 的综合运行体验。
- Screenshot artifact：从 HTML 报告生成的本地 PNG 证据。
- E2E report Markdown：解释测试用例、命令、输出和结论。

## Prototype Or Wireframe

- Required: already covered by existing pattern
- Artifact: existing `run_view.py` 和 `examples/complete_runtime_report.py` 生成的 HTML。
- Fidelity: existing implementation reference。

## States

- Idle: 用户尚未运行 E2E，报告只提供命令和预期 artifact。
- Loading: P0 不新增加载 UI；浏览器打开本地静态 HTML。
- Success: 页面展示 agent identity、prompt、tool call/result、policy、approval、sandbox、audit、trace tree、raw evidence 和 JSON beauty view。
- Empty: 没有 artifact 时，测试报告必须说明命令未运行或 manual gate blocked。
- Error: provider unavailable、Docker unavailable、browser unavailable、policy regression、secret scan failed 必须在报告中分开说明。
- Permission denied: policy deny 必须可见，且显示拒绝原因；不能表现成 agent 普通失败。

## Interaction Rules

- 报告首屏或主要区域必须能看出这是哪个 agent、输入 prompt 是什么、运行状态是什么。
- policy allow/deny、approval approve/reject/timeout、sandbox enforced/unavailable 必须是独立可找的证据区域。
- JSON 内容必须使用 beauty view 或格式化文本，不能只显示压缩 JSON。
- screenshot 不应包含真实 API key、完整 secret 或本地私有路径以外的敏感数据。
- E2E report 必须把 screenshot/HTML 的内容解释清楚，不能只说“生成成功”。

## Accessibility And Responsive Constraints

- 静态 HTML 的文字不能互相遮挡。
- 关键证据区域需要有明确标题，便于浏览器搜索和人工审查。
- JSON beauty view 需要保持换行和缩进。
- P0 不做完整无障碍审计，但不得引入只能靠颜色理解的状态。

## Frontend Feasibility Notes

- P0 不重新设计 run view UI，只验证现有 HTML 能承载 E2E 证据。
- Browser screenshot 可以先作为 local/manual artifact；CI 先做 HTML 关键内容断言。
- 如果后续引入 Playwright，应作为 dev/test dependency，不进入 runtime core dependency。

## Requirement Trace

- REQ-E2E-X-007: Run view HTML、complete report HTML 和 screenshot artifact 验收。
- REQ-E2E-X-008: screenshot/report secret boundary。
- REQ-E2E-X-013: E2E report 必须解释 output 和 visual evidence。

## Handoff Package

- `from_role`: Interaction Designer
- `to_role`: QA / Developer
- `handoff_reason`: 明确 browser/report evidence 的可视化验收规则。
- `input_context`: P0 要证明 run view/complete report 能展示完整运行过程。
- `decisions_already_made`: 复用现有 HTML；P0 不重做 UI；CI 先做内容断言。
- `open_questions`: Playwright screenshot 是否在 P1 进入 CI。
- `expected_output`: browser/report E2E test 和 E2E report 更新。
- `acceptance_criteria`: HTML 包含关键证据区域；报告解释截图能看到什么；secret 不泄漏。
- `risk_notes`: 浏览器依赖可能让 CI 变脆，先保持 local/manual。
