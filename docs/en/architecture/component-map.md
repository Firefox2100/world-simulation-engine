# Component Map

This page maps the major runtime components to their responsibilities. It is meant as a quick orientation before
reading the backend or persistence pages.

## Runtime component map

```mermaid
flowchart TD
    subgraph Frontend["Frontend"]
        Pages["Pages<br/>simulations, worlds, media, prompts, configurations"]
        APIClient["API client modules"]
        Editors["Editors<br/>world, simulation, prompt, media, config"]
    end

    subgraph Backend["FastAPI backend"]
        Routers["Routers"]
        AppState["App state<br/>database, storage, prompt/workflow loaders, simulator"]
        Simulator["WorldSimulator"]
        Services["Service layer<br/>LLM, embedding, image, TTS, STT, import/export"]
    end

    subgraph Simulation["Simulation components"]
        Interpreter["InputInterpreter"]
        Validator["ActionValidator"]
        Character["CharacterSimulator"]
        Perspective["PerspectiveResolver"]
        Coordinator["SceneCoordinator"]
        Committer["StateCommitter"]
        Memory["MemorySummarizer"]
        Relationship["RelationshipUpdater"]
        Subjective["SubjectiveModelUpdater"]
        Emotion["EmotionUpdater"]
        Narrator["Narrator"]
        MediaSideEffects["TurnImageTrigger / TurnVoiceTrigger"]
    end

    subgraph Persistence["Persistence"]
        DatabaseService["DatabaseService"]
        Stores["Typed Neo4j stores"]
        Storage["StorageService"]
        Neo4j["Neo4j"]
        Files["Media files"]
    end

    Pages --> APIClient --> Routers
    Routers --> AppState
    AppState --> Simulator
    AppState --> DatabaseService
    AppState --> Storage
    Simulator --> Interpreter
    Simulator --> Validator
    Simulator --> Character
    Character --> Perspective
    Simulator --> Coordinator
    Simulator --> Committer
    Simulator --> Memory
    Memory --> Relationship
    Memory --> Subjective
    Memory --> Emotion
    Simulator --> Narrator
    Simulator --> MediaSideEffects
    Interpreter --> Services
    Validator --> Services
    Character --> Services
    Coordinator --> Services
    Committer --> Services
    Memory --> Services
    Narrator --> Services
    DatabaseService --> Stores --> Neo4j
    Storage --> Files
```

## Simulation components

| Component | Reads | Produces | Truth boundary |
| --- | --- | --- | --- |
| `InputInterpreter` | User text and current simulation context | Structured candidate user actions or OOC detection | Proposal only. |
| `ActionValidator` | Proposed actions and graph state | Validation results and rework feedback | Proposal only. |
| `CharacterSimulator` | Private `CharacterPerspective` | Character action or reaction proposals | Proposal only. |
| `PerspectiveResolver` | Graph perception candidates | Actor-scoped perceived entities | Private context. |
| `SceneCoordinator` | Valid action plans and reaction history | Accepted action timeline or coordination problem | Proposal only. |
| `StateCommitter` | Accepted actions | `StateCommitProposal` operations | Truth only after store application. |
| `MemorySummarizer` | Committed turn, observers, state commit | Events, memories, intent updates | Derived truth after memory store application. |
| `RelationshipUpdater` | Memories and perspective evidence | Relationship proposals | Derived truth after store application. |
| `SubjectiveModelUpdater` | Memories and observer context | Private subjective claim proposals | Private derived truth after store application. |
| `EmotionUpdater` | Memories, actions, character state | Private emotion vector update | Private derived truth after store application. |
| `Narrator` | Accepted or committed turn context | `NarrationProposal` / presentation text | Display layer, not physical truth. |
| `ActionSuggester` | Recent turn context | Suggested user actions | UI aid only. |

## Service components

| Service | Responsibility |
| --- | --- |
| `LlmService` | Compose prompt messages, call chat providers, and repair structured output. |
| `EmbedService` | Call embedding providers for memory and intent retrieval. |
| `ImageService` | Submit image prompts to ComfyUI-compatible image backends. |
| `TurnImageTrigger` | Decide and run turn or entity image generation as a side effect. |
| `TurnVoiceTrigger` | Run configured TTS generation for turn presentation segments as a side effect. |
| `StorageService` | Store and retrieve content-addressed media and JSON artifacts. |
| `AuditService` | Record structured audit events for generation, validation, coordination, commit, time, and errors. |

## Configuration flow

Provider connections, model configs, prompt assignments, workflow assignments, and per-component bindings are stored
in Neo4j. Simulation components load their assigned configuration at runtime. This means the same code path can use
different models for interpretation, character proposal, coordination, narration, image prompt building, and media
generation.
