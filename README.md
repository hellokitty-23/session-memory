# Session Memory

[English README](./README.en.md)

> 这是一个用于跨会话保留高价值项目上下文的 Codex skill，让你不必反复翻长聊天记录。

## 这是什么

`session-memory` 用来保留真正会影响后续推进的上下文，而不是保存整段聊天历史。

它主要保留这些内容：

- 当前目标
- 当前思路
- 关键决策
- 已确认结论
- 失败路径
- 下一步动作

## 它解决什么问题

- 会话太长，重要上下文被聊天噪声淹没
- 新会话接手时，需要重新解释目标、约束和结论
- 方案变了，但之后很难回忆“为什么变”
- 分支研究很多，主线和旁路容易混在一起

## 快速开始

```bash
session-memory 保存
session-memory 研究保存
session-memory 恢复
session-memory 搜索 <关键词>
session-memory 检查
```

第一次接触这个仓库的用户，只要先知道这 5 个动作分别是主线保存、研究追加、恢复、检索和检查时机，就可以开始使用。

## 什么时候用

- 当前会话已经变长，准备结束或切到新会话
- 当前主目标、主方案、关键结论或下一步发生了变化
- 你想保留某条分支研究，但不想污染主线
- 你只想快速查一个旧结论，而不是恢复整份上下文

## 不适合什么

- 完整文档系统
- 长期知识库
- 项目管理工具
- 原始聊天记录备份

## 设计取向

这个 skill 来自一种偏轻量化的工作方式：少记录无效过程，少引入复杂机制，只保留真正影响项目推进的上下文。

## Sleep / Dream

这个 skill 还带有轻量的 sleep/dream 机制。它会在合适的时机按需触发提炼，生成更短的 `dream-notes.md`，用于记录正确轨迹、错误与错因、判断准则和预警信号；它不是后台常驻进程。

`dream-notes.md` 是覆盖式提炼稿，不会因为 sleep 次数持续在项目里无限追加；真正会逐步增加的是全局 `dreams/` 快照目录，以及项目里的追加式 `history.md`。

默认热路径只看 `current.md`、`history.md`、`dream-notes.md`。`archive` 是 dream 之后瘦身出来的冷层，除非主动要求查看归档，否则不应默认读取。

对于同项目下的分叉研究，最小版研究层使用 `research.md` 作为研究流水账。`研究保存` 只往这里追加，不直接覆盖主线 `current.md`。`research.md` 会参与 dream 提炼和 dream 后归档，但默认不进入恢复/检索热路径，除非你明确要求查看研究层。

## 记忆空间路由

默认 `--scope auto` 会优先把当前目录解析到“共享项目记忆”：

- Git 项目：默认落到 `<git-root>/.codex/session-memory/`
- 非 Git 项目：如果某个祖先目录已经存在 `.codex/session-memory/`，默认继续复用那一层
- 只有上述共享根都不存在时，才退回当前目录自己的 `.codex/session-memory/`

如果同一项目里需要两套或多套互不覆盖的研究记忆，在项目根创建 `.codex/session-memory/config.toml`：

```toml
[spaces]
"当前路线" = "current-research"
"旧路线" = "legacy-research"
```

如果你更喜欢最简写法，也兼容直接写 `"记忆1" = "current-research"`。

规则很简单：

- key 是记忆空间名，value 是相对项目根的子目录
- 当当前工作目录落在某个子目录内时，读写目标会切到 `<子目录>/.codex/session-memory/`
- 多条路径重叠时，按最长匹配优先
- 不会自动混读项目共享层和其他记忆空间
- `研究保存` 仍然只是追加当前命中的 `research.md`

## 常用口令

这个 skill 主要通过下面这些口令使用：

- `session-memory 保存` / `session-memory save`
- `session-memory 研究保存` / `session-memory research-save`
- `session-memory 恢复` / `session-memory restore`
- `session-memory 搜索 <关键词>` / `session-memory search <keyword>`
- `session-memory 检查` / `session-memory check`

这些口令分别用于主线保存、研究追加、恢复、搜索和检查当前项目记忆。

## 使用案例

- 当一个会话已经积累了较多研究和决策时，可以用 `session-memory 保存` / `session-memory save` 留下当前上下文，而不是下次重新解释。
- 当你在新会话中继续同一项目时，可以用 `session-memory 恢复` / `session-memory restore` 快速接上当前目标、思路和下一步。
- 当你只想确认某个方案为什么被放弃，或某个结论是否已经验证过时，可以用 `session-memory 搜索 <关键词>` / `session-memory search <keyword>` 做轻量检索。
- 当你只是在同一个记忆空间里分阶段记录研究时，用 `session-memory 研究保存` / `session-memory research-save` 把阶段性结论追加到当前空间的 `research.md`。
- 当你在同一项目里同时推进两条不同研究路线时，先在项目根配置 `config.toml` 划分独立记忆空间，再分别运行 `保存 / 研究保存 / 恢复 / 搜索`。这样不同本地 fork 或不同研究目录就不会互相覆盖。

## 核心文件

- `current.md`：当前项目状态
- `history.md`：关键变化与决策
- `research.md`：同项目多工作上下文的研究流水账
- `dream-notes.md`：提炼后的经验、错因与预警信号
- `config.toml`：可选的项目级路由配置，用来把不同子目录映射到独立记忆空间

## 归档

归档不是主读取层，而是 dream 成功后触发的冷层瘦身。它会存放已被新主线覆盖、但暂时不想直接删除的旧历史、旧 dream 快照，以及 `research.md` 里那些“已经并入主线”或“已经判定无效”的旧研究条目。

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/archive_session_memory.py" --workspace "$PWD" --scope auto --dry-run
```

默认情况下不应读取 `archive`；只有当你明确要“查归档”“看旧分支为什么被放弃”时，才应显式带上归档开关。

## 限制

- 这个 skill 依赖是否持续记录高价值信息；如果 `current.md` 和 `history.md` 长期不更新，恢复质量会下降。
- 它适合提炼和延续项目上下文，不适合替代完整文档、知识库或正式项目管理工具。
- sleep/dream 只做轻量提炼，不保证自动生成的内容总是完美，重要结论仍然需要人工判断。

## 说明

这个项目主要面向本地 Codex skill 工作流。

## License

MIT
