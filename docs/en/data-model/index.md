# Data Model

World Simulation Engine stores narrative state as structured graph data. The graph is not only persistence; it is the working memory that lets simulation components answer questions such as who is present, what a character privately believes, which memories support a relationship, and which generated media belongs to a turn.

This section is a contributor reference for the main node labels, relationships, lifecycle rules, and API surfaces.

## Model families

| Area | Documents | Primary labels |
| --- | --- | --- |
| World structure | [World and location](world-and-location.md) | `Author`, `World`, `Simulation`, `Location`, `Landmark` |
| People | [Characters](characters.md) | `Character`, `BackgroundCharacter`, `Intent`, `CharacterTtsConfig` |
| Physical state | [Items and containers](items-and-containers.md) | `Item`, `ItemStack`, `Equipment`, `Container` |
| Turn history | [Events, turns, and actions](events-turns-and-actions.md) | `Turn`, `TurnPresentationBlock`, `Event`, `Intent`, `GenerationJob`, `GraphStateSnapshot`, `SimulationAuditEvent` |
| Memory and belief | [Memories and claims](memories-and-claims.md) | `MemoryAtom`, `SubjectiveEntityClaim`, `SubjectiveClaimChangeAudit` |
| Social state | [Relationships and emotions](relationships-and-emotions.md) | `EntityRelationship`, `EmotionState`, `RelationshipChangeAudit`, `EmotionChangeAudit` |
| Assets and service config | [Media and configuration](media-and-configuration.md) | `Media`, `ConnectionConfig`, model config nodes, generation config nodes |

## Complete entity-relationship diagram

