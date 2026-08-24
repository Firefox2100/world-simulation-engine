# Events, Turns, and Actions

## Purpose

Turns record the ordered conversation and simulation execution. Events group one or more turns into meaningful occurrences. Intents represent character goals and plans that may be created or affected by events. Triggers are hidden condition-to-effect rules that drive scripted story progression. Generation jobs, graph snapshots, audit events, and presentation blocks support asynchronous execution, inspection, and user-facing output. Turn versions and world state checkpoints support regenerating or reverting a turn without losing the world state it left behind.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Turn` | `id`, `sequence`, `type`, `content`, `start_time` |
| `TurnPresentationBlock` | `id`, `turn_id`, `rendering_id`, `locale`, `sequence`, `type`, `text`, `speaker_id`, `speaker_name`, `media_id`, `voice_media_id`, `completion`, timestamps |
| `Event` | `id`, `name`, `summary` |
| `Intent` | `id`, `type`, `name`, `description`, `keywords`, `embedding`, `priority`, `urgency`, `status`, planning and condition fields |
| `Trigger` | `id`, `source_id`, `name`, `description`, `condition`, `effect_kind`, `effects`, `gate_effect`, `chance`, `repeatable`, `cooldown_turns`, `reversible`, `status`, `last_condition_result`, `last_fired_turn_id`, `last_evaluated_turn_id` |
| `TriggerActivation` | `id`, `trigger_id`, `simulation_id`, `fired_at_turn_id`, `effect`, `consumed`, `consumed_at_turn_id` |
| `GenerationJob` | `id`, `simulation_id`, `request_type`, `status`, `stage`, timestamps, `error`, `final_turn_id` |
| `GraphStateSnapshot` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, `state`, `created_at` |
| `TurnVersion` | `id`, `simulation_id`, `turn_sequence`, `turn`, `presentation_blocks`, `user_input`, `checkpoint_id`, `created_at` |
| `WorldStateCheckpoint` | `id`, `simulation_id`, `type`, `turn_id`, `turn_sequence`, per-entity-type capture lists (`characters`, `items`, `entity_relationships`, `memories`, ...), `created_at` |
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
- `(:World|Simulation)-[:CONTAINS]->(:Trigger)`
- `(:Trigger)-[:FIRED]->(:TriggerActivation)`
- `(:Simulation)-[:CONTAINS]->(:TriggerActivation)`
- `(:Simulation)-[:HAS_GENERATION_JOB]->(:GenerationJob)`
- `(:Simulation)-[:HAS_GRAPH_STATE_SNAPSHOT]->(:GraphStateSnapshot)`
- `(:Simulation)-[:HAS_TURN_VERSION]->(:TurnVersion)`
- `(:Simulation)-[:HAS_STATE_CHECKPOINT]->(:WorldStateCheckpoint)`
- `(:Simulation|GenerationJob|Turn)-[:HAS_AUDIT_EVENT]->(:SimulationAuditEvent)`

## Triggers and cues

A `Trigger` is a hidden condition-to-effect rule authored on a `World` and copied into each `Simulation` created from
it, then evaluated independently per simulation copy. Its `condition` is a time, location, variable, semantic
statement, or a boolean combination of the deterministic ones; deterministic conditions are checked in code every
turn, while a semantic condition is judged by the `SemanticTriggerEvaluator` LLM component against recent narration
and memories. `effect_kind` decides the shape: `EVENT` fires once (optionally with a `chance` roll, and optionally
`repeatable` with a `cooldown_turns`) and queues up to 3 effects as a `TriggerActivation`; `GATE` instead tracks an
open/closed permission state, optionally `reversible`.

The defining design constraint is that a dormant trigger's own existence and content — `name`, `description`,
`effects`, `gate_effect` — must never reach an LLM prompt. The only trigger-derived content ever allowed into a
prompt is a `SemanticCondition`'s own `statement` (fed to the evaluator) and a *fired* `EVENT` effect's payload,
injected via `TriggerActivation` only into the specific prompt that needs it and only until `consumed`.

Authors and users can also create, redefine, arm/disable, or delete triggers indirectly: `OOCHandler` can turn an
out-of-character command into a `trigger_directive` (`create`/`update`/`set_status`/`delete`), applied through the
same store path as an authored trigger.

## Turn versioning and state checkpoints

Regenerating a turn ("swipe") or reverting to a discarded one has to put the world back the way it was, not just
change the displayed text. `WorldStateCheckpoint` captures the simulation's actual persisted entity graph (not the
transient LangGraph state `GraphStateSnapshot` holds) at one of four boundaries: `BEFORE_USER_INPUT`,
`AFTER_USER_INPUT`, and `AFTER_CHARACTER_ROUND` (mirroring `GraphStateSnapshotType` 1:1), plus `BEFORE_OOC_MUTATION`
— captured before an OOC-forced world-state mutation commits, with no restore path yet, laid down for a future
"undo my last OOC command."

`TurnVersion` archives one turn slot's previous content — the turn, its presentation blocks, the user input that
produced it, and a pointer to the checkpoint captured right after it — the instant that slot is about to be
replaced by a regeneration or a revert. Reverting is symmetric with regenerating: it archives whatever is currently
live first (so a revert of a revert is always possible), then restores the target version's content and, if its
checkpoint hasn't since been pruned, the world state that went with it.

Both models are pruned aggressively once the story moves forward for real: saving a new `BEFORE_USER_INPUT`
checkpoint deletes every other checkpoint for that simulation, and starting a genuine user-input generation deletes
every archived `TurnVersion` for the simulation. Archived alternates are only browsable and revertible within the
current turn cycle. See [Turn versioning and state checkpoints](../features/turn-versioning.md) for the full
regenerate/revert flow and the checkpoint restore order.

## Ownership and lifecycle

Turns are owned by a world or simulation and ordered by `sequence` plus `NEXT`. Runtime simulation turns are append-only history. Events are linked from turns and then support memories and intent changes.

Proposed state is not truth by itself. A turn can record proposed changes with `PROPOSED_STATE_CHANGE`, but the graph becomes committed truth when the state committer writes properties and relationships to the affected entities.

## Creation and deletion behaviour

Creating a turn assigns it to a source and links it after the previous turn. Creating an event links the selected turn or turns with `PART_OF`. Presentation rendering replaces the blocks for a specific turn/rendering pair before writing the new ordered block set.

Deleting an event removes event links from turns and deletes the event if nothing still references it. Deleting a
simulation removes turns, jobs, and graph state snapshots with the runtime graph, by walking `CONTAINS`/`HOLDS`/
`PART_OF`/`HAS_GRAPH_STATE_SNAPSHOT`/`HAS_GENERATION_JOB` from the simulation node. `HAS_TURN_VERSION`,
`HAS_STATE_CHECKPOINT`, and `HAS_AUDIT_EVENT` are not in that walk, so `TurnVersion`, `WorldStateCheckpoint`, and
`SimulationAuditEvent` nodes are currently left behind as orphans when a simulation is deleted.

## Invariants

- Turn `sequence` should be unique within a world or simulation source.
- `NEXT` should match turn sequence order.
- Presentation block sequences must be unique and contiguous within a rendering.
- Media presentation blocks require `media_id`; non-media blocks require text.
- Speech blocks require either `speaker_id` or `speaker_name`.
- `updated_at` must not be earlier than `created_at`.
- A simulation has at most one `BEFORE_USER_INPUT` checkpoint at a time; `AFTER_USER_INPUT` and
  `AFTER_CHARACTER_ROUND` checkpoints are keyed by `turn_sequence`, so each turn slot has its own.
- Reverting to a `TurnVersion` is refused while the simulation already has an active generation job.

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
- `/triggers`, `/triggers/{trigger_id}`, `/triggers/{trigger_id}/status`
- `/simulations/{simulation_id}/input`, `/simulations/{simulation_id}/runs/{thread_id}`
- `/simulations/{simulation_id}/graph-snapshots`
- `/simulations/{simulation_id}/turn-versions`, `/simulations/{simulation_id}/turn-versions/{version_id}/revert`

