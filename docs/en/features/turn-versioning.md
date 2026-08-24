# Turn Versioning and State Checkpoints

Regenerating a turn ("swipe") is common in chat UIs, but here it can't just be re-narration. A discarded turn may
have already changed the world — an item moved, a relationship shifted, the clock advanced — and those effects have
to be undone too, or the world drifts out of sync with whatever turn ends up live. Two models make regeneration and
revert safe:

| Model | Purpose |
| --- | --- |
| `TurnVersion` | An archived alternate of one turn slot (a specific `turn_sequence`), captured right before that slot's live turn is replaced by a regeneration or a revert. |
| `WorldStateCheckpoint` | A full capture of the simulation's *persisted* entity graph at one save point, so restoring a turn can also restore the world state that went with it. |

## Why not just `GraphStateSnapshot`?

`GraphStateSnapshot` already exists to resume a LangGraph run for continuation or regeneration, but it only captures
the run's transient proposal state — not what has actually been committed to Neo4j. `WorldStateCheckpoint` captures
the real persisted entities instead: characters, background characters, items, item stacks, equipment, containers,
variable sets, entity relationships, emotion states, subjective claims, memories, and events. The two are paired at
the same save points, but only the checkpoint is enough to put the graph itself back the way it was.

## Checkpoint boundaries

`WorldStateCheckpointType` values:

| Type | Captured | Purpose |
| --- | --- | --- |
| `BEFORE_USER_INPUT` | Right before a new user-input generation starts. | Restore point for regenerating the turn that's about to be produced. |
| `AFTER_USER_INPUT` | Right after user input processing commits. | Restore point for the turn that resulted from user input. |
| `AFTER_CHARACTER_ROUND` | Right after an off-scene/continuation character round commits. | Restore point for a continuation turn. |
| `BEFORE_OOC_MUTATION` | Right before an OOC-forced world-state mutation commits. | No `GraphStateSnapshot` counterpart — an OOC mutation has no LangGraph proposal state to roll back. Capture-only today; nothing restores from it yet, laid down for a future "undo my last OOC command." |

The first three line up 1:1 by value with `GraphStateSnapshotType`, captured at the same points in `WorldSimulator`.

## Regenerating a turn ("swipe")

Requesting a `REGENERATION` for a given `turn_sequence`:

1. Archives whatever turn currently occupies that slot into a `TurnVersion` — its content, presentation blocks, the
   user input that produced it, and a pointer to the checkpoint captured right after it.
2. Restores the `WorldStateCheckpoint` from just before that slot (`turn_sequence - 1`), undoing any world-state
   effects the discarded turn had already committed.
3. Runs generation again for the same slot, producing a fresh turn.

## Reverting to an archived version

Reverting is the symmetric operation, not just a lookup:

1. Archives whatever is currently live at the target slot first — so reverting never destroys a branch the user
   might come back to, and a revert of a revert is always possible.
2. Deletes any turns that came after the target slot.
3. Restores the archived version's turn/presentation content.
4. Restores the version's paired `WorldStateCheckpoint`, if it hasn't since been pruned (see retention below).
   Otherwise it falls back to restoring the turn/presentation content alone, without world state.

A revert is refused while the simulation already has an active generation running, to avoid restoring state out from
under an in-progress run.

## Retention: alternates don't accumulate forever

Both models are pruned aggressively once the story genuinely moves forward, so discarded branches don't pile up:

- Saving a new `BEFORE_USER_INPUT` checkpoint deletes every other checkpoint for that simulation first — only the
  current turn cycle's checkpoints exist at once.
- Once a real user-input generation begins, every archived `TurnVersion` for the simulation is deleted. Whichever
  version was left live at each slot is the one that mattered; every other swipe becomes unreachable and is dropped
  rather than kept forever.

This means archived alternates are browsable and revertible only within the current turn cycle — swipe through them
before sending the next real message, not after.

## Restoring a checkpoint

`SimulationStateCheckpointService.restore` always applies a checkpoint in the same three phases, never interleaved
per entity type, so a partial restore can't leave the graph in a state nothing captured:

1. Create missing entities and force-overwrite existing ones, in dependency order (an entity referencing another is
   created only after the entity it references already exists).
2. Re-home placement relationships (owner, holder, location, landmark, equipped) for every captured character, item
   stack, equipment, and container, whether it was freshly created or overwritten.
3. Delete extra entities — present now but absent from the checkpoint — leaf-to-root, after step 2 has already
   re-homed anything worth keeping, so nothing gets collaterally destroyed by a cascading delete.

## OOC mutations also capture a checkpoint

An out-of-character command can force a world-state mutation directly (see [Multi-agent
flow](multi-agent-flow.md) for `OOCHandler`), including creating, updating, or disabling a
[`Trigger`](../data-model/events-turns-and-actions.md#triggers-and-cues). Every OOC-forced mutation is preceded by a
`BEFORE_OOC_MUTATION` checkpoint capture — recorded using the same primitive turn regeneration relies on, but with no
restore path wired up yet. It's there so a future "undo my last OOC command" feature has the data it needs without
requiring a second capture mechanism later.

## API and frontend

- `GET /simulations/{simulation_id}/turn-versions?turn_sequence={n}` — list archived versions for one turn slot,
  most recent first.
- `POST /simulations/{simulation_id}/turn-versions/{version_id}/revert` — revert to one archived version.
- `POST /simulations/{simulation_id}/input` with `request_type: regeneration` and `regenerate_turn_sequence` set —
  regenerate one turn slot.

`SimulationChatPage`'s swipe control uses these endpoints to let a user step back through discarded regenerations and
pick one up again, in addition to generating a fresh alternate.
