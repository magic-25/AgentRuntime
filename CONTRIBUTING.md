# Contributing

感谢你关注 Agent Runtime。当前项目处于 **Technical Preview**，下一门禁是 **Design Partner Pilot**。贡献重点应围绕 runtime contracts、policy/audit/sandbox、adapter、conformance certification 和 platform-ready manifest 的可验证性展开。

## 当前贡献边界

优先接受：

- 修复 runtime core、policy、audit、observer、sandbox、adapter 的明确 bug。
- 增加或强化 conformance、replay、certification、evidence 相关测试。
- 改进公开文档中和当前实现不一致、过度承诺或边界不清的内容。
- 增加 design partner pilot 所需的最小、可禁用、可审计能力。

暂不接受：

- 默认启用 optional adapter/backend pack。
- 把 weak subprocess 描述或改造成高风险生产安全沙箱。
- hosted SaaS、hosted control plane、enterprise console、RBAC UI。
- 不带测试或 evidence 的稳定性、生产就绪、安全性声明。
- 绕过 policy/audit/sandbox 链路的工具执行入口。

## 开发环境

首次克隆后推荐使用 editable install，并安装开发依赖：

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
python -m pytest
python examples/minimal_agent.py
```

只验证 CLI 初始化和配置校验：

```bash
agent-runtime init --path agent-runtime.json
agent-runtime validate --path agent-runtime.json
```

## 提交前检查

至少运行：

```bash
python -m pytest
python -m compileall -q src examples
python -m ruff check .
python -m pyright src
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
```

当前 Ruff 门槛覆盖 `E4/E7/E9/F/B`。格式化、导入排序和更激进的现代化规则会单独推进，避免把贡献 review 变成大规模机械 diff。

如果改动涉及 sandbox/backend，还应运行：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend docker --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend sidecar --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run
```

如果本机具备 Docker，也建议运行：

```bash
PYTHONPATH=src python -m agent_runtime.cli.main sandbox evidence --backend container --run-smoke --image busybox:latest
```

Docker smoke 只证明当前环境可以执行 no-network/read-only/cap-drop smoke，不证明绝对逃逸防护。

## 分支与合并规则

`main` 是受保护分支。除紧急仓库恢复操作外，所有代码、公开文档、测试、CI 和 release 配置变更都必须通过 Pull Request 合并。

PR 合并前必须满足：

- 分支从最新 `main` 创建，并保持和 `main` 可合并。
- GitHub Actions `CI / Python 3.12` 通过。
- PR 描述包含验证命令和风险说明。
- 所有 review conversation 已解决。
- 不使用 force push、直接 push `main` 或绕过 runtime governance 的临时提交。

维护者发现本地已经在 `main` 上产生变更时，应先新建分支保留变更，再通过 PR 合并；不得继续把后续变更直接推到 `main`。

## 代码要求

- 保持工具调用链路经过 `ToolCall -> Context Filter -> Policy Engine -> Approval Gate -> Executor -> Result Filter -> Audit`。
- adapter 只做 provider/tool-call shape 翻译，不授予 capability，不直接绕过 runtime 执行工具。
- optional pack 默认 disabled，必须 explicit allowlist。
- `require_approval` 没有显式 approval provider 时必须 reject，不应默认批准。
- 高风险 prod command tool 必须使用 `sandboxed_command_tool` 和宿主注入的强隔离 sandbox backend。
- sandbox backend 收到的 env 必须已经按 allowlist 裁剪，不应接触未授权 secret。
- backend 不可用时应 fail closed，不应退回普通 subprocess。
- 新增稳定候选能力时必须补 conformance evidence 和测试引用。

## 文档要求

- 对外文档不得包含密钥、凭证、客户数据或生产敏感信息。
- 对外文档不得把 Technical Preview 写成 public launch 或 hosted enterprise platform。
- 对外文档中的 support level 必须和 `agent-runtime release status` 保持一致。
- 本地、私有、草稿或内部协作文档放在 `.gitignore` 排除路径中，并只使用中文正文。

## Pull Request 建议

PR 描述建议包含：

- 改动目的。
- 影响的 runtime contract 或 public API。
- policy/audit/sandbox 影响。
- 运行过的验证命令。
- 已知限制和回滚方式。

## Issue 建议

请优先使用仓库内的 GitHub issue templates：

- Bug report：可复现 bug。
- Feature request：能力、contract、adapter 或 workflow 改进。
- Design partner feedback：不含敏感信息的 pilot/staging 反馈。
- Security boundary question：公开讨论边界问题；真实漏洞请按 `SECURITY.md` 私下报告。
