# Session Memory

中文：这是一个用于跨会话保存和恢复高价值项目上下文的 Codex skill。  
English: A Codex skill for keeping high-value project context across sessions.

## 设计取向 | Design Philosophy

中文：这个 skill 来自一种偏轻量化的工作方式：少记录无效过程，少引入复杂机制，只保留真正影响项目推进的上下文。  
English: This skill comes from a lightweight way of working: record less noise, avoid heavy process, and keep only the context that changes how a project moves forward.

## 项目说明 | What It Does

中文：`session-memory` 用来保留项目中真正重要的信息，而不是依赖冗长聊天记录。  
English: `session-memory` preserves the parts of project context that actually matter, instead of relying on long chat history.

中文：它主要保存这些内容：  
English: It is designed to keep:

- 当前目标 | current goals
- 当前思路 | working approach
- 重要决策 | important decisions
- 已确认结论 | confirmed findings
- 失败路径 | failed paths
- 下一步动作 | next actions

## Sleep / Dream

中文：这个 skill 还带有轻量的 sleep/dream 机制。它会在合适的时机按需触发提炼，生成更短的 `dream-notes.md`，用于记录正确轨迹、错误与错因、判断准则和预警信号；它不是后台常驻进程。  
English: This skill also includes a lightweight sleep/dream mechanism. It distills project memory on demand at suitable times and generates a shorter `dream-notes.md` with correct paths, mistakes and causes, heuristics, and warning signals; it is not a persistent background service.

## 常用口令 | Common Commands

中文：这个 skill 主要通过下面这些口令使用。  
English: This skill is mainly used through commands like:

- `session-memory 保存` / `session-memory save`
- `session-memory 恢复` / `session-memory restore`
- `session-memory 搜索 <关键词>` / `session-memory search <keyword>`
- `session-memory 检查` / `session-memory check`

中文：这些口令分别用于保存、恢复、搜索和检查当前项目记忆。  
English: These commands are used to save, restore, search, and check project memory.

## 使用案例 | Example Use Cases

中文：

- 当一个会话已经积累了较多研究和决策时，可以用 `session-memory 保存` / `session-memory save` 留下当前上下文，而不是下次重新解释。
- 当你在新会话中继续同一项目时，可以用 `session-memory 恢复` / `session-memory restore` 快速接上当前目标、思路和下一步。
- 当你只想确认某个方案为什么被放弃，或某个结论是否已经验证过时，可以用 `session-memory 搜索 <关键词>` / `session-memory search <keyword>` 做轻量检索。

English:

- After a session has accumulated enough research and decisions, use `session-memory 保存` / `session-memory save` to keep the current context instead of re-explaining it later.
- When continuing the same project in a new session, use `session-memory 恢复` / `session-memory restore` to quickly recover the current goal, approach, and next step.
- If you only need to check why a path was abandoned or whether something was already verified, use `session-memory 搜索 <关键词>` / `session-memory search <keyword>` for lightweight lookup.

## 核心文件 | Core Files

- `current.md`：当前项目状态 | current project state
- `history.md`：关键变化与决策 | key changes and decisions
- `dream-notes.md`：提炼后的经验、错因与预警信号 | distilled heuristics, mistakes, and warning signals

## 限制 | Limitations

中文：

- 这个 skill 依赖是否持续记录高价值信息；如果 `current.md` 和 `history.md` 长期不更新，恢复质量会下降。
- 它适合提炼和延续项目上下文，不适合替代完整文档、知识库或正式项目管理工具。
- sleep/dream 只做轻量提炼，不保证自动生成的内容总是完美，重要结论仍然需要人工判断。

English:

- This skill depends on whether high-value information is consistently recorded. If `current.md` and `history.md` are not updated, restore quality will degrade.
- It is designed for distilled project continuity, not as a replacement for full documentation, a knowledge base, or formal project management tools.
- The sleep/dream flow is lightweight and does not guarantee perfect distilled output, so important conclusions still need human judgment.

## 说明 | Notes

中文：这个项目主要面向本地 Codex skill 工作流。  
English: This project is intended for local Codex skill workflows.

## License

MIT
