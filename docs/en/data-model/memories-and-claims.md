# Memories and Claims

## Purpose

Memories and claims model character perspective. `MemoryAtom` nodes store compact recollections with keywords and embeddings. `SubjectiveEntityClaim` nodes store what one character believes about another entity, including confidence and evidence links.

## Important properties

| Entity | Important properties |
| --- | --- |
| `MemoryAtom` | `id`, `summary`, `keywords`, `embedding` |
| `REMEMBERS` relationship | confidence, salience, behavioral relevance, stance metadata |
| `SubjectiveEntityClaim` | `id`, `simulation_id`, `observer_character_id`, `subject`, `category`, `statement`, `normalized_statement`, `stance`, `confidence`, supporting and contradicting memory ids, timestamps, `version`, `active` |
| `SubjectiveClaimChangeAudit` | `id`, `claim_id`, `simulation_id`, `turn_id`, `observer_character_id`, `change_type`, evidence memory ids, timestamps |

## Relationships

- `(:Event)-[:SUPPORTS]->(:MemoryAtom)`
- `(:Character)-[:REMEMBERS]->(:MemoryAtom)`
- `(:Character)-[:HOLDS_MODEL]->(:SubjectiveEntityClaim)`
- `(:SubjectiveEntityClaim)-[:ABOUT]->(:Character|BackgroundCharacter|Location|Landmark|Item|ItemStack|Equipment|Container|...)`
- `(:MemoryAtom)-[:CLAIM_EVIDENCE]->(:SubjectiveEntityClaim)`
- `(:Simulation)-[:CONTAINS]->(:SubjectiveEntityClaim)`
- `(:Simulation)-[:CONTAINS]->(:SubjectiveClaimChangeAudit)`
- `(:Turn)-[:TRIGGERED]->(:SubjectiveClaimChangeAudit)`
- `(:SubjectiveClaimChangeAudit)-[:CHANGED]->(:SubjectiveEntityClaim)`

## Ownership and lifecycle

Memories are produced from events and then attached to the characters who remember them. A memory can be shared by multiple characters, but each `REMEMBERS` relationship can carry character-specific relevance.

Subjective claims belong to a simulation and an observer character. They describe a subject entity from that observer's perspective and are revised over time by simulator proposals and state commits.

## Creation and deletion behaviour

Creating a memory attaches it to an event with `SUPPORTS` and to one or more characters with `REMEMBERS`. Reassigning memory characters replaces the existing remembered links. Deleting a memory removes the memory node and its evidence links.

Creating a subjective claim validates that the observer belongs to the simulation and that the subject is visible in the simulation or inherited world graph. Claim updates create audit nodes when the change is part of a turn.

## Invariants

- A subjective claim observer cannot be the same entity as the subject.
- Supporting and contradicting memory ids are deduplicated and must not overlap.
- Evidence memories for a claim must be remembered by the observer.
- `normalized_statement` should be stable enough for duplicate detection and contradiction checks.
- Claims can be inactive instead of physically deleted when history needs to remain explainable.

## Example Cypher representation

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

## Related API endpoints

- `/memories`, `/memories/{memory_id}`
- `/memories/{memory_id}/event`
- `/memories/{memory_id}/characters`
- `/events/{event_id}/turns`, `/events/{event_id}/characters`
- `/simulations/{simulation_id}/input` for simulator-driven memory and claim updates during a turn

Subjective claims are primarily maintained by the simulation pipeline and backing stores. A broad public CRUD router is not exposed for them in the same way as memories.

