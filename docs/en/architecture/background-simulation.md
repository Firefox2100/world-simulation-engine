# Background Simulation

World Simulation Engine tries to keep off-scene characters active without blocking every user interaction. Foreground
generation handles the user's current scene. Off-scene generation is queued separately per simulation and can finish
in the background unless it might conflict with the foreground turn.

## Foreground and off-scene execution

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant Foreground as Foreground generation
    participant Conflict as Conflict check
    participant Queue as Off-scene queue
    participant Worker as Off-scene worker
    participant Actor as Off-scene character simulator
    participant Store as Neo4j

    User->>Foreground: submit input
    Foreground->>Conflict: check active off-scene generations
    alt user action may touch off-scene result
        Conflict->>Worker: wait_for_off_scene_activity()
        Worker->>Store: finish pending off-scene commits
        Worker-->>Foreground: safe to continue
    else no conflict
        Conflict-->>Foreground: continue immediately
    end

    Foreground->>Store: commit foreground turn
    Foreground->>Queue: schedule off-scene activity from committed turn
    Queue-->>Worker: work item
    Worker->>Actor: select available off-scene actor
    Note over Actor: Reads private character context for that actor
    Actor-->>Worker: proposed action
    Worker->>Worker: validate and coordinate single-actor activity
    Worker->>Store: apply state commit and memory summary
    Note over Store: Off-scene result becomes committed truth when applied
```

## Scheduling model

After a foreground turn commits, `WorldSimulator._schedule_off_scene_activity()` creates an off-scene generation
status and enqueues work for the simulation. A per-simulation worker consumes those work items. The worker selects
available actors, proposes activity, validates it, coordinates it into a simple accepted timeline, applies state
changes, and summarizes memory.

Characters are considered available when their current activity is absent, due for reevaluation, or interruptible.
The scheduler bounds how many scheduled characters are considered in foreground character rounds so a single turn
does not explode into an unbounded cast-wide generation.

## Conflict checks

Foreground generation calls `_wait_for_conflicting_off_scene_activity()` before interpretation and before character
validation. It waits for off-scene work when the user's action could depend on it, for example:

- the user refers to an off-scene actor by name,
- the user moves into or interacts with a location where off-scene activity is active,
- a foreground character proposal could collide with a pending off-scene actor or location.

If there is no likely conflict, foreground generation proceeds. The next read of graph state will see whatever
off-scene work has already committed.

## Why this exists

A global "everyone acts every turn" loop would be too slow and would overexpose hidden context. A pure foreground
loop would freeze everyone outside the user's immediate view. The queue model is the compromise:

- visible and relevant activity stays synchronized with the user's turn,
- unrelated off-scene activity can progress independently,
- private character context remains actor-scoped,
- off-scene results still pass through validation, coordination, commit, and memory summary before becoming truth.
