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
- `session-memory 研究保存` / `session-memory research-save`：把未并入主线的研究阶段性追加到 `research.md`，不覆盖 `current.md`。
- `session-memory 恢复` / `session-memory restore`：恢复当前项目的记忆，先读 `current.md`，必要时再读 `history.md`，并且只在有未消费 dream 时才读取 `dream-notes.md`。
- `session-memory 搜索 <关键词>` / `session-memory search <keyword>`：在当前项目的记忆中查旧结论、旧路径、旧决策。
- `session-memory 检查` / `session-memory check`：判断现在是否到了应该保存的时机。

对应脚本入口：

- 保存准备/提交：`scripts/save_session_memory.py --stage prepare|commit`
- 研究保存准备/提交：`scripts/research_save_session_memory.py --stage prepare|commit`
- 恢复：`scripts/restore_session_memory.py`
- 搜索：`scripts/search_session_memory.py`，默认只查热层；明确要求查研究时再加 `--include-research`，明确要求查归档时再加 `--include-archive`
- 检查：`scripts/checkpoint_session_memory.py`
- 归档：`scripts/archive_session_memory.py`

如果项目记忆文件还不存在，`保存 / save` 和 `研究保存 / research-save` 的 `prepare` 阶段都应先初始化。

默认使用中文记录。只有代码、命令、路径、API 名、库名、固定技术标识等内容保留原文。

## 存储规则

默认优先使用项目级记忆，避免不同项目互相污染：

- `<git-root>/.codex/session-memory/current.md`：当前最新状态，作为恢复入口。
- `<git-root>/.codex/session-memory/history.md`：追加式历史，只记录关键变化。
- `<git-root>/.codex/session-memory/research.md`：研究流水账，面向同项目多个工作上下文的追加式研究记录。

默认恢复入口只看 `current.md`、`history.md`、`dream-notes.md`。`research.md` 是研究层，不进入默认恢复/检索热路径，只有用户明确要求“查研究”“恢复某条研究上下文”时才读取。

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
2. 更新当前项目的 `last_seen_at`
3. 只有 `save --stage commit` 才更新当前项目的 `last_active_at`
4. 检查距离上次 `sleep check` 是否超过 5 小时
5. 若超过，再判断是否存在需要 dream 的项目
6. 若需要且当前没有运行中的 dream，则后台异步启动一次 dream

这样做的原因是：单纯 `restore/search/check` 不应把项目重新标成“发生了新内容变化”，否则会造成重复 dream 和无意义快照增长。

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

只有当用户明确要求“查归档”时，才追加：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/search_session_memory.py" --workspace "$PWD" --scope auto --query "关键词" --include-archive
```

只有当用户明确要求“查研究”时，才追加：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/search_session_memory.py" --workspace "$PWD" --scope auto --query "关键词" --include-research
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

这里要区分三层：

- `<project>/.codex/session-memory/dream-notes.md` 是覆盖式文件，每次 dream 会重写最新提炼稿，不会无限追加。
- `<project>/.codex/session-memory/history.md` 是追加式文件，会随着关键变化持续变长。
- `<project>/.codex/session-memory/research.md` 是追加式研究层，会在 dream 提炼时参与归纳，但不进入默认恢复入口。
- `${CODEX_HOME:-$HOME/.codex}/session-memory/dreams/` 会按每次成功 dream 的快照数量持续增加，但会在后续 dream 成功后做冷层归档。
- `<project>/.codex/session-memory/archive/` 与 `${CODEX_HOME:-$HOME/.codex}/session-memory/archive/` 是冷层，只做兜底保留，不进入默认恢复/检索路径。

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

## 归档策略

归档必须放在 dream 之后，而不是和热层并列长期参与默认读取。也就是说：先提炼，再瘦身。

如果项目已经持续较久，建议归档“旧历史”和“旧快照”，但不要归档当前活跃层：

- 不要归档：`current.md`、最新 `dream-notes.md`、活跃项目的 `registry/state` 元数据
- 可以归档：`history.md` 的旧条目、`${CODEX_HOME:-$HOME/.codex}/session-memory/dreams/` 里的旧快照、`research.md` 中已并入主线或已判定无效的旧研究条目

默认命令：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/session-memory/scripts/archive_session_memory.py" --workspace "$PWD" --scope auto --dry-run
```

默认行为：

