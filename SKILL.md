---
name: session-memory
description: 为 Codex 保存和恢复高价值会话记忆。适用于会话过长、准备结束当前会话、准备在新会话中接续同一项目，或需要保留决策、思路变化、已完成工作、研究结论、失败路线、约束和下一步，而不携带完整聊天记录的场景。
---

# Session Memory

这不是聊天摘要工具，而是一套“高价值会话记忆”机制。目标是只保留跨会话真正有用的状态，让新会话能快速恢复上下文，并支持轻量检索、保存时机检查、后台 sleep/dream 复盘。

## 开源仓库使用说明

- 这个仓库可直接作为本地 skill 使用，默认安装位置是 `${CODEX_HOME:-$HOME/.codex}/skills/session-memory`。
- 仓库不应提交运行时产物，例如 `__pycache__/`、`.DS_Store`、日志文件和项目内 `.codex/` 数据。
- 对外分发时，优先把行为约定写在 `SKILL.md`，把安装、贡献和许可证写在 `README.md`、`CONTRIBUTING.md`、`LICENSE`。
- 如果你的 agent 平台不是 Codex，可以复用 `scripts/` 和 `references/`，再按目标平台调整 skill 元数据和入口描述。

## 何时使用

- 用户说当前会话太长，context 太臃肿。
- 用户想在新会话中继续同一项工作。
- 用户想保留决策、研究结果、失败尝试和下一步。
- 一个任务存在明显的思路演化，需要记录“为什么变了”。
- 结束或归档会话前，需要留下可恢复的状态。
- 同时进行多个项目，必须避免项目间记忆串线。

## 快捷口令

默认使用以下固定口令，中英文别名等价：

- `session-memory 保存` / `session-memory save`：内部应拆成 `prepare -> 编辑文件 -> commit` 三步，不再是假定一次命令就完成保存。
- `session-memory 恢复` / `session-memory restore`：恢复当前项目的记忆，先读 `current.md`，必要时再读 `history.md`，并且只在有未消费 dream 时才读取 `dream-notes.md`。
- `session-memory 搜索 <关键词>` / `session-memory search <keyword>`：在当前项目的记忆中查旧结论、旧路径、旧决策。
- `session-memory 检查` / `session-memory check`：判断现在是否到了应该保存的时机。

对应脚本入口：

- 保存准备/提交：`scripts/save_session_memory.py --stage prepare|commit`
- 恢复：`scripts/restore_session_memory.py`
- 搜索：`scripts/search_session_memory.py`
- 检查：`scripts/checkpoint_session_memory.py`

如果项目记忆文件还不存在，`保存 / save` 的 `prepare` 阶段应先初始化。

默认使用中文记录。只有代码、命令、路径、API 名、库名、固定技术标识等内容保留原文。

## 存储规则

默认优先使用项目级记忆，避免不同项目互相污染：

- `<git-root>/.codex/session-memory/current.md`：当前最新状态，作为恢复入口。
- `<git-root>/.codex/session-memory/history.md`：追加式历史，只记录关键变化。

如果当前工作不在 Git 仓库中，就使用当前工作目录下的 `.codex/session-memory/`。

只有在明确处理“个人跨项目主题”时，才使用全局记忆。

## 全局索引与 sleep/dream

除了项目内的 `current.md/history.md`，这个 skill 现在还使用全局索引层：

- `${CODEX_HOME:-$HOME/.codex}/session-memory/registry.json`：记录已接触项目的位置和时间戳
- `${CODEX_HOME:-$HOME/.codex}/session-memory/state.json`：记录全局 sleep check / sleep 时间
- `${CODEX_HOME:-$HOME/.codex}/session-memory/sleep.lock`：防止同时触发多个后台 dream
- `${CODEX_HOME:-$HOME/.codex}/session-memory/dreams/`：保存每次 dream 的全局快照

每次执行 `恢复/搜索/检查` 时，都要先做统一前置钩子。`保存` 因为会先修改文件，所以改成两阶段：

- `save --stage prepare`：先定位并确保记忆文件存在
- 编辑 `current.md/history.md`
- `save --stage commit`：提交本次保存动作，登记项目并触发 `sleep check`

也就是说：

- `恢复/搜索/检查`：进入主动作前先跑前置钩子
- `保存`：只有 `commit` 阶段才登记项目活动并触发 `sleep check`

统一前置钩子内容：

1. 登记当前项目到全局 `registry`
2. 更新当前项目的 `last_active_at`
3. 检查距离上次 `sleep check` 是否超过 5 小时
4. 若超过，再判断是否存在需要 dream 的项目
5. 若需要且当前没有运行中的 dream，则后台异步启动一次 dream

dream 判定规则：

- `last_dream_at` 不存在
- 或 `last_active_at > last_dream_at`

任一满足即表示该项目需要进入本轮 dream。

## 轻量检索

当用户不是要“完整恢复”，而是只想追问一个具体问题时，优先检索，不要默认整份读取。

