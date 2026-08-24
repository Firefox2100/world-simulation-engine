# 记忆与主观断言

## 目的

Memories 和 claims 建模角色视角。`MemoryAtom` 节点存储带 keywords 和 embeddings 的紧凑回忆。`SubjectiveEntityClaim` 节点存储某个角色对另一个实体的看法，包括 confidence 和 evidence links。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `MemoryAtom` | `id`, `summary`, `keywords`, `embedding` |
| `REMEMBERS` relationship | confidence, salience, behavioral relevance, stance metadata |
| `SubjectiveEntityClaim` | `id`, `simulation_id`, `observer_character_id`, `subject`, `category`, `statement`, `normalized_statement`, `stance`, `confidence`, supporting 和 contradicting memory ids, timestamps, `version`, `active` |
| `SubjectiveClaimChangeAudit` | `id`, `claim_id`, `simulation_id`, `turn_id`, `observer_character_id`, `change_type`, evidence memory ids, timestamps |

## 关系

- `(:Event)-[:SUPPORTS]->(:MemoryAtom)`
- `(:Character)-[:REMEMBERS]->(:MemoryAtom)`
- `(:Character)-[:HOLDS_MODEL]->(:SubjectiveEntityClaim)`
- `(:SubjectiveEntityClaim)-[:ABOUT]->(:Character|BackgroundCharacter|Location|Landmark|Item|ItemStack|Equipment|Container|...)`
- `(:MemoryAtom)-[:CLAIM_EVIDENCE]->(:SubjectiveEntityClaim)`
- `(:Simulation)-[:CONTAINS]->(:SubjectiveEntityClaim)`
- `(:Simulation)-[:CONTAINS]->(:SubjectiveClaimChangeAudit)`
- `(:Turn)-[:TRIGGERED]->(:SubjectiveClaimChangeAudit)`
- `(:SubjectiveClaimChangeAudit)-[:CHANGED]->(:SubjectiveEntityClaim)`

## 归属与生命周期

Memories 由 events 产生，然后附着到记住它们的 characters。一个 memory 可以被多个 characters 共享，但每条 `REMEMBERS` relationship 可以携带角色特定的 relevance。

Subjective claims 属于一个 simulation 和一个 observer character。它们从该 observer 的视角描述 subject entity，并会随着 simulator proposals 和 state commits 不断修订。

## 创建与删除行为

创建 memory 会用 `SUPPORTS` 把它连接到 event，并用 `REMEMBERS` 连接到一个或多个 characters。重新分配 memory characters 会替换现有 remembered links。删除 memory 会移除 memory node 和它的 evidence links。

创建 subjective claim 会校验 observer 属于 simulation，并校验 subject 在 simulation 或继承的 world graph 中可见。作为 turn 的一部分变更 claim 时，会创建 audit nodes。

## 不变量

- Subjective claim observer 不能和 subject 是同一实体。
- Supporting 和 contradicting memory ids 会去重，且不能重叠。
- Claim 的 evidence memories 必须被 observer 记住。
- `normalized_statement` 应足够稳定，以支持重复检测和矛盾检查。
- 当历史需要可解释性时，claims 可以变为 inactive，而不是物理删除。

## 示例 Cypher 表示

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (turn:Turn {id: "turn-7"})
MATCH (mira:Character {id: "char-1"})
MATCH (crate:Container {id: "container-1"})
MATCH (event:Event {id: "event-3"})
CREATE (memory:MemoryAtom {
  id: "memory-1",
  summary: "Mira opened the locked crate with the brass key.",
  keywords: ["crate", "key", "opened"]
})
CREATE (claim:SubjectiveEntityClaim {
  id: "claim-1",
  simulation_id: "sim-1",
  observer_character_id: "char-1",
  category: "state",
  statement: "The crate can be opened with the brass key.",
  normalized_statement: "crate unlocks with brass key",
  stance: "believes",
  confidence: 0.91,
  active: true,
  version: 1
})
CREATE (event)-[:SUPPORTS]->(memory)
CREATE (mira)-[:REMEMBERS {salience: 0.8, confidence: 0.95}]->(memory)
CREATE (simulation)-[:CONTAINS]->(claim)
CREATE (mira)-[:HOLDS_MODEL]->(claim)
CREATE (claim)-[:ABOUT]->(crate)
CREATE (memory)-[:CLAIM_EVIDENCE]->(claim);
```

## 相关 API 端点

- `/memories`, `/memories/{memory_id}`
- `/memories/{memory_id}/event`
- `/memories/{memory_id}/characters`
- `/events/{event_id}/turns`, `/events/{event_id}/characters`
- `/simulations/{simulation_id}/input` 用于 turn 中由 simulator 驱动的 memory 和 claim updates

Subjective claims 主要由模拟流水线和底层 stores 维护。目前不像 memories 那样暴露宽泛的公共 CRUD router。