```mermaid
flowchart LR
    Author["Author"]
    World["World"]
    Simulation["Simulation"]
    Location["Location"]
    Landmark["Landmark"]
    Character["Character"]
    BackgroundCharacter["BackgroundCharacter"]
    Intent["Intent"]
    Item["Item"]
    ItemStack["ItemStack"]
    Equipment["Equipment"]
    Container["Container"]
    Turn["Turn"]
    TurnPresentationBlock["TurnPresentationBlock"]
    Event["Event"]
    MemoryAtom["MemoryAtom"]
    SubjectiveEntityClaim["SubjectiveEntityClaim"]
    SubjectiveClaimChangeAudit["SubjectiveClaimChangeAudit"]
    EntityRelationship["EntityRelationship"]
    RelationshipChangeAudit["RelationshipChangeAudit"]
    EmotionState["EmotionState"]
    EmotionChangeAudit["EmotionChangeAudit"]
    Media["Media"]
    PromptMediaFile["PromptMediaFile"]
    WorkflowMediaFile["WorkflowMediaFile"]
    ConnectionConfig["ConnectionConfig"]
    ChatModelConfig["Chat model config"]
    EmbedModelConfig["Embedding model config"]
    ImageModelConfig["Image model config"]
    TtsModelConfig["TTS model config"]
    SttModelConfig["STT model config"]
    ImageGenerationConfig["ImageGenerationConfig"]
    TtsGenerationConfig["TtsGenerationConfig"]
    CharacterTtsConfig["CharacterTtsConfig"]
    GraphStateSnapshot["GraphStateSnapshot"]
    GenerationJob["GenerationJob"]
    SimulationAuditEvent["SimulationAuditEvent"]

    Author -->|CREATED| World
    World -->|NEW_VERSION_OF| World
    Simulation -->|BASED_ON| World
    World -->|CONTAINS| Location
    World -->|CONTAINS| Character
    World -->|CONTAINS| BackgroundCharacter
    World -->|CONTAINS| Item
    World -->|CONTAINS| Equipment
    World -->|CONTAINS| Container
    Simulation -->|CONTAINS| Location
    Simulation -->|CONTAINS| Character
    Simulation -->|CONTAINS| BackgroundCharacter
    Simulation -->|CONTAINS| Item
    Simulation -->|CONTAINS| ItemStack
    Simulation -->|CONTAINS| Equipment
    Simulation -->|CONTAINS| Container
    Simulation -->|CONTAINS| Turn
    Simulation -->|CONTAINS| EntityRelationship
    Simulation -->|CONTAINS| SubjectiveEntityClaim
    World -->|CONTAINS| SubjectiveEntityClaim
    Simulation -->|CONTAINS| EmotionState
    Simulation -->|HAS_GENERATION_JOB| GenerationJob
    Simulation -->|HAS_GRAPH_STATE_SNAPSHOT| GraphStateSnapshot
    Simulation -->|HAS_AUDIT_EVENT| SimulationAuditEvent

    Location -->|CONTAINS| Location
    Location -->|CONTAINS| Landmark
    Character -->|PRESENT_IN| Location
    BackgroundCharacter -->|PRESENT_IN| Location
    Character -->|ANCHORED_TO| Landmark
    BackgroundCharacter -->|ANCHORED_TO| Landmark

    Character -->|HOLDS| Intent
    Character -->|HOLDS| ItemStack
    Character -->|HOLDS| Equipment
    Character -->|EQUIPS| Equipment
    Character -->|HOLDS| Container
    Character -->|OWNS| ItemStack
    Character -->|OWNS| Equipment
    Character -->|OWNS| Container
    Container -->|HOLDS| ItemStack
    Container -->|HOLDS| Equipment
    Container -->|HOLDS| Container
    ItemStack -->|OF_TYPE| Item
    Equipment -->|PRESENT_IN| Location
    ItemStack -->|PRESENT_IN| Location
    Container -->|PRESENT_IN| Location
    Item -->|UNLOCKS| Container

    Turn -->|NEXT| Turn
    Turn -->|PART_OF| Event
    Event -->|INVOLVES| Character
    Event -->|CREATES| Intent
    Event -->|CONTRIBUTES_TO| Intent
    Turn -->|PROPOSED_STATE_CHANGE| Character
    Turn -->|PROPOSED_STATE_CHANGE| Location
    Turn -->|PROPOSED_STATE_CHANGE| ItemStack
    Turn -->|HAS_PRESENTATION| TurnPresentationBlock
    TurnPresentationBlock -->|HAS_VOICE| Media
    Turn -->|GENERATES_IMAGE| Media
    TurnPresentationBlock -->|GENERATES_IMAGE| Media

    Event -->|SUPPORTS| MemoryAtom
    Character -->|REMEMBERS| MemoryAtom
    Character -->|HOLDS_MODEL| SubjectiveEntityClaim
    SubjectiveEntityClaim -->|ABOUT| Character
    SubjectiveEntityClaim -->|ABOUT| Location
    SubjectiveEntityClaim -->|ABOUT| Item
    MemoryAtom -->|CLAIM_EVIDENCE| SubjectiveEntityClaim
    Turn -->|TRIGGERED| SubjectiveClaimChangeAudit
    SubjectiveClaimChangeAudit -->|CHANGED| SubjectiveEntityClaim

    Character -->|HAS_EMOTION_STATE| EmotionState
    MemoryAtom -->|EVIDENCE_FOR| EntityRelationship
    Character -->|RELATIONSHIP_SOURCE| EntityRelationship
    EntityRelationship -->|RELATIONSHIP_TARGET| Character
    MemoryAtom -->|EVIDENCE_FOR| RelationshipChangeAudit
    Turn -->|TRIGGERED| RelationshipChangeAudit
    RelationshipChangeAudit -->|CHANGED| EntityRelationship
    Event -->|CAUSED_EMOTION_CHANGE| EmotionChangeAudit
    MemoryAtom -->|EVIDENCE_FOR| EmotionChangeAudit
    Turn -->|TRIGGERED| EmotionChangeAudit
    EmotionChangeAudit -->|CHANGED| EmotionState

    World -->|HAS_MEDIA| Media
    Simulation -->|HAS_MEDIA| Media
    Character -->|HAS_MEDIA| Media
    Location -->|HAS_MEDIA| Media
    Item -->|HAS_MEDIA| Media
    ItemStack -->|HAS_MEDIA| Media
    Equipment -->|HAS_MEDIA| Media
    Container -->|HAS_MEDIA| Media
    World -->|HAS_COVER| Media
    Character -->|HAS_COVER| Media
    Location -->|HAS_COVER| Media
    Media -->|specializes as| PromptMediaFile
    Media -->|specializes as| WorkflowMediaFile

    World -->|USES| ChatModelConfig
    Simulation -->|USES| ChatModelConfig
    World -->|USES| EmbedModelConfig
    Simulation -->|USES| EmbedModelConfig
    World -->|USES| ImageModelConfig
    Simulation -->|USES| ImageModelConfig
    World -->|USES| TtsModelConfig
    Simulation -->|USES| TtsModelConfig
    ChatModelConfig -->|USES| ConnectionConfig
    EmbedModelConfig -->|USES| ConnectionConfig
    ImageModelConfig -->|USES| ConnectionConfig
    TtsModelConfig -->|USES| ConnectionConfig
    SttModelConfig -->|USES| ConnectionConfig
    Simulation -->|HAS_IMAGE_GENERATION_CONFIG| ImageGenerationConfig
    Simulation -->|HAS_TTS_GENERATION_CONFIG| TtsGenerationConfig
    Character -->|HAS_CONFIG| CharacterTtsConfig
    CharacterTtsConfig -->|USE_CONFIG| TtsModelConfig
    World -->|USE_PROMPT| PromptMediaFile
    Simulation -->|USE_PROMPT| PromptMediaFile
    World -->|USE_WORKFLOW| WorkflowMediaFile
    Simulation -->|USE_WORKFLOW| WorkflowMediaFile
```

## Cross-cutting rules

- `World` is the reusable authored template. `Simulation` is the mutable run state based on a world.
- Most authored and runtime entities are connected from a `World` or `Simulation` with `CONTAINS`.
- Simulations can read inherited world data through `BASED_ON`, but runtime mutations are committed into the simulation graph.
- Physical placement is exclusive in normal state: an object is either in a location, held/equipped by another entity, or contained by a container.
- Turns record proposals with `PROPOSED_STATE_CHANGE`; the graph becomes committed truth only when the state committer writes the proposed changes.
- Private context is modeled on character fields, subjective claims, relationship visibility, memories, and emotion state. Presentation APIs should expose only the appropriate rendered view.