适用场景：

- `为什么之前放弃方案 A`
- `之前查过哪个仓库`
- `某个命令是否验证过`
- `某个路径、接口名、文件名之前记到哪里了`

默认命令：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/search_session_memory.py" --workspace "$PWD" --scope auto --query "关键词"
```

检索命中后：

1. 先简短复述命中点。
2. 只有当命中结果不足以支持当前任务时，再读取 `current.md` 或 `history.md`。
3. 不要把整份记忆文件一次性倒给用户。

## 初始化

默认初始化到项目根目录或当前工作目录：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/init_session_memory.py"
```

显式按当前目录自动判断项目范围：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/init_session_memory.py" --workspace "$PWD" --scope auto
```

显式初始化全局记忆：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/init_session_memory.py" --scope global
```

## 保存时机检查

在以下时刻，应该主动检查是否需要保存，而不是等用户提醒：

- 主目标变化
- 主方案变化
- 研究结论从“不确定”变成“已确认”
- 一个关键阻塞被清掉
- 下一步优先级变化
- 一个阶段性任务完成
- 会话准备结束

默认检查命令：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/checkpoint_session_memory.py" --workspace "$PWD" --scope auto
```

如果已知触发原因，带上 `--event`：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/checkpoint_session_memory.py" --workspace "$PWD" --scope auto --event approach-changed --event research-confirmed
```

事件枚举：

- `goal-changed`
- `approach-changed`
- `research-confirmed`
- `blocker-cleared`
- `next-step-changed`
- `task-completed`
- `session-ending`

处理规则：

1. `decision=INIT_FIRST`：先初始化，再保存。
2. `decision=SAVE_NOW`：应主动执行保存，不要等用户再补一句。
3. `decision=SKIP`：继续当前任务，不必强行记录。

## Sleep Check

`sleep check` 不是单独给用户使用的主命令，而是 `保存/恢复/搜索/检查` 的统一前置动作。

规则：

- 每次进入 `sm` 主动作时都先检查
- 若距离上次 `sleep check` 未超过 5 小时，直接跳过
- 若已超过 5 小时，再看是否存在需要 dream 的项目
- 若需要，则后台启动一次 `scripts/dream_session_memory.py`
- 同一时刻只允许一个 dream 运行，靠 `sleep.lock` 防重入

这个机制的目标不是“每次都做梦”，而是“隔一段时间按需做梦”。

## Dream 产物

每个项目的 dream 结果写到：

- `<project>/.codex/session-memory/dream-notes.md`

全局快照同时写到：

- `${CODEX_HOME:-$HOME/.codex}/session-memory/dreams/`

`dream-notes.md` 不是 `current.md/history.md` 的复制，而是项目提炼稿，只保留以后还能直接指导判断的内容：

- `正确轨迹`：最多 3 条，只记被证明有效的做法和路径
- `错误与错因`：最多 3 条，优先写成 `错误 -> 规避动作`，不要只写事故现象
- `判断准则`：最多 3 条，只记以后遇到类似问题该怎么判断
- `预警信号`：最多 3 条，只记哪些信号说明项目又在偏航或重踩旧坑

写法要求：

- 只写判断句，不写情绪、铺垫和解释性废话
- 能压成短句就不要写成长句
- 能提炼成规则就不要复述过程
- 没有实质内容的段落不要输出
- 如果提炼不出有效内容，就不要生成新的 dream 产物

## 恢复流程

当用户要求继续之前的工作时：

1. 先读取项目级 `.codex/session-memory/current.md`。
2. 只有当需要解释“为什么思路变了”时，再读取 `.codex/session-memory/history.md`。
3. 检查当前项目是否存在“未消费的新 dream 产物”：
   - `last_dream_at` 存在
   - 且 `last_dream_at > last_dream_consumed_at`
   - 且 `dream-notes.md` 存在
4. 只有满足上面条件时，才额外读取 `dream-notes.md`。
5. 先向用户简短复述恢复结果，再继续执行任务。复述内容应包括：
   - 当前目标
   - 当前思路
   - 已完成工作
   - 有效做法 / 无效做法
   - 下一步
6. 读取过新的 `dream-notes.md` 后，更新 `last_dream_consumed_at`，避免重复消费。
7. 把记忆文件视为恢复依据，而不是去依赖旧聊天记录。

对应脚本的可见信号：

- `include_dream=yes`：本次恢复读入了新的 `dream-notes.md`
- `include_dream=no`：本次恢复没有新的 dream 需要消费

如果用户只是问一个局部问题，先走“轻量检索”，不要默认完整恢复。

项目级 `AGENTS.md` 可以加入一条辅助规则：

- 如果 `<project>/.codex/session-memory/dream-notes.md` 存在，进入项目上下文或恢复时一并读取

但它只作为补充上下文，不应覆盖 `current.md` 的优先级。

当某个项目第一次成功生成 `dream-notes.md` 后，dream 流程会自动检查 `<project>/AGENTS.md`：

