# Release Checklist

Agent Runtime 当前发布目标是 **v0.1.0 Technical Preview**。这不是 public stable release，也不是 hosted platform release。

## 已完成

- GitHub repository 为 public。
- `main` branch protection 已与 `ReviewMatrix` 对齐：enforce admins，禁止 force push/delete，启用 required pull request flow、required conversation resolution、required linear history 和严格 required status check `Python 3.12`；`required_approving_review_count` 当前按项目约束保持 `0`。
- GitHub private vulnerability reporting 已启用。
- Apache-2.0 license、code of conduct、security policy、contributing guide、issue templates、PR template 和 CI 已提交。
- CI 覆盖 compile、ruff `E4/E7/E9/F/B`、`pyright src`、pytest、certification、adapter replay 和 sandbox conformance。
- `DockerSandboxBackend` 是显式 opt-in preview，仍不标记 stable candidate。
- `ContainerSandboxBackend` 明确为 plan simulation，不执行真实 Docker container。
- Production incident staging dry run 已生成 comparison、audit 和 run view artifacts。
- OpenAI、Anthropic、LangGraph、MCP、Codex adapter 已有匿名 payload fixture 回归测试。

## 发布前验证命令

```bash
python -m ruff check .
python -m compileall -q src examples
python -m pyright src
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m pytest tests/e2e -q
PYTHONPATH=src python -m agent_runtime.cli.main certify run --subject all
PYTHONPATH=src python -m agent_runtime.cli.main adapter replay --scenario code-ci --adapter openai --adapter langgraph --adapter codex
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend container --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend docker --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend sidecar --dry-run
PYTHONPATH=src python -m agent_runtime.cli.main sandbox conformance --backend remote --dry-run
python -m build
python -m twine check dist/*
```

## GitHub Release

发布 tag：`v0.1.0`

Release notes 必须说明：

- 当前是 technical preview。
- sandbox 不是绝对逃逸防护。
- Docker backend 是 preview。
- remote executor 是 contract beta。
- hosted control plane / SaaS / enterprise console 不在当前范围。

## PyPI

PyPI publish 需要项目 owner 的 PyPI API token。当前仓库已具备 build 和 twine check 流程；拿到 token 后再执行：

```bash
python -m build
python -m twine check dist/*
python -m twine upload dist/*
```

不要把 PyPI token 写入仓库或 `.env.example`。

## 回滚

如果 GitHub release 或 tag 有问题：

```bash
gh release delete v0.1.0 --cleanup-tag
```

如果 PyPI 已发布，不能真正删除版本号；只能发布修复版本，并在 release notes 中说明问题。
