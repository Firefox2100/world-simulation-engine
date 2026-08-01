# Simulation Lifecycle

A simulation generation is a background job started by the simulation API. For a normal user turn, the job runs the
user-input LangGraph in `WorldSimulator`. Continuation and regeneration use the character-round graph restored from a
saved graph state snapshot.

## One-turn sequence

This diagram shows the intended data boundary for a normal turn. The exact graph can branch for invalid input,
out-of-character commands, reaction rounds, or no scheduled character activity, but the truth boundary is the same:
candidate and proposed data remain provisional until state commit applies accepted operations.

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API as FastAPI simulation router
    participant Sim as WorldSimulator
    participant Input as Input interpreter
    participant Validator as Action validator
    participant Char as Character simulator
    participant Coord as Scene coordinator
    participant Commit as State committer
    participant Memory as Memory/belief/emotion updates
    participant Narrator
    participant Store as Neo4j + media stores
    participant UI as Turn presentation

    User->>API: POST /simulations/{id}/input
    API->>Sim: start_generation(user_input)
    Sim->>Store: save BEFORE_USER_INPUT snapshot
    Sim->>Input: interpret text against public simulation state
    Input-->>Sim: candidate user action or OOC result

    Sim->>Validator: validate candidate action
    Validator-->>Sim: validation result (proposed validity)

    alt valid user action
        Sim->>Store: select event observers from graph scope
        Sim->>Commit: build StateCommitProposal for user action
        Commit-->>Sim: proposed physical graph operations
        Sim->>Store: create turn + apply state commit
        Note over Store: User action becomes committed truth here
        Sim->>Memory: summarize user turn for observers
        Memory-->>Sim: MemorySummaryProposal and derived updates
        Sim->>Store: apply events, memories, intents, relationships, beliefs, emotion
    else invalid user action
        Sim->>Narrator: narrate validation failure
        Narrator-->>Sim: failure presentation
        Sim->>Store: create failure/no-op turn presentation
    end

    Sim->>Char: propose scheduled character actions
    Note over Char: Reads private character context: perspective, memory, beliefs, relationships, emotion
    Char-->>Sim: per-character ActionProposal values
    Sim->>Validator: validate character proposals
    Validator-->>Sim: validated proposed action plans
    Sim->>Coord: resolve simultaneous actions and reactions
    Coord-->>Sim: AcceptedSceneAction timeline
    Note over Sim,Coord: Still proposed state, not graph truth
    Sim->>Narrator: narrate accepted timeline
    Narrator-->>Sim: narration blocks
    Sim->>Store: select event observers
    Sim->>Commit: build StateCommitProposal for accepted actions
    Commit-->>Sim: proposed physical graph operations
    Sim->>Store: create turn + apply state commit + advance simulation time
    Note over Store: Character actions become committed truth here
    Sim->>Memory: summarize committed character turn
    Memory-->>Sim: events, memories, intents, relationships, beliefs, emotion
    Sim->>Store: apply abstract and derived state
    Store-->>UI: turn presentation blocks
    UI-->>User: rendered narration, speech, actions, media
```

## State phases

| Phase | Examples | Truth status |
| --- | --- | --- |
| Interpretation | `InputInterpretation`, candidate `ProposedAction` | Not truth. It is a parsed proposal. |
| Validation | `ActionValidationResult` | Not truth. It decides whether proposals may continue. |
| Character proposal | `ActionProposal`, `CharacterActionPlan` | Not truth. It is private-context output from one actor. |
| Coordination | `SceneCoordinationResult`, `AcceptedSceneAction` | Not truth. It is the accepted timeline to commit. |
| Physical commit proposal | `StateCommitProposal` | Not truth until applied by the database store. |
| Physical commit | `Turn`, graph entity/relationship mutations, `Simulation.current_time` | Committed truth. |
| Abstract memory commit | `MemorySummaryProposal`, events, memories, intents | Committed derived truth after memory summary store applies it. |
| Presentation | `TurnPresentationRendering` | Display layer derived from committed turns and narration. |

## Private context

Private character context is read during character proposal, reaction proposal, relationship updates, subjective
model updates, and emotion updates. It should not be treated as globally visible state. A character prompt receives a
scoped `CharacterPerspective`, not the full graph. That perspective can include private memories, subjective claims,
private relationship descriptions, and emotion, but those are only made visible to the actor whose context is being
built.

## Snapshots and regeneration

`WorldSimulator` saves graph state snapshots before user input and after generation base points. Continuation and
regeneration load those snapshots instead of trying to reconstruct execution state from narration. This keeps reruns
grounded in structured graph state and the simulator's own intermediate state.
