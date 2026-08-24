# 事件、回合与动作

## 目的

Turns 记录有序对话和模拟执行。Events 把一个或多个 turns 组合成有意义的发生事项。Intents 表示角色目标和计划，可能由 events 创建或影响。Triggers 是驱动脚本化剧情推进的隐藏条件-效果规则。Generation jobs、graph snapshots、audit events 和 presentation blocks 支持异步执行、检查和面向用户的输出。Turn version 和 world state checkpoint 让重新生成或回退一个 turn 时不至于丢掉它留下的世界状态。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Turn` | `id`, `sequence`, `type`, `content`, `start_time` |
| `TurnPresentationBlock` | `id`, `turn_id`, `rendering_id`, `locale`, `sequence`, `type`, `text`, `speaker_id`, `speaker_name`, `media_id`, `voice_media_id`, `completion`, timestamps |
| `Event` | `id`, `name`, `summary` |
| `Intent` | `id`, `type`, `name`, `description`, `keywords`, `embedding`, `priority`, `urgency`, `status`, planning 和 condition fields |
| `Trigger` | `id`, `source_id`, `name`, `description`, `condition`, `effect_kind`, `effects`, `gate_effect`, `chance`, `repeatable`, `cooldown_turns`, `reversible`, `status`, `last_condition_result`, `last_fired_turn_id`, `last_evaluated_turn_id` |
| `TriggerActivation` | `id`, `trigger_id`, `simulation_id`, `fired_at_turn_id`, `effect`, `consumed`, `consumed_at_turn_id` |
| `GenerationJob` | `id`, `simulation_id`, `request_type`, `status`, `stage`, timestamps, `error`, `final_turn_id` |
| `GraphStateSnapshot` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, `state`, `created_at` |
| `TurnVersion` | `id`, `simulation_id`, `turn_sequence`, `turn`, `presentation_blocks`, `user_input`, `checkpoint_id`, `created_at` |
| `WorldStateCheckpoint` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, 按实体类型分组的捕获列表（`characters`、`items`、`entity_relationships`、`memories` 等）, `created_at` |
| `SimulationAuditEvent` | `id`, `simulation_id`, `run_id`, `turn_id`, `category`, `origin`, `status`, `stage`, `summary`, actor 和 entity ids, `details`, timestamps |

## 关系

- `(:World|Simulation)-[:CONTAINS]->(:Turn)`
- `(:Turn)-[:NEXT]->(:Turn)`
- `(:Turn)-[:PART_OF]->(:Event)`
- `(:Event)-[:INVOLVES]->(:Character)`
- `(:Event)-[:CREATES]->(:Intent)`
- `(:Event)-[:CONTRIBUTES_TO]->(:Intent)`
- `(:Character)-[:HOLDS]->(:Intent)`
- `(:Turn)-[:PROPOSED_STATE_CHANGE]->(:Character|Location|ItemStack|Equipment|Container|...)`
- `(:Turn)-[:HAS_PRESENTATION]->(:TurnPresentationBlock)`
- `(:World|Simulation)-[:CONTAINS]->(:Trigger)`
- `(:Trigger)-[:FIRED]->(:TriggerActivation)`
- `(:Simulation)-[:CONTAINS]->(:TriggerActivation)`
- `(:Simulation)-[:HAS_GENERATION_JOB]->(:GenerationJob)`
- `(:Simulation)-[:HAS_GRAPH_STATE_SNAPSHOT]->(:GraphStateSnapshot)`
- `(:Simulation)-[:HAS_TURN_VERSION]->(:TurnVersion)`
- `(:Simulation)-[:HAS_STATE_CHECKPOINT]->(:WorldStateCheckpoint)`
- `(:Simulation|GenerationJob|Turn)-[:HAS_AUDIT_EVENT]->(:SimulationAuditEvent)`

## Trigger 与剧情推进

`Trigger` 是一个隐藏的条件-效果规则，作者在 `World` 上创建，随后被复制到基于该 world 创建的每个 `Simulation` 中，
并在各个 simulation 副本里独立评估。它的 `condition` 可以是时间、地点、变量、语义陈述，或确定性条件的布尔组合；
确定性条件在每个 turn 由代码直接检查，语义条件则由 `SemanticTriggerEvaluator` 这个 LLM 组件根据最近的叙事和记忆来
判断。`effect_kind` 决定了它的形态：`EVENT` 只触发一次（可选带 `chance` 概率判定，也可以设为 `repeatable` 并配合
`cooldown_turns`），触发后最多把 3 个 effect 排入队列，成为一条 `TriggerActivation`；`GATE` 则用于追踪一个可选
`reversible` 的开/关许可状态。

这里最核心的设计约束是：一个休眠中的 trigger，它自身的存在和内容——`name`、`description`、`effects`、
`gate_effect`——绝不能进入任何 LLM prompt。唯一允许出现在 prompt 中的 trigger 相关内容，是 `SemanticCondition` 自
身的 `statement`（喂给 evaluator），以及一次*已触发*的 `EVENT` effect 的 payload——通过 `TriggerActivation` 只注
入真正需要它的那一个 prompt，且只在被 `consumed` 之前有效。

作者和用户也可以间接创建、重新定义、启用/禁用或删除 trigger：`OOCHandler` 可以把一条 out-of-character 指令转成
`trigger_directive`（`create`/`update`/`set_status`/`delete`），并走与作者态 trigger 相同的存储路径应用。

## Turn 版本与状态检查点

重新生成一个 turn（「swipe」）或回退到某个被丢弃的 turn，不能只改显示的文字，还得把世界状态也还原回去。
`WorldStateCheckpoint` 捕获的是模拟已持久化的实体图（不是 `GraphStateSnapshot` 保存的那种临时 LangGraph 状态），
捕获点分四种：`BEFORE_USER_INPUT`、`AFTER_USER_INPUT`、`AFTER_CHARACTER_ROUND`（与 `GraphStateSnapshotType` 一一
对应），以及 `BEFORE_OOC_MUTATION`——在一次 OOC 强制世界状态变更提交之前捕获，目前还没有对应的恢复路径，是为将来
「撤销上一条 OOC 指令」预留的。

`TurnVersion` 会在某个 turn 槽位即将被重新生成或回退替换掉的那一刻，把它当前的内容归档下来——包括这个 turn 本身、
它的 presentation blocks、产出它的 user input，以及指向紧随其后那次 checkpoint 的指针。回退和重新生成是对称的：
会先把当前生效的内容归档（所以回退之后还能再回退一次），然后恢复目标版本的内容，如果它对应的 checkpoint 还没被
清理，也会一并恢复对应的世界状态。

这两个模型一旦故事真的向前推进，都会被积极清理：保存新的 `BEFORE_USER_INPUT` checkpoint 时会先删掉该模拟的所有
其他 checkpoint；一旦真正开始一次 user-input 生成，该模拟下所有归档的 `TurnVersion` 也会被删除。归档备份只能在
当前这一轮 turn 周期内浏览和回退。完整的重新生成/回退流程和 checkpoint 恢复顺序，见
[Turn 版本与状态检查点](../features/turn-versioning.md)。

## 归属与生命周期

Turns 由 world 或 simulation 拥有，并通过 `sequence` 和 `NEXT` 排序。运行时 simulation turns 是 append-only history。Events 从 turns 连接出来，然后支持 memories 和 intent changes。

Proposed state 本身不是事实。Turn 可以用 `PROPOSED_STATE_CHANGE` 记录 proposed changes，但只有 state committer 把 properties 和 relationships 写入受影响实体后，图才成为已提交事实。

## 创建与删除行为

创建 turn 会把它分配到 source，并链接到 previous turn 之后。创建 event 会用 `PART_OF` 连接所选 turn 或 turns。Presentation rendering 会先替换特定 turn/rendering pair 的 blocks，再写入新的有序 block 集合。

删除 event 会移除 turns 上的 event links；如果不再被引用，则删除 event。删除 simulation 会沿 `CONTAINS`/`HOLDS`/
`PART_OF`/`HAS_GRAPH_STATE_SNAPSHOT`/`HAS_GENERATION_JOB` 这几条关系从 simulation 节点往下走，把 turns、jobs 和
graph state snapshots 随运行时图一起删除。`HAS_TURN_VERSION`、`HAS_STATE_CHECKPOINT` 和 `HAS_AUDIT_EVENT` 目前不
在这条删除路径里，所以删除 simulation 时，`TurnVersion`、`WorldStateCheckpoint` 和 `SimulationAuditEvent` 节点会
变成孤立节点，留在图里。

## 不变量

- Turn `sequence` 在一个 world 或 simulation source 内应唯一。
- `NEXT` 应与 turn sequence 顺序一致。
- Presentation block sequences 在一个 rendering 内必须唯一且连续。
- Media presentation blocks 需要 `media_id`；非 media blocks 需要 text。
- Speech blocks 需要 `speaker_id` 或 `speaker_name`。
- `updated_at` 不能早于 `created_at`。
- 一个 simulation 同一时刻最多只有一个 `BEFORE_USER_INPUT` checkpoint；`AFTER_USER_INPUT` 和
  `AFTER_CHARACTER_ROUND` checkpoint 按 `turn_sequence` 区分，每个 turn 槽位各有一份。
- 如果 simulation 已经有一次生成在运行，回退到某个 `TurnVersion` 的请求会被拒绝。

## 示例 Cypher 表示

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (mira:Character {id: "char-1"})
CREATE (turn:Turn {
  id: "turn-7",
  sequence: 7,
  type: "user_input",
  content: "Mira opens the crate.",
  start_time: datetime("1894-04-16T08:05:00Z")
})
CREATE (event:Event {
  id: "event-3",
  name: "Crate opened",
  summary: "Mira opens the supply crate by the pier."
})
CREATE (block:TurnPresentationBlock {
  id: "block-1",
  turn_id: "turn-7",
  rendering_id: "default",
  sequence: 0,
  type: "narration",
  text: "The brass key turns, and the crate lid lifts.",
  completion: "complete"
})
CREATE (simulation)-[:CONTAINS]->(turn)
CREATE (turn)-[:PART_OF]->(event)
CREATE (event)-[:INVOLVES]->(mira)
CREATE (turn)-[:HAS_PRESENTATION]->(block)
CREATE (simulation)-[:CONTAINS]->(block);
```

## 相关 API 端点

- `/turns`, `/turns/{turn_id}`, `/worlds/{world_id}/turns`, `/simulations/{simulation_id}/turns/{sequence}`
- `/turn-presentations`, `/turns/{turn_id}/presentation`
- `/events`, `/events/{event_id}`, `/events/{event_id}/turns`, `/events/{event_id}/characters`
- `/intents`, `/intents/{intent_id}`, `/characters/{character_id}/intents`, `/intents/{intent_id}/character`, `/intents/{intent_id}/created-by`, `/intents/{intent_id}/contributing-events`
- `/triggers`, `/triggers/{trigger_id}`, `/triggers/{trigger_id}/status`
- `/simulations/{simulation_id}/input`, `/simulations/{simulation_id}/runs/{thread_id}`
- `/simulations/{simulation_id}/graph-snapshots`
- `/simulations/{simulation_id}/turn-versions`, `/simulations/{simulation_id}/turn-versions/{version_id}/revert`

