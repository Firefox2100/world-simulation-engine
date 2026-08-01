# Persistence

Persistence is split between Neo4j and content-addressed file storage. Neo4j stores structured simulation state and
relationships. File storage holds media and JSON artifacts that should not live as large graph properties.

## Neo4j store facade

The backend uses `DatabaseService` as a facade over typed store classes. Each store owns a focused part of the graph:

| Store area | Examples |
| --- | --- |
| World and simulation | Worlds, simulations, current time, copied world state. |
| Physical state | Characters, locations, landmarks, items, equipment, containers, location and inventory relationships. |
| Cognitive state | Memories, intents, relationships, subjective claims, emotions. |
| Generation state | Turns, turn presentation, generation jobs, graph state snapshots, audit records. |
| Configuration | Provider connections, model configs, component assignments, prompt and workflow assignments. |
| Media links | Media records and relationships from worlds, simulations, entities, prompts, workflows, and turns. |

## Committed truth

Physical graph truth is applied through `StateCommitStore.apply_state_commit_proposal()`. The LLM-facing committer
builds a `StateCommitProposal`, but the proposal is not truth until this store applies it and the turn is recorded.

Abstract truth is applied after the physical commit:

- `MemorySummaryStore` creates or updates events, memories, and intents.
- Relationship updates use committed memories as evidence.
- Subjective claim updates are observer-scoped private beliefs.
- Emotion updates are private character state.

This separation prevents narration from becoming the database and prevents a proposed mutation from being treated as
state before commit.

## Graph state snapshots

Graph state snapshots persist generation state around important boundaries:

| Snapshot type | Purpose |
| --- | --- |
| `BEFORE_USER_INPUT` | Restore the base state before a user-input generation. |
| `AFTER_USER_INPUT` | Preserve the state after user input processing. |
| `AFTER_CHARACTER_ROUND` | Provide a base for continuation and regeneration. |

Snapshots are not a replacement for the graph. They capture the simulator's execution state so later continuation or
regeneration can resume from a known structured boundary.

## Turn presentation

Turns are canonical records of what happened and when. `TurnPresentationRendering` stores display blocks separately:

- narration,
- speech,
- action text,
- generated audio references,
- generated image references.

This allows the frontend to render or regenerate presentation without rewriting the underlying truth of the turn.

## Media storage

`StorageService` stores binary and JSON content in a content-addressed folder. Neo4j stores metadata and links, not
the raw files. This is used for generated images, uploaded cover media, voice files, prompt JSON, and workflow JSON.
