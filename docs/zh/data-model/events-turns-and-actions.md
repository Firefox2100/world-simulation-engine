# 事件、回合与动作

## 目的

Turns 记录有序对话和模拟执行。Events 把一个或多个 turns 组合成有意义的发生事项。Intents 表示角色目标和计划，可能由 events 创建或影响。Generation jobs、graph snapshots、audit events 和 presentation blocks 支持异步执行、检查和面向用户的输出。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Turn` | `id`, `sequence`, `type`, `content`, `start_time` |
| `TurnPresentationBlock` | `id`, `turn_id`, `rendering_id`, `locale`, `sequence`, `type`, `text`, `speaker_id`, `speaker_name`, `media_id`, `voice_media_id`, `completion`, timestamps |
| `Event` | `id`, `name`, `summary` |
| `Intent` | `id`, `type`, `name`, `description`, `keywords`, `embedding`, `priority`, `urgency`, `status`, planning 和 condition fields |
| `GenerationJob` | `id`, `simulation_id`, `request_type`, `status`, `stage`, timestamps, `error`, `final_turn_id` |
| `GraphStateSnapshot` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, `state`, `created_at` |
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
- `(:Simulation)-[:HAS_GENERATION_JOB]->(:GenerationJob)`
- `(:Simulation)-[:HAS_GRAPH_STATE_SNAPSHOT]->(:GraphStateSnapshot)`
- `(:Simulation|GenerationJob|Turn)-[:HAS_AUDIT_EVENT]->(:SimulationAuditEvent)`

## 归属与生命周期

Turns 由 world 或 simulation 拥有，并通过 `sequence` 和 `NEXT` 排序。运行时 simulation turns 是 append-only history。Events 从 turns 连接出来，然后支持 memories 和 intent changes。

Proposed state 本身不是事实。Turn 可以用 `PROPOSED_STATE_CHANGE` 记录 proposed changes，但只有 state committer 把 properties 和 relationships 写入受影响实体后，图才成为已提交事实。

## 创建与删除行为

创建 turn 会把它分配到 source，并链接到 previous turn 之后。创建 event 会用 `PART_OF` 连接所选 turn 或 turns。Presentation rendering 会先替换特定 turn/rendering pair 的 blocks，再写入新的有序 block 集合。

删除 event 会移除 turns 上的 event links；如果不再被引用，则删除 event。删除 simulation 会随运行时图一起删除 turns、jobs、snapshots 和 contained audit nodes。

## 不变量

- Turn `sequence` 在一个 world 或 simulation source 内应唯一。
- `NEXT` 应与 turn sequence 顺序一致。
- Presentation block sequences 在一个 rendering 内必须唯一且连续。
- Media presentation blocks 需要 `media_id`；非 media blocks 需要 text。
- Speech blocks 需要 `speaker_id` 或 `speaker_name`。
- `updated_at` 不能早于 `created_at`。

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
- `/simulations/{simulation_id}/input`, `/simulations/{simulation_id}/runs/{thread_id}`
- `/simulations/{simulation_id}/graph-snapshots`

