# 持久化

持久化分为 Neo4j 和内容寻址文件存储。Neo4j 存储结构化模拟状态和关系。文件存储保存不适合作为大型图属性的媒体和 JSON artifact。

## Neo4j store facade

后端使用 `DatabaseService` 作为类型化 store 类之上的 facade。每个 store 负责图中的一个聚焦区域：

| Store 区域 | 示例 |
| --- | --- |
| 世界和模拟 | Worlds、simulations、当前时间、复制后的世界状态。 |
| 物理状态 | Characters、locations、landmarks、items、equipment、containers、地点和库存关系。 |
| 认知状态 | Memories、intents、relationships、subjective claims、emotions。 |
| 生成状态 | Turns、turn presentation、generation jobs、graph state snapshots、audit records。 |
| 配置 | 供应商连接、模型配置、组件分配、prompt 和 workflow 分配。 |
| 媒体链接 | 媒体记录，以及来自 worlds、simulations、entities、prompts、workflows 和 turns 的关系。 |

## 已提交事实

物理图事实通过 `StateCommitStore.apply_state_commit_proposal()` 应用。面向 LLM 的 committer 会构建 `StateCommitProposal`，但这个 proposal 在 store 应用并记录 turn 之前不是事实。

抽象事实在物理提交之后应用：

- `MemorySummaryStore` 创建或更新事件、记忆和 intents。
- 关系更新使用已提交记忆作为证据。
- 主观断言更新是观察者作用域的私有信念。
- 情绪更新是私有角色状态。

这种分离可以防止叙事直接变成数据库，也防止拟议变更在提交前被当作状态。

## 图状态快照

图状态快照在重要边界附近持久化生成状态：

| 快照类型 | 用途 |
| --- | --- |
| `BEFORE_USER_INPUT` | 恢复用户输入生成之前的基础状态。 |
| `AFTER_USER_INPUT` | 保留用户输入处理之后的状态。 |
| `AFTER_CHARACTER_ROUND` | 为继续生成和重新生成提供基准。 |

快照不是图的替代品。它们捕获模拟器的执行状态，使后续继续生成或重新生成可以从已知的结构化边界恢复。

## 回合呈现

Turns 是发生了什么以及何时发生的规范记录。`TurnPresentationRendering` 单独存储显示块：

- 叙事；
- 对白；
- 动作文本；
- 生成音频引用；
- 生成图像引用。

这允许前端渲染或重新生成呈现，而不重写 turn 背后的事实。

## 媒体存储

`StorageService` 把二进制和 JSON 内容存储在内容寻址文件夹中。Neo4j 存储元数据和链接，不存储原始文件。这用于生成图像、上传封面媒体、语音文件、prompt JSON 和 workflow JSON。

