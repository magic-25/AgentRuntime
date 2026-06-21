# Agent Runtime E2E 扩展 Security Gate

日期：2026-06-21

状态：通过但带必修项

上游 spec：[2026-06-21-e2e-expansion-spec.md](../specs/2026-06-21-e2e-expansion-spec.md)

## Security Surface

- 真实 provider key：来自 ignored `.env` 或环境变量。
- Provider transcript：可能包含 prompt、tool arguments、model response 和错误信息。
- Runtime tool execution：可能触发命令执行、sandbox、policy deny 和 approval。
- Docker sandbox：依赖宿主 Docker daemon、镜像可信链和容器配置。
- HTML/PNG report：可能把敏感输入、secret、路径或 provider payload 固化成 artifact。
- Sidecar/remote/staging：P2 涉及网络服务、执行器边界和外部审计。

## Findings

| ID | Severity | Finding | Required remediation | Status |
| --- | --- | --- | --- | --- |
| SEC-E2E-001 | high | 真实 provider key 不能进入 git、audit、trace、HTML、PNG 或 Markdown 报告。 | 所有真实 provider E2E 必须使用 ignored `.env` 或 env；提交前对 public docs 和 generated text 做 secret scan；报告只写环境变量名。 | required |
| SEC-E2E-002 | high | registered runtime deny 后若 fallback direct execution，会破坏 policy boundary。 | P0 必须有 deny-path E2E，断言 direct side effect 没有发生，audit/trace 记录 deny reason。 | required |
| SEC-E2E-003 | high | sandbox failure path 如果只测 happy path，会误导用户以为隔离完整。 | P0 必须覆盖 no-network、read-only、env allowlist、timeout/write deny，并明确 Docker 不等于绝对 escape prevention。 | required |
| SEC-E2E-004 | medium | Browser screenshot 可能保存敏感 prompt 或本地路径。 | Screenshot 只用于测试 fixture 或 redacted report；真实 provider screenshot 不提交。 | required |
| SEC-E2E-005 | medium | Adapter/framework E2E 可能引入供应链和 optional dependency 风险。 | P1 adapter E2E 使用 optional extras、fixture 或 fake transport；不得进入 core runtime dependency。 | planned |
| SEC-E2E-006 | medium | Sidecar/remote executor P2 涉及网络边界和执行权限。 | P2 前必须补单独 threat model 或 security gate；默认不标记 stable。 | deferred |

## Permission Checks

- Provider E2E 不需要仓库写权限以外的权限；`.env` 不提交。
- Docker E2E 需要本机 Docker daemon 权限；测试报告必须说明这不是生产容器逃逸证明。
- Runtime command execution 必须通过 policy capabilities 和 sandbox profile。
- Direct execution 只能用于对比，不能在 registered deny 后被 runtime 调用。

## Data Exposure Checks

- Public docs 可以写 `GLM_API_KEY`、`ZAI_API_KEY` 变量名，不能写真实值。
- Audit/trace/report 不应包含 secret environment value。
- `.agent-runtime/` 产物默认不提交。
- Provider raw payload 进入 report 前必须 redacted 或 summary 化。

## Destructive Action Checks

- Production incident agent 的 direct path 可以模拟 hotfix side effect，但必须在临时目录或内存状态中执行。
- Docker sandbox failure tests 不得写宿主敏感路径。
- Remote/sidecar P2 不得默认连接真实生产服务。

## Dependency And Generated-Code Checks

- P0 不新增必须安装的 provider SDK 或 browser automation dependency。
- 如引入 Playwright，必须在 dev/test extras，并保留无浏览器环境下的 skip/manual gate。
- Docker image 默认继续使用 `python:3.12-slim`，报告中写明镜像和短命 `--rm` 行为。

## Decision

Security gate: pass with required remediation.

允许进入 P0 implementation，前提是实现批次必须满足 SEC-E2E-001 到 SEC-E2E-004，并在 E2E report 中保留 residual risk。

## Residual Risk

- 真实 provider 外部调用仍可能因网络、额度和 provider 行为变化而不稳定。
- Docker sandbox E2E 只能证明 runtime 传入的 Docker 参数和本机执行路径，不证明绝对隔离。
- Browser evidence 在 P0 主要证明可视化内容完整，不是完整前端安全审计。

## Handoff Package

- `from_role`: Security
- `to_role`: QA / Developer
- `handoff_reason`: 把安全必修项转成 E2E assertions 和 secret scan。
- `input_context`: P0 涉及真实 provider、命令执行、Docker、HTML/PNG artifact。
- `decisions_already_made`: 真实 provider manual-only；Docker preview；截图不提交真实 provider secret 内容。
- `open_questions`: P1 是否引入 Playwright CI。
- `expected_output`: P0 E2E tests、secret scan command、更新后的 E2E report。
- `acceptance_criteria`: SEC-E2E-001 到 SEC-E2E-004 全部有测试或手工门禁证据。
- `risk_notes`: 密钥、fallback、sandbox 误读、截图泄漏。