- 若不存在，则创建一个最小 `AGENTS.md` 并写入这条读取规则
- 若已存在且尚未包含这条规则，则自动追加到文件末尾
- 若已包含，则不重复写入

## 保存流程

在出现有意义的状态变化后更新记忆，尤其是：

- 主方案变化
- 某次实验确认有效或无效
- 发现了重要约束
- 一个阻塞被解决
- 会话即将结束

如果不确定现在该不该保存，先运行 `session-memory 检查` / `session-memory check` 对应脚本，再决定。

执行 `session-memory 保存` / `session-memory save` 时，内部流程应是：

1. 先运行 `save --stage prepare`，定位 `current.md/history.md`，必要时初始化。
2. 编辑 `current.md`，并在满足历史追加条件时更新 `history.md`。
3. 编辑完成后运行 `save --stage commit`，把这次保存登记为项目新活动，并触发 `sleep check`。
4. 只记录耐久、可复用的信息，不记录工具噪音、来回讨论、低价值中间输出。

## `current.md` 记录什么

`current.md` 必须尽量高信号，建议包含以下部分：

- `当前目标`：现在到底要完成什么。
- `当前思路`：当前采用的方案，以及为什么采用它。
- `思路变化`：关键方案从什么变成什么，原因是什么。
- `已完成工作`：已经做完、无需重复做的部分。
- `研究记录`：查过什么，得到了什么结论，依据是什么。
- `关键词/标签`：便于后续搜索命中。
- `关键文件与路径`：便于快速找回上下文落点。
- `有效做法`：哪些方案、实验、材料证明有用。
- `无效或放弃的做法`：哪些路线被否掉，以及为什么。
- `未决问题`：还没解决、但确实影响推进的问题。
- `下一步`：新会话接手后应该先做什么。
- `恢复提示`：适合直接交给新会话的短提示。

## 什么时候才写 `history.md`

只有在以下三类“真实状态变化”发生时，才追加到 `history.md`：

- `思路变化`
- `研究结论`
- `下一步变化`

不要因为措辞变化、普通执行过程、零散聊天、或短暂工具输出就写历史。

## 历史追加标准

### 思路变化

指主方案、判断框架或关键假设发生了变化。

应该记录的情况：

- 主路线改了
- 原本偏好的方案被否掉了
- 做判断的依据变了
- 新约束迫使方案变化

不应该记录的情况：

- 只是换了说法，方案没变
- 只是脑暴，没有影响决策
- 只是补充细节，没有改方向

快速判断：
如果新会话需要知道“为什么不再按原方案做”，就应该记录。

### 研究结论

指查阅、比较、测试、验证之后，形成了对后续决策有价值的稳定结论。

应该记录的情况：

- 某个工具、库、方案被确认可用或不可用
- 某个原本不确定的问题被证据解决了
- 一次比较得出了明确选择
- 某项检查改变了后续路线

不应该记录的情况：

- 还只是猜测
- 只是原始输出，没有形成结论
- 这个发现对后续选择没有影响

快速判断：
如果这个结论会改变后续选路，就应该记录。

### 下一步变化

指“接下来先做什么”的优先级、顺序或目标发生了变化。

应该记录的情况：

- 下一项任务变了
- 执行顺序变了
- 优先级变了
- 由于阻塞，下一最佳动作变了

不应该记录的情况：

- 只是很小的操作动作
- 只是“我现在去读一个文件”
- 不会影响新会话如何继续

快速判断：
如果一个新会话接手时会因为这个变化而从不同地方开始，就应该记录。

## 质量要求

- 优先写事实、决策和依据，不写空泛叙述。
- 要保留“为什么变了”，不只保留最终结论。
- 涉及关键文件、命令、路径、Issue、提交时，应写进去。
- 已验证和未验证的信息要区分清楚。
- 不要假装确定。
- `current.md` 必须足够短，能在一次读取中快速恢复状态。
- 搜索友好的关键词要具体，避免只写“这个”“那个方案”。

## 参考文件

- 当前状态模板：`references/current-template.md`
- 历史模板：`references/history-template.md`

## 典型请求

- `session-memory 保存`
- `session-memory save`
- `session-memory 恢复`
- `session-memory restore`
- `session-memory 搜索 stripe webhook`
- `session-memory search stripe webhook`
- `session-memory 检查`
- `session-memory check`
- `session-memory 恢复，并带上新的 dream-notes`
- `session-memory restore with latest dream-notes`
- `把这次会话里真正有用的东西记下来，后面新开会话能接上。`
- `不要总结聊天，帮我记录当前思路、做过什么、哪些路走不通。`
- `新会话先恢复之前的关键记忆，再继续做。`

## 输出约定

使用这个 skill 时，要明确当前是在做哪一类动作：

- 恢复记忆
- 保存记忆
- 初始化记忆文件
- 搜索记忆
- 检查保存时机

如果是在恢复，先给出简短恢复结果，再继续执行用户当前任务。
