# Relationships and Emotions

## Purpose

Relationships and emotions make social and affective state explicit in the graph. `EntityRelationship` nodes describe typed relationships between entities with optional private visibility and evidence. `EmotionState` nodes store baseline and immediate emotion vectors for characters. Audit nodes explain why relationship or emotion state changed.

## Important properties

| Entity | Important properties |
| --- | --- |
| `EntityRelationship` | `id`, `scope_type`, `scope_id`, `source`, `target`, `label`, `public_description`, `private_description`, `visibility`, `perspective_character_id`, `confidence`, `details`, evidence memory ids, timestamps, `version`, `active` |
| `EmotionState` | `id`, `simulation_id`, `character_id`, `baseline`, `immediate`, half-life seconds, `last_updated_at`, `version` |
| `EmotionVector` value | `valence`, `arousal`, `dominance`, free-form dimensions |
| `RelationshipChangeAudit` | relationship id, turn id, perspective character id, evidence memory ids, timestamps |
| `EmotionChangeAudit` | emotion state id, turn id, evidence memory ids, caused-by events |

## Relationships

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

## Ownership and lifecycle

Relationships are scoped to a world or simulation. World-scoped relationships are authored background facts. Simulation-scoped relationships are runtime facts and can reference inherited world entities or simulation entities.

Emotion state is simulation-scoped and character-owned. It is expected to change over time as turns produce events and memories. The baseline vector represents slower affective tendency; the immediate vector represents short-lived response.

## Creation and deletion behaviour

Creating an entity relationship validates source, target, scope, visibility, perspective, and evidence. Updating evidence replaces previous `EVIDENCE_FOR` links. Explicit deletion detaches and deletes the relationship node.

Emotion state is created for a simulation character as needed. Emotion deltas create `EmotionChangeAudit` nodes with turn, event, and memory evidence, then update the state vector and version.

## Invariants

- Relationship source and target must be different entities.
- Private relationships require `perspective_character_id`.
- A `private_description` requires a perspective character.
- Interpersonal relationship detail should connect character endpoints.
- Evidence memory ids are deduplicated.
- Emotion audit evidence must be remembered by the affected character and supported by events in the simulation.

## Example Cypher representation

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

## Related API endpoints

- `/simulations/{simulation_id}/input` for simulator-driven relationship and emotion updates
- `/characters`, `/characters/{character_id}` for character context that may include relationship and emotion-derived state
- `/memories`, `/memories/{memory_id}` for evidence records
- `/events`, `/events/{event_id}` for the event records that cause emotional changes

Relationship and emotion state is currently maintained mainly through the simulator and database services rather than broad public CRUD routers.

