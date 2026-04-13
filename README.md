# Session Memory

`session-memory` 是一个面向 Codex/Coding Agent 工作流的本地 skill，用来保存、恢复、检索和检查“高价值会话记忆”。

它不追求保留完整聊天记录，而是把跨会话真正有用的内容结构化沉淀下来，例如：

- 当前目标与当前方案
- 为什么方案变了
- 已确认的研究结论
- 已完成工作与关键路径
- 有效做法、失败路线与风险
- 下一步应该从哪里继续

## Features

- Project-scoped memory by default, avoiding cross-project contamination
- `current.md` / `history.md` split for fast restore and selective history lookup
- Lightweight keyword search before full restore
- Save checkpoint recommendation based on high-value state transitions
- Background `dream` notes for extracting reusable lessons and risks

## Repository Layout

```text
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── current-template.md
│   └── history-template.md
└── scripts/
    ├── checkpoint_session_memory.py
    ├── dream_session_memory.py
    ├── init_session_memory.py
    ├── restore_session_memory.py
    ├── save_session_memory.py
    ├── search_session_memory.py
    └── session_memory_common.py
```

## Requirements

- Python 3.10+
- A Codex-compatible local skill directory

## Install

将仓库放到你的 skill 目录下，例如：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone <your-repo-url> "${CODEX_HOME:-$HOME/.codex}/skills/session-memory"
```

如果你的环境没有设置 `CODEX_HOME`，默认使用 `$HOME/.codex`。

## Usage

初始化记忆文件：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/init_session_memory.py" --workspace "$PWD" --scope auto
```

搜索已有记忆：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/search_session_memory.py" --workspace "$PWD" --scope auto --query "stripe webhook"
```

检查是否该保存：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/checkpoint_session_memory.py" --workspace "$PWD" --scope auto --event session-ending
```

准备保存：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/save_session_memory.py" --workspace "$PWD" --scope auto --stage prepare --init-if-missing
```

提交保存：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/save_session_memory.py" --workspace "$PWD" --scope auto --stage commit
```

恢复记忆：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/restore_session_memory.py" --workspace "$PWD" --scope auto
```

## Storage Model

默认优先使用项目级目录：

- Git 仓库内：`<git-root>/.codex/session-memory/`
- 非 Git 目录：`<workspace>/.codex/session-memory/`

全局索引与后台状态位于：

- `${CODEX_HOME:-$HOME/.codex}/session-memory/registry.json`
- `${CODEX_HOME:-$HOME/.codex}/session-memory/state.json`
- `${CODEX_HOME:-$HOME/.codex}/session-memory/dreams/`

## Open Source Notes

- 仓库不包含任何必需密钥或外部服务凭据。
- 运行时状态、日志和项目内 `.codex/` 产物已默认加入忽略规则。
- 如果你要发布自己的 fork，建议保留 `SKILL.md` 行为说明，但按你的 agent 平台规范调整入口描述。

## Contributing

见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

## License

本项目采用 [MIT License](./LICENSE)。
