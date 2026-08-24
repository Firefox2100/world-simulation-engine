# Turn 版本与状态检查点

在聊天类 UI 里，重新生成一个 turn（也就是「swipe」）很常见，但这里不能只是重新叙事了事。被丢弃的 turn 可能已经改变了世界——物品被挪动、关系发生变化、时钟往前走了——这些效果也必须一并撤销，否则世界状态会和最终留下的那个 turn 对不上。有两个模型让重新生成和回退能够安全进行：

| 模型 | 用途 |
| --- | --- |
| `TurnVersion` | 某个 turn 槽位（具体到一个 `turn_sequence`）的归档备份，在该槽位的当前 turn 即将被重新生成或回退替换之前捕获。 |
| `WorldStateCheckpoint` | 模拟*已持久化*实体图在某个保存点的完整快照，让恢复一个 turn 时也能把对应的世界状态一起恢复。 |

## 为什么不直接用 `GraphStateSnapshot`？

`GraphStateSnapshot` 本来就用于恢复 LangGraph 运行，支持续写或重新生成，但它只捕获这次运行的临时提案状态，并不是已经写入 Neo4j 的内容。`WorldStateCheckpoint` 捕获的是真正已持久化的实体：角色、背景角色、物品、item stack、装备、容器、variable set、entity relationship、情绪状态、subjective claim、记忆和事件。两者在同样的保存点成对出现，但只有 checkpoint 才足以把图本身还原回去。

## Checkpoint 的捕获边界

`WorldStateCheckpointType` 的取值：

| 类型 | 捕获时机 | 用途 |
| --- | --- | --- |
| `BEFORE_USER_INPUT` | 新一轮 user-input 生成开始之前。 | 重新生成即将产出的那个 turn 时的恢复点。 |
| `AFTER_USER_INPUT` | user input 处理提交之后。 | 该次 user input 产出 turn 的恢复点。 |
| `AFTER_CHARACTER_ROUND` | 离场/continuation 角色回合提交之后。 | continuation turn 的恢复点。 |
| `BEFORE_OOC_MUTATION` | OOC 强制世界状态变更提交之前。 | 没有对应的 `GraphStateSnapshot`——OOC 变更并没有 LangGraph 提案状态可以回滚。目前只捕获、不恢复，是为将来「撤销上一条 OOC 指令」预先埋下的数据。 |

前三种在取值上和 `GraphStateSnapshotType` 一一对应，在 `WorldSimulator` 里于相同的时间点捕获。

## 重新生成一个 turn（「swipe」）

针对某个 `turn_sequence` 发起 `REGENERATION` 请求时：

1. 把该槽位当前的 turn 归档为一条 `TurnVersion`——包括它的内容、presentation block、产出它的 user input，以及指向它之后那次 checkpoint 的指针。
2. 恢复该槽位之前（`turn_sequence - 1`）的 `WorldStateCheckpoint`，撤销被丢弃 turn 已经提交的世界状态影响。
3. 针对同一个槽位重新执行一次生成，产出新的 turn。

## 回退到某个归档版本

回退不只是取出数据，而是与重新生成对称的操作：

1. 先把该槽位当前生效的 turn 归档——这样回退永远不会销毁用户之后可能还想回来的分支，而且回退之后还能再回退。
2. 删除目标槽位之后的所有 turn。
3. 恢复归档版本的 turn/presentation 内容。
4. 恢复该版本对应的 `WorldStateCheckpoint`，前提是它还没被清理（见下面的保留策略）；否则退化为只恢复 turn/presentation 内容，不恢复世界状态。

如果模拟当前已经有一次生成在运行，回退请求会被拒绝，以免在生成过程中把状态从其脚下换掉。

## 保留策略：归档备份不会无限堆积

这两个模型一旦故事真的向前推进，就会被积极清理，不会让废弃分支越堆越多：

- 保存新的 `BEFORE_USER_INPUT` checkpoint 时，会先删除该模拟的所有其他 checkpoint——同一时刻只存在当前这一轮 turn 周期的 checkpoint。
- 一旦真正开始一次 user-input 生成，该模拟下所有归档的 `TurnVersion` 都会被删除。每个槽位最终留下的那个版本才是真正生效的；其他 swipe 出来的版本就此不可达，会被丢弃而不是永久保留。

也就是说，归档备份只能在当前这一轮 turn 周期内浏览和回退——要在发送下一条真正的消息之前完成 swipe，之后就来不及了。

## 恢复一个 checkpoint

`SimulationStateCheckpointService.restore` 始终按照相同的三个阶段应用 checkpoint，而且不会按实体类型交叉进行，避免恢复到一半就把图留在一个谁都没捕获过的中间状态：

1. 按依赖顺序创建缺失实体、强制覆盖已存在实体（引用另一个实体的实体，只在被引用实体已存在或已恢复之后才创建）。
2. 为每个被捕获的角色、item stack、装备和容器重新挂载归属关系（owner、holder、location、landmark、equipped），无论它是新建的还是被覆盖的。
3. 从叶子到根，删除多出来的实体——即现在存在但 checkpoint 里没有的实体。这一步放在第 2 步之后，是为了不让级联删除误伤刚刚重新挂载、值得保留的实体。

## OOC 变更也会捕获一次 checkpoint

出戏指令可以直接强制产生世界状态变更（`OOCHandler` 的相关内容见[多智能体流程](multi-agent-flow.md)），包括创建、更新或禁用某个
[`Trigger`](../data-model/events-turns-and-actions.md#trigger-与剧情推进)。每一次 OOC 强制变更提交前，都会先捕获一次 `BEFORE_OOC_MUTATION` checkpoint——用的是和 turn 重新生成同一套捕获机制，但目前还没有配套的恢复路径。这样做是为了让将来「撤销我上一条 OOC 指令」这个功能不需要再造一套捕获机制，数据已经现成。

## API 与前端

- `GET /simulations/{simulation_id}/turn-versions?turn_sequence={n}`——列出某个 turn 槽位的归档版本，按时间倒序。
- `POST /simulations/{simulation_id}/turn-versions/{version_id}/revert`——回退到某个归档版本。
- `POST /simulations/{simulation_id}/input`，携带 `request_type: regeneration` 并设置 `regenerate_turn_sequence`——重新生成某个 turn 槽位。

`SimulationChatPage` 的 swipe 控件正是通过这几个端点，让用户既能生成新的备选内容，也能回看并拾回之前被丢弃的重新生成结果。
