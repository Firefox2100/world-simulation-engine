# Events, Turns, and Actions

## Purpose

Turns record the ordered conversation and simulation execution. Events group one or more turns into meaningful occurrences. Intents represent character goals and plans that may be created or affected by events. Generation jobs, graph snapshots, audit events, and presentation blocks support asynchronous execution, inspection, and user-facing output.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Turn` | `id`, `sequence`, `type`, `content`, `start_time` |
| `TurnPresentationBlock` | `id`, `turn_id`, `rendering_id`, `locale`, `sequence`, `type`, `text`, `speaker_id`, `speaker_name`, `media_id`, `voice_media_id`, `completion`, timestamps |
| `Event` | `id`, `name`, `summary` |
| `Intent` | `id`, `type`, `name`, `description`, `keywords`, `embedding`, `priority`, `urgency`, `status`, planning and condition fields |
| `GenerationJob` | `id`, `simulation_id`, `request_type`, `status`, `stage`, timestamps, `error`, `final_turn_id` |
| `GraphStateSnapshot` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, `state`, `created_at` |
| `SimulationAuditEvent` | `id`, `simulation_id`, `run_id`, `turn_id`, `category`, `origin`, `status`, `stage`, `summary`, actor and entity ids, `details`, timestamps |

## Relationships

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

## Ownership and lifecycle

Turns are owned by a world or simulation and ordered by `sequence` plus `NEXT`. Runtime simulation turns are append-only history. Events are linked from turns and then support memories and intent changes.

Proposed state is not truth by itself. A turn can record proposed changes with `PROPOSED_STATE_CHANGE`, but the graph becomes committed truth when the state committer writes properties and relationships to the affected entities.

## Creation and deletion behaviour

Creating a turn assigns it to a source and links it after the previous turn. Creating an event links the selected turn or turns with `PART_OF`. Presentation rendering replaces the blocks for a specific turn/rendering pair before writing the new ordered block set.

Deleting an event removes event links from turns and deletes the event if nothing still references it. Deleting a simulation removes turns, jobs, snapshots, and contained audit nodes with the runtime graph.

## Invariants

- Turn `sequence` should be unique within a world or simulation source.
- `NEXT` should match turn sequence order.
- Presentation block sequences must be unique and contiguous within a rendering.
- Media presentation blocks require `media_id`; non-media blocks require text.
- Speech blocks require either `speaker_id` or `speaker_name`.
- `updated_at` must not be earlier than `created_at`.

## Example Cypher representation

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

## Related API endpoints

- `/turns`, `/turns/{turn_id}`, `/worlds/{world_id}/turns`, `/simulations/{simulation_id}/turns/{sequence}`
- `/turn-presentations`, `/turns/{turn_id}/presentation`
- `/events`, `/events/{event_id}`, `/events/{event_id}/turns`, `/events/{event_id}/characters`
- `/intents`, `/intents/{intent_id}`, `/characters/{character_id}/intents`, `/intents/{intent_id}/character`, `/intents/{intent_id}/created-by`, `/intents/{intent_id}/contributing-events`
- `/simulations/{simulation_id}/input`, `/simulations/{simulation_id}/runs/{thread_id}`
- `/simulations/{simulation_id}/graph-snapshots`

