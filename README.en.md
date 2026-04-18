# Session Memory

[中文说明](./README.md)

> A Codex skill for keeping high-value project context across sessions, without rereading long chat history.

## What It Is

`session-memory` keeps the context that still affects future work, instead of storing full chat transcripts.

It mainly preserves:

- current goal
- working approach
- key decisions
- confirmed findings
- failed paths
- next step

## What Problem It Solves

- The session becomes too long and important context gets buried in chat noise
- A new session has to reconstruct goals, constraints, and conclusions from scratch
- The approach changed, but later it is hard to remember why
- Branch research accumulates and starts polluting the main path

## Quick Start

```bash
session-memory save
session-memory research-save
session-memory restore
session-memory search <keyword>
session-memory check
```

For a first-time user, it is enough to know these five actions: mainline save, research append, restore, search, and check whether now is a good time to save.

## When To Use

- The current session is getting long and you are about to stop or switch to a new one
- The main goal, approach, key conclusion, or next step has changed
- You want to keep branch research without polluting the main line
- You only want to check one old conclusion instead of restoring everything

## What It Is Not For

- Full documentation
- Long-term knowledge base
- Project management
- Raw chat transcript backup

## Design Philosophy

This skill comes from a lightweight way of working: record less noise, avoid heavy process, and keep only the context that changes how a project moves forward.

## Sleep / Dream

This skill also includes a lightweight sleep/dream mechanism. It distills project memory on demand at suitable times and generates a shorter `dream-notes.md` with correct paths, mistakes and causes, heuristics, and warning signals; it is not a persistent background service.

`dream-notes.md` is overwritten on each distilled run, so it does not grow forever inside the project; the parts that do grow over time are the global `dreams/` snapshot directory and the append-only `history.md`.

The default hot path only reads `current.md`, `history.md`, and `dream-notes.md`. `archive` is the cold layer created after dream-time slimming and should not be read unless archived context is explicitly requested.

For split research within the same project, the minimal research layer uses `research.md` as an append-only research log. `research-save` appends there instead of overwriting the main `current.md`. `research.md` participates in dream distillation and post-dream archive slimming, but it stays out of the default restore/search hot path unless research context is explicitly requested.

## Common Commands

This skill is mainly used through commands like:

- `session-memory 保存` / `session-memory save`
- `session-memory 研究保存` / `session-memory research-save`
- `session-memory 恢复` / `session-memory restore`
- `session-memory 搜索 <关键词>` / `session-memory search <keyword>`
- `session-memory 检查` / `session-memory check`

These commands are used for mainline save, research append, restore, search, and checkpointing project memory.

## Example Use Cases

- After a session has accumulated enough research and decisions, use `session-memory 保存` / `session-memory save` to keep the current context instead of re-explaining it later.
- When continuing the same project in a new session, use `session-memory 恢复` / `session-memory restore` to quickly recover the current goal, approach, and next step.
- If you only need to check why a path was abandoned or whether something was already verified, use `session-memory 搜索 <关键词>` / `session-memory search <keyword>` for lightweight lookup.
- When experimenting in `main-local`, a feature branch, or another work context, use `session-memory 研究保存` / `session-memory research-save` to append staged research into `research.md` with an explicit `work context`. That keeps same-project multi-fork and multi-stage research append-only instead of overwriting the main `current.md`.

## Core Files

- `current.md`: current project state
- `history.md`: key changes and decisions
- `research.md`: append-only research log for multiple work contexts in the same project
- `dream-notes.md`: distilled heuristics, mistakes, and warning signals

## Archive

Archive is not a primary read layer. It is the cold-layer slimming step that follows a successful dream pass, storing superseded history, older dream snapshots, and research entries from `research.md` that were either merged into the main line or explicitly marked invalid.

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/archive_session_memory.py" --workspace "$PWD" --scope auto --dry-run
```

`archive` should stay unread by default. Only include it when you explicitly want archived context, such as checking why an old branch was abandoned.

## Limitations

- This skill depends on whether high-value information is consistently recorded. If `current.md` and `history.md` are not updated, restore quality will degrade.
- It is designed for distilled project continuity, not as a replacement for full documentation, a knowledge base, or formal project management tools.
- The sleep/dream flow is lightweight and does not guarantee perfect distilled output, so important conclusions still need human judgment.

## Notes

This project is intended for local Codex skill workflows.

## License

MIT
