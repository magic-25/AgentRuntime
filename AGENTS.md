# 项目协作约束

## 文档提交规则

以下文档属于本地、私有、草稿或内部协作材料，不提交到仓库：

- `docs/local/`
- `docs/private/`
- `docs/drafts/`
- `docs/internal/`
- `docs/superpowers/specs/local/`
- `docs/superpowers/specs/private/`
- `docs/superpowers/specs/drafts/`
- `docs/superpowers/plans/local/`
- `docs/superpowers/plans/private/`
- `docs/superpowers/plans/drafts/`
- `*.local.md`
- `*.private.md`
- `*.draft.md`

这些路径和后缀必须同步维护在 `.gitignore` 中。

## 本地/私有文档语言规则

所有不会提交的 spec、草稿、私有说明、内部备忘和本地协作文档，只使用中文编写。

如果需要记录英文术语，可以保留必要的专有名词，例如 `agent runtime`、`policy engine`、`audit sink`、`executor`，但正文说明应使用中文。

## 可提交文档

准备长期保留、对外共享或作为正式项目依据的文档，可以放在未被 `.gitignore` 排除的路径中。

可提交文档在提交前应确认：

- 没有包含密钥、凭证、客户数据或生产敏感信息。
- 没有包含只适合本地讨论的临时假设。
- 文档状态清晰，例如草稿、待评审或已批准。

## 本项目角色 Overlay

项目级评审角色放在 `roles/overlays/` 下，不修改全局 skill 或全局 role registry。

overlay 至少包含：

- `roles/overlays/<role-slug>/SKILL.md`
- `roles/overlays/<role-slug>/memory.md`
- `roles/overlays/role-registry.overlay.json`

使用 `role-review-matrix` 做本项目评审时，应先读取全局角色，再读取本项目 overlay。若 overlay 角色和全局角色有重叠，以 overlay 中声明的边界为准。
