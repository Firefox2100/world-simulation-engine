# 关系与情绪

## 目的

Relationships 和 emotions 让社交与情感状态在图中显式化。`EntityRelationship` 节点描述实体之间带类型的关系，可带 private visibility 和 evidence。`EmotionState` 节点存储角色的 baseline 与 immediate emotion vectors。Audit nodes 解释关系或情绪状态为什么变化。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `EntityRelationship` | `id`, `scope_type`, `scope_id`, `source`, `target`, `label`, `public_description`, `private_description`, `visibility`, `perspective_character_id`, `confidence`, `details`, evidence memory ids, timestamps, `version`, `active` |
| `EmotionState` | `id`, `simulation_id`, `character_id`, `baseline`, `immediate`, half-life seconds, `last_updated_at`, `version` |
| `EmotionVector` value | `valence`, `arousal`, `dominance`, free-form dimensions |
| `RelationshipChangeAudit` | relationship id, turn id, perspective character id, evidence memory ids, timestamps |
| `EmotionChangeAudit` | emotion state id, turn id, evidence memory ids, caused-by events |

## 关系

- `(:World|Simulation)-[:CONTAINS]->(:EntityRelationship)`
- `(:Entity)-[:RELATIONSHIP_SOURCE]->(:EntityRelationship)`
- `(:EntityRelationship)-[:RELATIONSHIP_TARGET]->(:Entity)`
- `(:MemoryAtom)-[:EVIDENCE_FOR]->(:EntityRelationship)`
- `(:Simulation)-[:CONTAINS]->(:EmotionState)`
- `(:Character)-[:HAS_EMOTION_STATE]->(:EmotionState)`
- `(:Turn)-[:TRIGGERED]->(:RelationshipChangeAudit|EmotionChangeAudit)`
- `(:RelationshipChangeAudit)-[:CHANGED]->(:EntityRelationship)`
- `(:EmotionChangeAudit)-[:CHANGED]->(:EmotionState)`
- `(:MemoryAtom)-[:EVIDENCE_FOR]->(:RelationshipChangeAudit|EmotionChangeAudit)`
- `(:Event)-[:CAUSED_EMOTION_CHANGE]->(:EmotionChangeAudit)`

## 归属与生命周期

Relationships 以 world 或 simulation 为作用域。World-scoped relationships 是作者态背景事实。Simulation-scoped relationships 是运行时事实，可以引用继承的 world entities 或 simulation entities。

Emotion state 属于 simulation scope，由 character 拥有。随着 turns 不断产出新的 events 和 memories，情绪状态也会随之变化。Baseline vector 表示更慢变化的情感倾向；immediate vector 表示短期反应。

## 创建与删除行为

创建 entity relationship 会校验 source、target、scope、visibility、perspective 和 evidence。更新 evidence 会替换之前的 `EVIDENCE_FOR` links。显式删除会 detach 并删除 relationship node。

Emotion state 会按需要为 simulation character 创建。Emotion deltas 会创建带 turn、event 和 memory evidence 的 `EmotionChangeAudit` 节点，然后更新 state vector 和 version。

## 不变量

- Relationship source 和 target 必须是不同实体。
- Private relationships 需要 `perspective_character_id`。
- `private_description` 需要 perspective character。
- Interpersonal relationship detail 应连接 character endpoints。
- Evidence memory ids 会去重。
- Emotion audit evidence 必须被受影响角色记住，并由 simulation 中的 events 支持。

## 示例 Cypher 表示

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (mira:Character {id: "char-1"})
MATCH (dockmaster:Character {id: "char-2"})
MATCH (memory:MemoryAtom {id: "memory-1"})
CREATE (relationship:EntityRelationship {
  id: "rel-1",
  scope_type: "simulation",
  scope_id: "sim-1",
  label: "trusts",
  visibility: "private",
  perspective_character_id: "char-1",
  confidence: 0.74,
  private_description: "Mira thinks the dockmaster is hiding useful information.",
  active: true,
  version: 1
})
CREATE (emotion:EmotionState {
  id: "emotion-1",
  simulation_id: "sim-1",
  character_id: "char-1",
  baseline_half_life_seconds: 86400,
  immediate_half_life_seconds: 900,
  version: 1
})
CREATE (simulation)-[:CONTAINS]->(relationship)
CREATE (mira)-[:RELATIONSHIP_SOURCE]->(relationship)
CREATE (relationship)-[:RELATIONSHIP_TARGET]->(dockmaster)
CREATE (memory)-[:EVIDENCE_FOR]->(relationship)
CREATE (simulation)-[:CONTAINS]->(emotion)
CREATE (mira)-[:HAS_EMOTION_STATE]->(emotion);
```

## 相关 API 端点

- `/simulations/{simulation_id}/input` 用于由 simulator 驱动的 relationship 和 emotion updates
- `/characters`, `/characters/{character_id}` 用于可能包含关系和情绪派生状态的角色上下文
- `/memories`, `/memories/{memory_id}` 用于 evidence records
- `/events`, `/events/{event_id}` 用于导致情绪变化的 event records

Relationship 和 emotion state 当前主要由 simulator 和 database services 维护，而不是通过宽泛的公共 CRUD routers 维护。