- 只有在存在“新 dream 尚未归档”的前提下，才允许继续做项目历史瘦身
- 保留 `history.md` 最新若干条，把更早的条目移到 `archive/history-archive.md`
- 把 `research.md` 中 `是否并入主线=yes` 或 `是否有效=no` 的研究条目移到 `archive/research-archive.md`
- 保留近一段时间的全局 dream 快照，把更老的快照移到 `${CODEX_HOME:-$HOME/.codex}/session-memory/archive/dreams/`
- 默认 `restore/search` 不读取 `archive`；只有用户明确要求查看归档时，才显式带 `--include-archive`

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

如果当前内容还没有进入主线，不要直接覆盖 `current.md`，优先改走 `研究保存`：

1. 先运行 `research-save --stage prepare`，定位 `research.md`，必要时初始化。
2. 用 `research-save --stage commit` 追加一条研究记录，至少带上 `工作上下文 / 研究主题 / 当前结论 / 是否有效 / 是否并入主线 / 下一步`。
3. 同一工作上下文允许多次 `研究保存`，每次都只追加，不回写旧条目。
4. 只有当某条研究已经成为默认方向时，才把它并入 `current.md` 或 `history.md`。

`current.md` 里的 `分支研究` 表格可以保留高层摘要，但不应该再承担多阶段研究流水账的职责；详细研究过程默认写入 `research.md`。

## `current.md` 记录什么

`current.md` 必须尽量高信号，建议包含以下部分：

- `当前目标`：现在到底要完成什么。
- `当前思路`：当前采用的方案，以及为什么采用它。
- `思路变化`：关键方案从什么变成什么，原因是什么。
- `已完成工作`：已经做完、无需重复做的部分。
- `研究记录`：查过什么，得到了什么结论，依据是什么。
- `分支研究`：记录未进入主线、但值得保留的研究路径。每行至少带上 `日期 / 工作上下文 / 分支研究 / 研究主题 / 当前结论 / 是否有效 / 是否并入主线 / 下一步`。
- `工作上下文`：写当前研究发生在哪个工作副本或 Git 分支里，例如 `main`、`main-local`、`feature-auth`。
- `分支研究`（字段）：写这条研究路径的短名，例如 `stl`、`signature-fix`、`queue-vs-cron`。
- `关键词/标签`：便于后续搜索命中。
- `关键文件与路径`：便于快速找回上下文落点。
- `有效做法`：哪些方案、实验、材料证明有用。
- `无效或放弃的做法`：哪些路线被否掉，以及为什么。
- `未决问题`：还没解决、但确实影响推进的问题。
- `下一步`：新会话接手后应该先做什么。
- `恢复提示`：适合直接交给新会话的短提示。

## `research.md` 记录什么

`research.md` 是研究层，不是主线层。最小版只做追加记录，不承担主线恢复入口职责。

- 每次研究保存只追加一条，不回写主线 `current.md`
- 每条记录至少带：`时间 / 工作上下文 / 研究主题 / 当前结论 / 是否有效 / 是否并入主线 / 下一步`
- `工作上下文` 用来区分同项目下不同 fork、worktree 或实验副本
- 同一 `工作上下文` 允许多次 `研究保存`，每次都视为新的阶段性 checkpoint，不覆盖之前的研究条目
- 研究真正进入主线后，再把结果并入 `current.md` 或 `history.md`
- 默认 `restore/search` 不读取 `research.md`；只有明确要求查看研究层时，才显式带 `--include-research`

## 什么时候才写 `history.md`

只有在以下三类“真实状态变化”发生时，才追加到 `history.md`：

- `思路变化`
- `研究结论`
- `下一步变化`

不要因为措辞变化、普通执行过程、零散聊天、或短暂工具输出就写历史。

如果更新属于某条分支研究，条目标题建议写成：

```md
### YYYY-MM-DD HH:MM [context: main-local]
```

并补充：

- `工作上下文`：`main / main-local / feature-xxx`
- `分支研究`：这条研究路径的短名
- `研究主题`：当前在验证什么
- `研究结果`：这次更新确认了什么
- `是否有效`：`yes / no / partial / unknown`
- `是否并入主线`：`yes / no`

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
- `把这个 local fork 的研究结果增量记下来，但不要覆盖主线`
- `记录这条 feature 分支的研究结论，并标明工作上下文是 feature-auth`
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
