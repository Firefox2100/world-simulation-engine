import os
import pytest

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.misc.enums import MessageRole, LlmProvider, FactionRelationshipEntity, \
    EquipmentStatus, WorldEntryVisibility, WorldEntryRecallType, NarrationPermission, TaskType, TaskStatus, \
    TaskPriority
from world_simulation_engine.model import LlmConnectionProfile, EmbeddingProfile, WorldGeneratorAgentProfile, \
    OllamaAgentBackendConfiguration, PromptMessage, DirectorAgentProfile, MemoryAgentProfile, \
    CharacterAgentProfile, Simulation, AgentPreset, DataPreset, ModelAttribute, SimulationState, Character, \
    Faction, FactionRelationship, Item, Equipment, Location, Entity, WorldEntry, WorldEntryRecallKeyword, Task, \
    ResolverAgentProfile, CommitterAgentProfile, NarratorAgentProfile
from world_simulation_engine.model.connection_profile import LlmConnectionCreate
from world_simulation_engine.service import DatabaseService


@pytest.fixture(autouse=True)
def disable_console_logger():
    if LOGGER.hasHandlers():
        for h in LOGGER.handlers[:]:
            LOGGER.removeHandler(h)


@pytest.fixture
async def db() -> DatabaseService:
    service = DatabaseService(
        database_path=":memory:",
        is_static=True,
    )

    await service.init()
    return service


@pytest.fixture
def ollama_base_url() -> str:
    return os.environ.get("TEST_OLLAMA_BASE_URL", "http://localhost:11434")


@pytest.fixture
def embedding_model() -> str:
    return os.getenv("TEST_OLLAMA_MODEL_EMBED", "text-embedding-3-small")


@pytest.fixture
def inference_model() -> str:
    return os.getenv("TEST_OLLAMA_MODEL", "gpt-4")


@pytest.fixture
def mock_llm_connection_create(ollama_base_url) -> LlmConnectionCreate:
    return LlmConnectionCreate(
        name="Mock Connection",
        provider=LlmProvider.OLLAMA,
        base_url=ollama_base_url,
        api_key=None,
    )


@pytest.fixture
def mock_llm_connection(ollama_base_url) -> LlmConnectionProfile:
    return LlmConnectionProfile(
        id=1,
        name="Mock Connection",
        provider=LlmProvider.OLLAMA,
        base_url=ollama_base_url,
        api_key=None,
    )


@pytest.fixture
def mock_embedding_profile(embedding_model) -> EmbeddingProfile:
    return EmbeddingProfile(
        connection=1,
        model=embedding_model,
        dimensions=1024,
        context_window=8192,
    )


@pytest.fixture
def mock_world_generator_profile(inference_model) -> WorldGeneratorAgentProfile:
    return WorldGeneratorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
            context_window=65536,
        ),
        location_generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a location generation tool for a role-play simulation.

Generate exactly one ProposedLocation.

Output schema:
- temp_id: temporary string ID for this proposal, for example "loc_temp_iron_stag_cellar". Do not use a database ID.
- primary_location: broad area or parent place.
- detailed_location: specific named place inside the parent area.
- scene: concise scene label used for the current playable area.
- description: objective, playable description of what characters can perceive and interact with.
- attributes: mapping of attribute names to lists of string values. Use {} unless constraints require attributes.
- stats: mapping of stat names to numeric values. Use {} unless constraints require stats.
- entities: 0-3 ProposedEntity objects already present in this location.
- reason: why this proposal is useful and how it satisfies the trigger.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Hard rules:
- The location is a pending proposal, not canonical.
- Do not reuse an existing location.
- Do not contradict existing locations or state summary.
- Do not solve major mysteries.
- Do not reveal final answers unless explicitly required.
- Use temporary IDs only for the location and generated entities.
- If adding entities inside the location, their type must match an existing setting entity type when possible.
- Keep the location useful for interaction, not just description.
- The location must fit the setting, era, tone, and current scene.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.

Location quality rules:
- Provide a concrete playable scene.
- Include sensory details only when they imply interaction or atmosphere.
- Include 0-3 proposed entities maximum.
- Entities should be clues, obstacles, containers, mechanisms, traces, or interactable fixtures.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate Location

## Goal

Your goal is:
{{ data.goal }}

This is only a guidance. You do not have to generate exactly the same content as it describes, as long as the
goal aligns. However, your proposed location must match the world style and is sensible.

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.round_number }}
Time: {{ data.generation_context.time_label }}
State summary:
{{ data.generation_context.state_summary }}

Data preset constraints:
- Entity types:
{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}
  - {{ type_name }}: {{ description }}
{% else %}
  - No custom entity types configured.
{% endfor %}
- Character attributes:
{% for attr in data.generation_context.data_preset.character_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Character stats:
{% for stat in data.generation_context.data_preset.character_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction attributes:
{% for attr in data.generation_context.data_preset.faction_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction stats:
{% for stat in data.generation_context.data_preset.faction_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}

Current location:
{{ data.generation_context.current_location }}

Present characters:
{% for c in data.generation_context.present_characters %}
- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}
{% else %}
None.
{% endfor %}

Existing locations:
{% for l in data.generation_context.existing_locations %}
- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}
{% else %}
None.
{% endfor %}

Existing entities in current location:
{% for e in data.generation_context.existing_entities %}
- {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}
{% else %}
None.
{% endfor %}

Existing items:
{% for i in data.generation_context.existing_items %}
- {{ i.id }}: {{ i.name }} | description={{ i.description }}
{% else %}
None.
{% endfor %}

Existing equipment:
{% for e in data.generation_context.existing_equipments %}
- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}
{% else %}
None.
{% endfor %}

Relevant factions and relationships:
{% for f in data.generation_context.factions %}
- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.generation_context.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Generate exactly one ProposedLocation.
    """
            )
        ],
        item_generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are an item generation tool for a role-play simulation.

Generate exactly one ProposedItem.

Output schema:
- temp_id: temporary string ID for this proposal, for example "item_temp_torn_receipt". Do not use a database ID.
- name: short item name.
- description: what the item is and what can be noticed about it. Do not narrate discovery.
- quality: optional condition label such as "worn", "torn", "polished", or null.
- quantity: integer count. Use 1 for unique or clue items.
- unique: true for named clues/evidence, false only for ordinary stackable objects.
- proposed_owner_id: existing character ID if the item clearly belongs in a character inventory; otherwise null.
- proposed_location_id: existing location ID if the item clearly belongs in a known location; otherwise null.
- reason: why this item is useful and how it satisfies the trigger.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Hard rules:
- The item is a pending proposal, not canonical.
- Do not duplicate existing items.
- Do not solve major mysteries.
- Do not create a final-answer clue unless explicitly required.
- The item must fit the setting, era, tone, and trigger.
- Use temp_id only.
- proposed_owner_id must be null unless the item is clearly generated for one of the present character IDs.
- proposed_location_id must be null or one of the existing location IDs.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.

Item quality rules:
- Prefer partial, ambiguous, actionable clues.
- A clue item should point to a lead, contradiction, location, person, or question.
- Avoid overly symbolic or genre-breaking objects unless the simulation tone supports them.
- description should say what the item is, not narrate its discovery.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate Item

## Goal

Your goal is:
{{ data.goal }}

This is only a guidance. You do not have to generate exactly the same content as it describes, as long as the
goal aligns. However, your proposed location must match the world style and is sensible.

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.round_number }}
Time: {{ data.generation_context.time_label }}
State summary:
{{ data.generation_context.state_summary }}

Data preset constraints:
- Entity types:
{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}
  - {{ type_name }}: {{ description }}
{% else %}
  - No custom entity types configured.
{% endfor %}
- Character attributes:
{% for attr in data.generation_context.data_preset.character_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Character stats:
{% for stat in data.generation_context.data_preset.character_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction attributes:
{% for attr in data.generation_context.data_preset.faction_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction stats:
{% for stat in data.generation_context.data_preset.faction_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}

Current location:
{{ data.generation_context.current_location }}

Present characters:
{% for c in data.generation_context.present_characters %}
- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}
{% else %}
None.
{% endfor %}

Existing locations:
{% for l in data.generation_context.existing_locations %}
- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}
{% else %}
None.
{% endfor %}

Existing items:
{% for i in data.generation_context.existing_items %}
- {{ i.id }}: {{ i.name }} | quality={{ i.quality }} | description={{ i.description }}
{% else %}
None.
{% endfor %}

Existing equipment:
{% for e in data.generation_context.existing_equipments %}
- {{ e.id }}: {{ e.name }} | status={{ e.status }} | quality={{ e.quality }} | description={{ e.description }}
{% else %}
None.
{% endfor %}

Relevant factions and relationships:
{% for f in data.generation_context.factions %}
- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.generation_context.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Generate exactly one ProposedItem.
"""
            ),
        ],
        entity_generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are an entity generation tool for a role-play simulation.

Generate exactly one ProposedEntity.

Output schema:
- temp_id: temporary string ID for this proposal, for example "entity_temp_locked_cabinet". Do not use a database ID.
- name: short entity name.
- type: exactly one supported entity type from the simulation data preset.
- description: objective details visible or discoverable by interaction.
- status: current state, access, damage, concealment, or other condition.
- interactions: concrete verbs or short phrases characters can attempt.
- reason: why this entity is useful and how it satisfies the trigger.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Hard rules:
- The entity is a pending proposal, not canonical.
- The entity must belong to or be discoverable within the current location unless constraints specify another location.
- Do not duplicate existing entities.
- type must be exactly one supported entity type from the simulation data preset.
- Do not invent unsupported entity types.
- Do not solve major mysteries.
- Do not create portable inventory items as entities unless they remain scene-anchored containers or fixtures.
- Use temp_id only.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.

Entity quality rules:
- The entity must support meaningful interactions.
- interactions must be concrete verbs or short phrases.
- status must describe its current discoverable condition.
- description should be objective and playable, not narrated prose.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate Entity

## Goal

Your goal is:
{{ data.goal }}

This is only a guidance. You do not have to generate exactly the same content as it describes, as long as the
goal aligns. However, your proposed location must match the world style and is sensible.

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.round_number }}
Time: {{ data.generation_context.time_label }}
State summary:
{{ data.generation_context.state_summary }}

Data preset constraints:
- Entity types:
{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}
  - {{ type_name }}: {{ description }}
{% else %}
  - No custom entity types configured.
{% endfor %}
- Character attributes:
{% for attr in data.generation_context.data_preset.character_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Character stats:
{% for stat in data.generation_context.data_preset.character_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction attributes:
{% for attr in data.generation_context.data_preset.faction_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction stats:
{% for stat in data.generation_context.data_preset.faction_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}

Current location:
{{ data.generation_context.current_location }}

Present characters:
{% for c in data.generation_context.present_characters %}
- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}
{% else %}
None.
{% endfor %}

Existing entities in current location:
{% for e in data.generation_context.existing_entities %}
- {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}
{% else %}
None.
{% endfor %}

Existing items:
{% for i in data.generation_context.existing_items %}
- {{ i.id }}: {{ i.name }} | description={{ i.description }}
{% else %}
None.
{% endfor %}

Existing equipment:
{% for e in data.generation_context.existing_equipments %}
- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}
{% else %}
None.
{% endfor %}

Relevant factions and relationships:
{% for f in data.generation_context.factions %}
- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.generation_context.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Generate exactly one ProposedEntity.
"""
            ),
        ],
        world_entry_generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a world-entry generation tool for a role-play simulation.

Generate exactly one ProposedWorldEntry.

Output schema:
- temp_id: temporary string ID for this proposal, for example "entry_temp_clara_suspicion". Do not use a database ID.
- scope: list of IDs that can know this entry. Use [0] for public/common knowledge, [-1] for hidden GM-only, or character IDs from present characters.
- content: one complete factual sentence. It may describe a belief or rumour, but make uncertainty explicit.
- visibility: one of "known", "suspected", "perceived", or "inferred".
- confidence: 0.0-1.0. Use less than 1.0 for rumours, suspicions, guesses, and unreliable testimony.
- narration_permission: one of "visible", "may_hint", or "invisible".
- recall_type: one of "always", "keyword", "semantic", or "chained".
- keywords: for keyword recall, provide useful keyword dicts; otherwise null.
- chained_ids: for chained recall, provide existing world entry IDs; otherwise null.
- semantic_instruction: for semantic recall, describe when this entry should be recalled; otherwise null.
- reason: why this persistent knowledge is needed.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Hard rules:
- The world entry is a pending proposal, not canonical.
- content must be a complete factual sentence, not a title.
- Do not duplicate existing world entries.
- Do not contradict canonical state.
- Do not solve major mysteries unless explicitly required.
- scope may contain only present character IDs, 0 for everyone, or -1 for hidden GM-only.
- If recall_type is KEYWORD, include useful keywords.
- If recall_type is CHAINED, include chained_ids only if known from supplied context; otherwise use SEMANTIC.
- If recall_type is SEMANTIC, include semantic_instruction.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.

World-entry quality rules:
- Use confidence below 1.0 for rumours, suspicions, guesses, or unreliable testimony.
- Use scoped character knowledge when only some characters know it.
- Use scope [0] only for public/common knowledge.
- Use scope [-1] only for hidden GM-side truth.
- Do not create a world entry for “someone noticed a person standing there” unless it must persist as memory.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate World Entry

## Goal

Your goal is:
{{ data.goal }}

This is only a guidance. You do not have to generate exactly the same content as it describes, as long as the
goal aligns. However, your proposed location must match the world style and is sensible.

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.round_number }}
Time: {{ data.generation_context.time_label }}
State summary:
{{ data.generation_context.state_summary }}

Data preset constraints:
- Entity types:
{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}
  - {{ type_name }}: {{ description }}
{% else %}
  - No custom entity types configured.
{% endfor %}
- Character attributes:
{% for attr in data.generation_context.data_preset.character_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Character stats:
{% for stat in data.generation_context.data_preset.character_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction attributes:
{% for attr in data.generation_context.data_preset.faction_attributes %}
  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }}
{% else %}
  - None.
{% endfor %}
- Faction stats:
{% for stat in data.generation_context.data_preset.faction_stats %}
  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}
{% else %}
  - None.
{% endfor %}

Current location:
{{ data.generation_context.current_location }}

Present characters:
{% for c in data.generation_context.present_characters %}
- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}
{% else %}
None.
{% endfor %}

Existing items:
{% for i in data.generation_context.existing_items %}
- {{ i.id }}: {{ i.name }} | description={{ i.description }}
{% else %}
None.
{% endfor %}

Existing equipment:
{% for e in data.generation_context.existing_equipments %}
- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}
{% else %}
None.
{% endfor %}

Relevant factions and relationships:
{% for f in data.generation_context.factions %}
- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.generation_context.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Generate exactly one ProposedWorldEntry.
"""
            ),
        ],
    )


@pytest.fixture
def mock_director_profile(inference_model) -> DirectorAgentProfile:
    return DirectorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
            context_window=65536,
        ),
        generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Director tool-gate for a multi-agent role-play simulation.

Your only job is to decide whether one or more world-generation tools are needed before final scheduling.

You may call multiple generation tools in parallel if several independent pending proposals are needed.

Use tools only when concrete unknown content is required now, such as:
- the user enters or discovers an unknown location;
- a known action exposes an unknown hidden entity;
- a container, drawer, cache, corpse, desk, shelf, or room is searched and may contain an item;
- a new persistent fact, rumour, suspicion, memory, or belief needs to be stored as a world entry;
- a concrete external event must be proposed.

Do not call tools for:
- normal conversation;
- normal observation of someone already present;
- ordinary NPC activation;
- facts already represented in current state, entities, tasks, world entries, history, or pending proposals;
- narration, atmosphere, flavour, or mood;
- deciding who acts.

When calling tools:
- provide brief generation goal to describe what to generate, for example "a normal bedroom description", but do not
  specify the content of generation. Do not say things like: "a bedroom with a double bed, a wardrobe, and a lamp".
  This is for the tool to decide.
- do not ask the tool to decide whether an action succeeds;
- generated content is pending only.

If no tool is needed, return exactly:
NO_TOOL_NEEDED

Do not output DirectorOutput.
Do not output XML.
Do not output JSON unless calling tools.

Parallel tool calls are allowed only when the generated objects are independent.

Good:
- generate_location for an unknown archive room
- generate_entity for a locked cabinet inside the already-known current room

Bad:
- generate_location and generate_item that depends on that generated location
- generate_entity and generate_item where the item is inside the generated entity

If one generated object depends on another, call only the parent object first and let a later stage request dependent generation.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Director Tool-Gate Input

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Data preset
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes/stats:
{% for attr in data.data_preset.character_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom character attributes.
{% endfor %}
{% for stat in data.data_preset.character_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom character stats.
{% endfor %}
Faction attributes/stats:
{% for attr in data.data_preset.faction_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom faction attributes.
{% endfor %}
{% for stat in data.data_preset.faction_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom faction stats.
{% endfor %}

## Current state
Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}
Scene/location ID: {{ data.state.scene }}

State summary:
{{ data.state.state }}

## User input
{{ data.user_input or "No explicit user input. Passive continuation requested." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Recent history
{{ data.state.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.state.long_term_history_summary or "No long-term history summary." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

## Current location
ID: {{ data.location.id }}
Primary: {{ data.location.primary_location }}
Detailed: {{ data.location.detailed_location }}
Scene: {{ data.location.scene }}
Description:
{{ data.location.description }}

Entities:
{% for e in data.location.entities %}
- {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Present characters
{% for c in data.present_characters %}
- {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Public state: {{ c.public_state }}
  Director-only private state: {{ c.private_state }}
{% endfor %}

## Relevant tasks
{% for t in data.relevant_tasks %}
- Task {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Goal: {{ t.goal }}
{% else %}
None.
{% endfor %}

## Recalled world entries
{% for e in data.recalled_world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Content: {{ e.content }}
{% else %}
None.
{% endfor %}

## Existing items and equipment
{% for i in data.existing_items %}
- Item {{ i.id }}: {{ i.name }} | {{ i.description }}
{% else %}
No known items.
{% endfor %}
{% for e in data.existing_equipments %}
- Equipment {{ e.id }}: {{ e.name }} | status={{ e.status }} | {{ e.description }}
{% else %}
No known equipment.
{% endfor %}

## Relevant faction context
These may include private relationships. Use only for tool-gating decisions.
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

# Decision

Call generation tools only if needed.

If no generation is needed, return exactly:
NO_TOOL_NEEDED
"""
            )
        ],
        planning_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Director/Scheduler for a multi-agent role-play simulation.

Your job:
- decide which present non-user characters should act now;
- provide internal activation reasons;
- provide resolver and narrator constraints;
- include pending generated proposals supplied in the input.

You are not the narrator.
You are not the resolver.
You do not write character briefings.
You do not decide whether actions succeed.
You do not commit world state.
You do not write exact dialogue.
You do not call tools in this phase.

Privacy rules:
- You may use private states, private tasks, and private motives for activation decisions.
- If private data influenced activation, mark private_motive_used=true.
- Do not produce text intended for character agents.
- Do not leak private reasoning into scene_focus or any text that later agents may treat as visible.
- ActivationDecision.reason and director_notes are internal only.

Scheduling rules:
- Do not activate every character by default.
- Do not activate user-controlled characters unless explicitly delegated by user input.
- If wait_for_user=true, all activation decisions should have activate=false and priority=0.
- Priority uses 0-100, where 100 is most urgent.
- If this scene cannot meaningfully continue or will stall without further user actions or input, and user did not
  provide sufficient input, prefer wait_for_user = true. Otherwise, activate the characters accordingly, do not
  wait for user. Only wait when it's genuinely not possible to proceed with the simulation.
- If a character is absent from the current scene, do not activate them.

Pending proposal rules:
- Pending generated proposals are not canonical.
- They may be referenced only as pending content for the resolver.
- Do not treat them as facts.

Return only valid DirectorOutput. The output should contain:
- Scene focus: what this scene should focus on, a directive guidance for the characters to act upon
- Activations: a list of character activation decisions with reasons and priority. If the decision is based
  their private motive, it should specify. The priority is 0-100, where 100 is most urgent. It indicates
  how likely the actor is likely to act, and how fast. The priority is not a guarantee that the actor will
  actually act or act first, just a tendency. It should also include a reason for the decision.
- If a character should not be activated, still include them in the activations list, but mark their activation
  as false, priority as 0, and provide the reason for not activating.
- Whether to wait for the user, and the reason to wait for user, instead of progressing the scene.
- Extra notes to mark some important decisions or reasons for audit. Can be empty.

Schema fields:
- scene_focus: concise instruction for what this scene is about now.
- activations: one ActivationDecision for each present character considered.
- ActivationDecision.character_id: existing character ID.
- ActivationDecision.character_name: matching character name.
- ActivationDecision.activate: true if this character should produce an action this turn.
- ActivationDecision.priority: integer from 0 to 100. Use 0 when activate=false.
- ActivationDecision.reason: internal reason for the activation decision.
- ActivationDecision.private_motive_used: true only if private state/tasks affected the decision.
- wait_for_user: true only when the scene should pause for player input instead of NPC action.
- reason_to_wait: required when wait_for_user=true; otherwise null.
- director_notes: internal audit notes, or "" if none.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Director Final Scheduling Input

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Data preset
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes/stats:
{% for attr in data.data_preset.character_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom character attributes.
{% endfor %}
{% for stat in data.data_preset.character_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom character stats.
{% endfor %}
Faction attributes/stats:
{% for attr in data.data_preset.faction_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom faction attributes.
{% endfor %}
{% for stat in data.data_preset.faction_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom faction stats.
{% endfor %}

## Current state
Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}
Scene/location ID: {{ data.state.scene }}

State summary:
{{ data.state.state }}

## User input
{{ data.user_input or "No explicit user input. Passive continuation requested." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Recent history
{{ data.state.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.state.long_term_history_summary or "No long-term history summary." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

## Current location
ID: {{ data.location.id }}
Primary: {{ data.location.primary_location }}
Detailed: {{ data.location.detailed_location }}
Scene: {{ data.location.scene }}
Description:
{{ data.location.description }}

Entities:
{% for e in data.location.entities %}
- {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Present characters
{% for c in data.present_characters %}
- {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Director-only private state: {{ c.private_state }}
  Location: {{ c.location }}
{% endfor %}

## Recalled world entries
{% for e in data.recalled_world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
  Content: {{ e.content }}
{% else %}
None.
{% endfor %}

## Existing items and equipment
{% for i in data.existing_items %}
- Item {{ i.id }}: {{ i.name }}
  Description: {{ i.description }}
  Quality: {{ i.quality }}
  Quantity: {{ i.quantity }}
{% else %}
No known items.
{% endfor %}
{% for e in data.existing_equipments %}
- Equipment {{ e.id }}: {{ e.name }}
  Status: {{ e.status }}
  Quality: {{ e.quality }}
  Description: {{ e.description }}
{% else %}
No known equipment.
{% endfor %}

## Relevant faction context
These may include private relationships. Use for scheduling, but do not leak private relationship details into scene_focus.
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
  Attributes: {{ f.attributes }}
  Stats: {{ f.stats }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Relevant tasks
These may include private tasks. Use them only for scheduling.
{% for t in data.relevant_tasks %}
- Task {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Type: {{ t.type }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
  Source: {{ t.source }}
{% else %}
None.
{% endfor %}

## Pending generated proposals
These are pending and non-canonical.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required output

Produce DirectorOutput only.

Do not write character briefings.
Do not leak private information into narrator constraints.
Do not activate user-controlled characters unless explicitly delegated.
"""
            )
        ]
    )


@pytest.fixture
def mock_memory_agent_profile(inference_model) -> MemoryAgentProfile:
    return MemoryAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
            context_window=65536,
        ),
        briefing_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Briefing Builder for a multi-agent role-play simulation.

Your job:
- build compact, safe context briefings for selected character agents;
- include only information available in the supplied input;
- avoid chat-history dependence by summarising the immediate situation.

You are not the character.
You are not the narrator.
You are not the resolver.
You do not decide whether actions succeed.
You do not add new world facts.

Privacy rules:
- The supplied context has already been filtered.
- Do not infer hidden motives beyond the supplied safe data.
- Do not include information belonging to another character unless it is public or explicitly supplied as safe.

Briefing rules:
- Build one briefing per requested character. Each character must have a briefing.
- Keep each briefing compact but complete enough that the character agent does not need chat history.
- The briefing should orient the character to the scene, recent situation, known facts, immediate pressure, and possible focus.
- Do not write exact dialogue.

Return only BriefingOutput.

Output schema:
- briefings: one CharacterBriefing for each requested character.
- CharacterBriefing.character_id: existing requested character ID.
- CharacterBriefing.character_name: matching character name.
- CharacterBriefing.scene_context: stable scene context visible/known to the character.
- CharacterBriefing.recent_context: compact recent events relevant to this character.
- CharacterBriefing.known_relevant_facts: facts this character may safely know.
- CharacterBriefing.immediate_situation: what is happening right now from this character's perspective.
- CharacterBriefing.instruction: short action guidance from the Director focus.
- CharacterBriefing.available_interactions: concrete available interactions from scene/entity context.
- CharacterBriefing.relevant_task_ids: supplied task IDs relevant to this character.
- CharacterBriefing.relevant_world_entry_ids: supplied world entry IDs relevant to this character.
- CharacterBriefing.constraints: limits the character agent must respect.
- notes: optional internal notes, or "".
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Briefing Builder Input

## Requested characters
{% for c in data.characters %}
- {{ c.id }}: {{ c.name }}
{% else %}
None.
{% endfor %}

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Public data preset descriptions
Use these only to interpret existing attributes, stats, and entity types in safe context.
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes/stats:
{% for attr in data.data_preset.character_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom character attributes.
{% endfor %}
{% for stat in data.data_preset.character_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom character stats.
{% endfor %}
Faction attributes/stats:
{% for attr in data.data_preset.faction_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom faction attributes.
{% endfor %}
{% for stat in data.data_preset.faction_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom faction stats.
{% endfor %}

## Current state
Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}

State summary:
{{ data.state.state }}

## User input
{{ data.user_input or "No explicit user input." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Recent public history summary
{{ data.state.recent_history_summary or "No recent public history summary." }}

## Long-term public history summary
{{ data.state.long_term_history_summary or "No long-term public history summary." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

## Current location
Location ID: {{ data.location.id }}
Primary location: {{ data.location.primary_location }}
Detailed location: {{ data.location.detailed_location }}
Scene: {{ data.location.scene }}

Description:
{{ data.location.description }}

Entities:
{% for entity in data.location.entities %}
- Entity {{ entity.id }}: {{ entity.name }}
  Type: {{ entity.type }}
  Description: {{ entity.description }}
  Status: {{ entity.status }}
  Interactions: {{ entity.interactions | join(", ") }}
{% else %}
No notable entities.
{% endfor %}

## Safe character data
{% for c in data.characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% endfor %}

## Safe world entries
{% for e in data.world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Content: {{ e.content }}
{% else %}
No safe world entries.
{% endfor %}

## Safe tasks
{% for t in data.tasks %}
- Task {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Type: {{ t.type }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
  Source: {{ t.source }}
{% else %}
No safe tasks.
{% endfor %}

## Public faction context
Only public faction relationships are provided here. Treat private faction ties as unknown unless they are explicitly present in the character's safe world entries.
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
{% else %}
No public relevant factions.
{% endfor %}
{% for r in data.faction_relationships %}
- Public relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
{% else %}
No public relevant faction relationships.
{% endfor %}

## Pending generated proposals
These are not canonical facts. Mention only if relevant as pending/possible context.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required output

Build safe briefings for the requested characters only. Produce the final BriefingOutput.
"""
            ),
        ],
    )


@pytest.fixture
def mock_character_agent_profile(inference_model) -> CharacterAgentProfile:
    return CharacterAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
        ),
        action_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a character decision agent in a multi-agent role-play simulation.

You act only as the specified character.

Your job:
- decide what this character attempts to do now;
- express the action as structured intent;
- use the character's personality, state, goals, memories, knowledge, and current perception.

You are not the narrator.
You are not the resolver.
You do not decide whether the action succeeds.
You do not write final prose.
You do not control other characters.
You do not reveal information the character would not express or act upon.

Knowledge rules:
- You may use the character's own private state, own tasks, own inventory, and own scoped world entries.
- You may use public/visible scene information.
- You must not assume hidden facts that are not supplied.
- If you use private knowledge to motivate the action, set uses_private_knowledge=true and explain it only in private_reason_for_system.
- Do not put private motives into visible_behavior unless the character intentionally reveals them.

Action rules:
- Choose one primary action.
- The action should be plausible for the character now.
- Prefer behaviour over exposition.
- Do not write exact dialogue unless the action requires a short phrase; use spoken_intent to express meaning.
- If the character would stay still, observe, or wait, output action_type="wait" or "observe".
- Do not force confrontation unless the character has enough reason.
- Do not solve conflicts; the resolver will decide ordering and outcome.

Return only CharacterActionOutput.

Output schema:
- character_id: the acting character ID.
- character_name: the acting character name.
- intent: the character's immediate goal in plain language.
- action_type: one of speak, move, inspect, manipulate_entity, use_item, give_item, take_item, observe, wait, leave_scene, custom.
- target_character_ids: IDs of characters directly targeted, or [].
- target_entity_ids: IDs of entities directly targeted, or [].
- target_location_id: destination location ID for movement, or null.
- target_item_ids: IDs of inventory/world items directly used or targeted, or [].
- method: how the character attempts the action.
- visible_behavior: what other characters can observe.
- spoken_intent: short meaning of any speech, or null.
- urgency: 0-100, how quickly the character tries to act.
- persistence: 0-100, how hard the character keeps trying if resisted or delayed.
- expected_outcome: what the character hopes will happen, not a guaranteed result.
- fallback_if_blocked: backup attempt if the action cannot proceed, or null.
- uses_private_knowledge: true if private state, private tasks, or scoped facts motivated the action.
- private_reason_for_system: private explanation when uses_private_knowledge=true; otherwise null.
- constraints_for_resolver: facts or limits the resolver should respect.
- notes: optional internal notes, or "".
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Character Action Input

## Acting character
ID: {{ data.character.id }}
Name: {{ data.character.name }}
User controlled: {{ data.character.user_controlled }}
Description:
{{ data.character.description }}
Appearance:
{{ data.character.appearance }}
Public state:
{{ data.character.public_state }}
Private state:
{{ data.character.private_state }}
Current location ID: {{ data.character.location }}

## Data preset descriptions
Use these to interpret custom attributes, stats, and entity types. Do not update state here.
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes/stats:
{% for attr in data.data_preset.character_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | meaning={{ attr.creation_instruction }} | update meaning={{ attr.update_instruction }}
{% else %}
No custom character attributes.
{% endfor %}
{% for stat in data.data_preset.character_stats %}
- Stat {{ stat.name }} | meaning={{ stat.creation_instruction }} | update meaning={{ stat.update_instruction }}
{% else %}
No custom character stats.
{% endfor %}
Faction attributes/stats:
{% for attr in data.data_preset.faction_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | meaning={{ attr.creation_instruction }} | update meaning={{ attr.update_instruction }}
{% else %}
No custom faction attributes.
{% endfor %}
{% for stat in data.data_preset.faction_stats %}
- Stat {{ stat.name }} | meaning={{ stat.creation_instruction }} | update meaning={{ stat.update_instruction }}
{% else %}
No custom faction stats.
{% endfor %}

## Briefing
Scene context:
{{ data.briefing.scene_context }}

Recent context:
{{ data.briefing.recent_context }}

Known relevant facts:
{{ data.briefing.known_relevant_facts }}

Immediate situation:
{{ data.briefing.immediate_situation }}

Instruction:
{{ data.briefing.instruction }}

Available interactions:
{% for interaction in data.briefing.available_interactions %}
- {{ interaction }}
{% else %}
None specified.
{% endfor %}

Briefing constraints:
{% for constraint in data.briefing.constraints %}
- {{ constraint }}
{% else %}
None.
{% endfor %}

## Current location
ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}
Description:
{{ data.current_location.description }}

Entities:
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Visible other characters
{% for c in data.visible_characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% else %}
None.
{% endfor %}

## Relevant tasks
{% for t in data.tasks %}
- Task {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Type: {{ t.type }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
  Source: {{ t.source }}
{% else %}
None.
{% endfor %}

## Relevant world entries
{% for e in data.world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
  Content: {{ e.content }}
{% else %}
None.
{% endfor %}

## Relevant faction context
This includes public faction context visible in the scene plus private faction relationships involving {{ data.character.name }} or their inventory. Do not reveal private ties in visible_behavior unless the character intentionally exposes them.
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
  Attributes: {{ f.attributes }}
  Stats: {{ f.stats }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Inventory
{% for i in data.inventory %}
- Item {{ i.id }}: {{ i.name }}
  Quality: {{ i.quality }}
  Quantity: {{ i.quantity }}
  Description: {{ i.description }}
{% else %}
No inventory items.
{% endfor %}

## Equipment
{% for e in data.equipments %}
- Equipment {{ e.id }}: {{ e.name }}
  Status: {{ e.status }}
  Quality: {{ e.quality }}
  Description: {{ e.description }}
{% else %}
No equipment.
{% endfor %}

## Pending generated proposals
These are pending and non-canonical. Treat them only as possible content if the briefing makes them relevant.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## User input
{{ data.user_input or "No explicit user input." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required output

Choose exactly one plausible action for {{ data.character.name }} now.

Return only CharacterActionOutput.
"""
            )
        ],
        reaction_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a character reaction agent in a multi-agent role-play simulation.

You act only as the specified character.

This is a reaction pass after your previous action failed, was blocked, delayed, or only partially succeeded.

Your job:
- understand what you attempted;
- understand why it failed or was blocked;
- react plausibly based on what your character can perceive and know;
- produce one new attempted action.

You are not the narrator.
You are not the resolver.
You do not decide whether the new action succeeds.
You do not control other characters.
You do not rewrite already resolved events.
You do not undo another character's successful action.

Fixed-event rules:
- Events listed as fixed visible events already happened.
- You may react to them.
- You may not contradict them.
- You may not prevent them retroactively.
- Your new action must start from the changed scene state.

Retry rules:
- This is a limited reaction opportunity, not a full new turn.
- Prefer a direct adjustment, fallback, response to being blocked, or withdrawal.
- Do not repeat the exact same failed action unless there is a clearly different method.
- If the sensible response is to stop, observe, or wait, output action_type="wait" or "observe".
- This is the final retry for this character this round.

Knowledge rules:
- Use only your own private state, own tasks, own recalled world entries, and visible/fixed events.
- Do not assume hidden reasons for other characters' actions unless supplied.
- If private knowledge motivates your reaction, set uses_private_knowledge=true and explain it only in private_reason_for_system.

Return only CharacterActionOutput.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Character Reaction Input

## Acting character
ID: {{ data.character.id }}
Name: {{ data.character.name }}
Gender: {{ data.character.gender }}
Age: {{ data.character.age }}

Description:
{{ data.character.description }}

Appearance:
{{ data.character.appearance }}

Public state:
{{ data.character.public_state }}

Private state:
{{ data.character.private_state }}

Location: {{ data.character.location }}

Attributes:
{% for key, values in data.character.attributes.items() %}
- {{ key }}: {{ values | join(", ") }}
{% else %}
None.
{% endfor %}

Stats:
{% for key, value in data.character.stats.items() %}
- {{ key }}: {{ value }}
{% else %}
None.
{% endfor %}

## Original attempted action
Intent:
{{ data.reaction_context.original_action.intent }}

Action type:
{{ data.reaction_context.original_action.action_type }}

Method:
{{ data.reaction_context.original_action.method }}

Visible behaviour:
{{ data.reaction_context.original_action.visible_behavior }}

Spoken intent:
{{ data.reaction_context.original_action.spoken_intent or "None." }}

Expected outcome:
{{ data.reaction_context.original_action.expected_outcome }}

Fallback if blocked:
{{ data.reaction_context.original_action.fallback_if_blocked or "None." }}

## Failure / block reason
Failed action summary:
{{ data.reaction_context.failure_record.failed_action_summary }}

Reason:
{{ data.reaction_context.failure_record.reason }}

Retry context:
{{ data.reaction_context.failure_record.retry_context or "No additional retry context." }}

## Fixed visible events
These already happened and cannot be undone.
{% for event in data.reaction_context.fixed_visible_events %}
- {{ event }}
{% else %}
None.
{% endfor %}

## Private realisations for this character
{% for event in data.reaction_context.fixed_private_events_for_actor %}
- {{ event }}
{% else %}
None.
{% endfor %}

## Changed scene context
{{ data.reaction_context.changed_scene_context }}

## Immediate failure context
{{ data.reaction_context.immediate_failure_context }}

## Retry limit
Retry number: {{ data.reaction_context.retry_number }}
Maximum retries this round: {{ data.reaction_context.max_retries_this_round }}

Allowed reaction scope:
{{ data.reaction_context.allowed_reaction_scope }}

Reaction constraints:
{% for c in data.reaction_context.constraints %}
- {{ c }}
{% else %}
None.
{% endfor %}

## Current location
Location ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}

Description:
{{ data.current_location.description }}

Entities:
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
No visible entities.
{% endfor %}

## Visible characters
{% for c in data.visible_characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% else %}
No visible characters.
{% endfor %}

## Tasks
{% for t in data.tasks %}
- Task {{ t.id }}
  Private: {{ t.private }}
  Priority: {{ t.priority }}
  Status: {{ t.status }}
  Type: {{ t.type }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
  Source: {{ t.source }}
{% else %}
No active tasks.
{% endfor %}

## Recalled world entries
{% for e in data.world_entries %}
- Entry {{ e.id }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Content: {{ e.content }}
{% else %}
No recalled world entries.
{% endfor %}

## Inventory
{% for item in data.inventory %}
- Item {{ item.id }}: {{ item.name }}
  Description: {{ item.description }}
  Quantity: {{ item.quantity }}
  Quality: {{ item.quality }}
{% else %}
No items.
{% endfor %}

## Equipment
{% for eq in data.equipments %}
- Equipment {{ eq.id }}: {{ eq.name }}
  Description: {{ eq.description }}
  Status: {{ eq.status }}
  Quality: {{ eq.quality }}
{% else %}
No equipment.
{% endfor %}

## Factions
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}

## Faction relationships
{% for r in data.faction_relationships %}
- {{ r }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Pending generated proposals
These are not canonical facts.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## User input
{{ data.user_input or "No explicit user input." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required output

Produce one CharacterActionOutput representing this character's reaction.

Do not repeat the same failed action unless the method or target changes.
Do not contradict fixed events.
Do not decide success.
"""
            ),
        ],
    )


@pytest.fixture
def mock_resolver_agent_profile(inference_model) -> ResolverAgentProfile:
    return ResolverAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
        ),
        resolve_character_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Resolver for a multi-agent role-play simulation.

Your job:
- evaluate attempted character actions;
- determine ordering;
- detect conflicts;
- decide whether actions succeed, partially succeed, fail, or are blocked;
- produce structured event results.

This is role-play resolution, not a tabletop rules engine.
Use reasonable fictional causality, character positioning, timing, attention, and available objects.

You are not the narrator.
You do not write literary prose.
You do not decide future character actions.
You do not mutate canonical state directly.
You do not invent major new facts unless they are already supplied as pending proposals.

Resolution rules:
- Higher-priority actors generally act earlier.
- A lower-priority action may still complete if it does not conflict.
- If two actions require the same exclusive target, item, position, or attention, mark a conflict.
- If an action depends on unavailable knowledge, unavailable item, wrong location, or impossible timing, mark it failed or invalid.
- If an action is plausible but interrupted, mark it partially_succeeded, blocked, or delayed.
- Do not assume user-controlled character responses unless explicitly supplied.
- Do not generate exact dialogue.
- visible_result should describe observable outcome in plain event terms.
- private_result_for_actor may describe what the actor privately realises or fails to achieve.

Retry rules:
- If a character failed due to conflict, interruption, or blocked access, add them to failed_characters.
- Set requires_actor_retry=true only when a retry/revision pass is useful.
- Do not trigger infinite retries. One retry pass per character per round is assumed.

Pending generation rules:
- Pending generated proposals are not canonical.
- You may accept, reject, or defer them by suggesting state updates.
- Do not treat them as existing unless an action successfully reveals or uses them.

Return only ResolverOutput.

Output schema:
- accepted: false only when the action set cannot be resolved coherently at all.
- rejection_reason: reason when accepted=false; otherwise null.
- resolved_actions: one ResolvedAction for each attempted character action.
- ResolvedAction.actor_id / actor_name: acting character.
- ResolvedAction.original_intent: copied or summarized from the attempted action.
- ResolvedAction.final_status: succeeded, partially_succeeded, failed, blocked, delayed, invalid, or cancelled.
- ResolvedAction.resolved_order: 1-based action order when ordering matters; otherwise null.
- ResolvedAction.visible_result: observable result in plain event terms.
- ResolvedAction.private_result_for_actor: private realization/result for that actor, or null.
- ResolvedAction.failure_reason: required for failed, blocked, invalid, or cancelled actions; otherwise null.
- ResolvedAction.blocking_actor_id / blocking_entity_id: IDs that blocked the action, or null.
- ResolvedAction.state_change_hints: concise hints for persistent state changes.
- ResolvedAction.world_entry_hints: concise hints for persistent memories/facts.
- ResolvedAction.requires_actor_retry: true only if another action attempt is useful this round.
- ResolvedAction.retry_instruction: instruction for retry, or null.
- conflicts: any meaningful conflicts between actions.
- failed_characters: characters whose action failed and may need a retry.
- scene_result_summary: concise internal summary of what happened.
- next_round_note: guidance for the next Director turn.
- narrator_context: facts the eventual narrator may use without adding new outcomes.
- state_update_suggestions: state changes for the committer to consider.
- pending_world_entry_suggestions: persistent facts or memories the committer should consider.
- requires_director_rerun: true only if scheduling must be redone.
- director_rerun_reason: reason when requires_director_rerun=true; otherwise null.
- notes: optional internal notes, or "".
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Normal Resolver Input

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Data preset descriptions
Use these to interpret custom attributes, stats, entity types, and action plausibility.
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes/stats:
{% for attr in data.data_preset.character_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom character attributes.
{% endfor %}
{% for stat in data.data_preset.character_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom character stats.
{% endfor %}
Faction attributes/stats:
{% for attr in data.data_preset.faction_attributes %}
- Attribute {{ attr.name }} | values={{ attr.values or "open" }} | update={{ attr.update_instruction }}
{% else %}
No custom faction attributes.
{% endfor %}
{% for stat in data.data_preset.faction_stats %}
- Stat {{ stat.name }} | update={{ stat.update_instruction }}
{% else %}
No custom faction stats.
{% endfor %}

## Current state
Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}
State summary:
{{ data.state.state }}

## Current location
ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}
Description:
{{ data.current_location.description }}

## Visible entities
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Present characters
{% for c in data.characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Private state: {{ c.private_state }}
  Location: {{ c.location }}
{% endfor %}

## Character attempted actions
{% for a in data.character_actions %}
- Actor {{ a.character_id }}: {{ a.character_name }}
  Intent: {{ a.intent }}
  Action type: {{ a.action_type }}
  Targets characters: {{ a.target_character_ids }}
  Targets entities: {{ a.target_entity_ids }}
  Target location: {{ a.target_location_id }}
  Target items: {{ a.target_item_ids }}
  Method: {{ a.method }}
  Visible behaviour: {{ a.visible_behavior }}
  Spoken intent: {{ a.spoken_intent }}
  Urgency: {{ a.urgency }}
  Persistence: {{ a.persistence }}
  Expected outcome: {{ a.expected_outcome }}
  Fallback if blocked: {{ a.fallback_if_blocked }}
  Constraints for resolver:
  {% for c in a.constraints_for_resolver %}
  - {{ c }}
  {% endfor %}
{% else %}
No character actions.
{% endfor %}

## Inventory by character
{% for character_id, inventory in data.inventory.items() %}
- Character {{ character_id }}
  Items:
  {% for item in inventory.items %}
  - {{ item.id }}: {{ item.name }} | quantity={{ item.quantity }} | quality={{ item.quality }}
  {% else %}
  None.
  {% endfor %}
  Equipment:
  {% for equipment in inventory.equipments %}
  - {{ equipment.id }}: {{ equipment.name }} | status={{ equipment.status }} | quality={{ equipment.quality }}
  {% else %}
  None.
  {% endfor %}
{% else %}
None.
{% endfor %}

## Priority guidance
Higher urgency usually acts earlier. Persistence indicates how much an actor keeps trying if interrupted.

## Recalled resolver-safe world entries
{% for e in data.world_entries %}
- Entry {{ e.id }}: {{ e.content }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
{% else %}
None.
{% endfor %}

## Relevant faction context
These relationships may include private system-side context for resolving action plausibility. Use them to judge access, allegiance, and conflicts, but do not invent new faction facts.
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
  Attributes: {{ f.attributes }}
  Stats: {{ f.stats }}
{% else %}
No relevant factions.
{% endfor %}
{% for r in data.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Pending generated proposals
These are not canonical.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## Recent history
{{ data.state.recent_history_summary or "No recent history summary." }}

## Last narration
{{ data.last_narration or "No last narration." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required resolution

Resolve the attempted actions.

Detect conflicts, failures, blocked actions, and invalid assumptions.
Return ResolverOutput.
"""
            )
        ],
        resolve_reaction_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Resolver for a second-pass character reaction in a multi-agent role-play simulation.

A previous resolver pass already produced fixed resolved actions.
Some characters failed, were blocked, or were delayed.
Those characters have now produced reaction actions.

Your job:
- resolve only the supplied reaction actions;
- respect previous resolved actions as fixed truth;
- detect whether the reaction succeeds, partially succeeds, fails, is blocked, or is invalid;
- output the same ResolverOutput schema used by normal resolution.

You are not the narrator.
You do not write literary prose.
You do not mutate canonical state.
You do not re-resolve successful fixed actions.
You do not undo previous successful actions.

Second-pass rules:
- Fixed resolved actions already happened and cannot be undone.
- Reaction actions start after or during the consequences of those fixed actions.
- If a reaction conflicts with fixed truth, mark it failed or invalid.
- This is the final retry for these characters this round.
- If a reaction fails again, set requires_actor_retry=false.
- Do not request another retry.

Resolution rules:
- Use reasonable fictional causality.
- Do not assume user-controlled character responses unless explicitly supplied.
- Do not generate exact dialogue.
- visible_result should describe observable event outcome in plain terms.
- private_result_for_actor may describe what the actor privately realises.

Return only ResolverOutput with mode="normal_action_resolution".
""",
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Reaction Resolver Input

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Current state
Round: {{ data.state.round_number }}
Time: {{ data.state.time_label }}
State summary:
{{ data.state.state }}

## Current location
ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}
Description:
{{ data.current_location.description }}

Entities:
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Present characters
{% for c in data.characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% endfor %}

## Previous resolver output
These actions/conflicts are already resolved.
{{ data.previous_resolver_output }}

## Reaction actions to resolve
Resolve only these actions.
{% for a in data.reaction_actions %}
- Actor {{ a.character_id }}: {{ a.character_name }}
  Intent: {{ a.intent }}
  Action type: {{ a.action_type }}
  Targets characters: {{ a.target_character_ids }}
  Targets entities: {{ a.target_entity_ids }}
  Target location: {{ a.target_location_id }}
  Target items: {{ a.target_item_ids }}
  Method: {{ a.method }}
  Visible behaviour: {{ a.visible_behavior }}
  Spoken intent: {{ a.spoken_intent }}
  Urgency: {{ a.urgency }}
  Persistence: {{ a.persistence }}
  Expected outcome: {{ a.expected_outcome }}
  Fallback if blocked: {{ a.fallback_if_blocked }}
  Uses private knowledge: {{ a.uses_private_knowledge }}
  Constraints for resolver:
  {% for c in a.constraints_for_resolver %}
  - {{ c }}
  {% else %}
  None.
  {% endfor %}
{% else %}
No reaction actions supplied.
{% endfor %}

## Retry constraints
Second pass: {{ data.round_constraints.second_pass }}
Retrying character IDs: {{ data.round_constraints.retrying_character_ids }}
No more retries after this: {{ data.round_constraints.no_more_retries_after_this }}

## Inventory
{{ data.inventory }}

## World entries
{% for e in data.world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Content: {{ e.content }}
{% else %}
No resolver-safe world entries.
{% endfor %}

## Factions
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
{% else %}
No relevant factions.
{% endfor %}

## Faction relationships
{% for r in data.faction_relationships %}
- {{ r }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Pending generated proposals
These are not canonical.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required resolution

Resolve the reaction actions only.

Return ResolverOutput.
Do not request further retries.
"""
            ),
        ],
        resolve_user_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the User Input Resolver for a role-play simulation.

Your job:
- inspect the user's freeform input before the Director runs;
- decide whether the input is acceptable, needs rewriting, or should be rejected;
- convert valid user-described actions into resolved/accepted action records using the shared ResolverOutput format.

This mode does not resolve NPC agent actions.
This mode checks whether the user's declared action is legal and coherent.

Assumption:
- The user usually means well.
- Prefer preserving user intent.
- Do not over-police style.
- In permissive mode, accept most plausible input.
- In strict mode, reject or rewrite direct control of NPCs, impossible outcomes, or unsupported world-state assertions.

You are not the narrator.
You do not write prose.
You do not decide hidden discoveries unless the input only attempts to discover them.
You do not generate new canonical facts.
You do not force NPC reactions.

Validation rules:
- The user may control the player character.
- The user may not directly decide another character's internal state, success, failure, or exact reaction.
- The user may attempt actions, but cannot guarantee outcomes.
- The user may describe tone, posture, speech intent, movement, and interaction attempts.
- If the user says they find/open/reveal unknown content, convert it into an attempt; do not confirm the discovery.
- If the user asserts an impossible or unsupported fact, reject or rewrite that part.
- If part of the input is valid and part is invalid, accept the valid part and mark the invalid part in rejection_reason or notes.

Output rules:
- If accepted=false, explain why in rejection_reason.
- If accepted=true, produce one or more resolved_actions representing accepted user attempts.
- For valid attempts, final_status should normally be "succeeded" only for trivial positioning or speech preparation.
- For uncertain outcomes, use "delayed" or "partially_succeeded" and state that later resolver/director stages should handle outcome.

Return only ResolverOutput. Do not include a mode field.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# User Input Resolver Input

## Simulation
{{ data.simulation }}

## Current state
{{ data.state }}

## Current location
{{ data.current_location }}

## Player character
{{ data.player_character }}

## Present characters
{{ data.present_characters }}

## Visible entities
{{ data.visible_entities }}

## Player inventory
{{ data.player_inventory }}

## Player tasks
{{ data.player_tasks }}

## Player world entries
{{ data.player_world_entries }}

## User input
{{ data.user_input }}

## Last narration
{{ data.last_narration or "No last narration." }}

## Recent history
{{ data.recent_history_summary or "No recent history summary." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

## Strictness
{{ data.strictness }}

# Required output

Validate the user's input as player intent. Preserve valid intent, reject only impossible or unauthorized assertions, and return ResolverOutput only.
"""
            ),
        ],
    )


@pytest.fixture
def mock_committer_agent_profile(inference_model) -> CommitterAgentProfile:
    return CommitterAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
        ),
        mutation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the sandbox Committer Agent for a role-play simulation.

Your job is to apply state changes to a sandboxed in-memory copy of the world using tools.

You are the final LLM stage that can affect state before narration.
You do not write narration.
You do not write prose for the user.
You do not modify the real database.
You only call sandbox mutation tools.

ResolverOutput is authoritative:
- Apply successful and partially successful resolved actions.
- Do not apply failed, blocked, invalid, cancelled, or rejected actions except as failed attempts, changed attitudes, or persistent memories when appropriate.
- Do not reinterpret success or failure.
- Do not change outcomes.

Mutation rules:
- Every turn should update SimulationState.state to reflect progress.
- Prefer minimal precise changes.
- Use status updates instead of deletion for narrative state changes.
- DataPreset is authoritative for custom attributes, stats, and entity types.
- When creating character or faction attributes/stats, follow each preset creation_instruction and required universal fields.
- When updating character or faction attributes/stats, follow each preset update_instruction and allowed values.
- Do not invent custom attribute/stat keys outside DataPreset unless a resolved event clearly requires a one-off freeform field.
- Entity type values must match DataPreset.entity_types exactly when creating or updating entities.
- Do not delete characters because they die, leave, vanish, or become inactive.
- If a character dies, update the character state and create/mark a body/entity if appropriate.
- If an entity becomes an inventory item, update the entity status and update the inventory.
- If a pending generated proposal becomes real, accept it and create/update the corresponding canonical object.
- If a pending generated proposal is not confirmed, reject or defer it.
- Create world entries for persistent facts, memories, rumours, discoveries, or changed knowledge that should be recalled later.
- Create or update tasks when resolved events create, advance, pause, or complete goals.
- If unsure, prefer no mutation and leave a note through validation later.

Incremental loop rules:
- This is one mutation pass.
- Look at the current sandbox state and mutation log.
- Add missing changes only.
- You may refine a previous change by applying another update to the same object.
- Do not attempt to erase the mutation log.
- Do not call tools if nothing else needs to change.

Use tools only.
If no more mutations are needed, respond with no tool calls.

Tool-use contract:
- Use sandbox mutation tools only; do not return structured text in this pass.
- Every tool reason should cite the resolver event or pending proposal that requires the mutation.
- Do not create broad rewrites when a precise update is enough.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Committer Mutation Pass

Mutation round: {{ data.mutation_round }} / {{ data.max_mutation_rounds }}

## User input
{{ data.user_input or "No user input." }}

## Director output
{{ data.director_output }}

## Briefing output
{{ data.briefing_output }}

## Character actions
{{ data.character_actions }}

## Resolver output
{{ data.resolver_output }}

## Pending generated proposals
{{ data.pending_generated_proposals }}

## Data preset constraints
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}

Character attributes:
{% for attr in data.data_preset.character_attributes %}
- {{ attr.name }}
  Universal: {{ attr.universal }}
  Allowed values: {{ attr.values or "open" }}
  Creation instruction: {{ attr.creation_instruction }}
  Update instruction: {{ attr.update_instruction }}
{% else %}
None.
{% endfor %}

Character stats:
{% for stat in data.data_preset.character_stats %}
- {{ stat.name }}
  Universal: {{ stat.universal }}
  Creation instruction: {{ stat.creation_instruction }}
  Update instruction: {{ stat.update_instruction }}
{% else %}
None.
{% endfor %}

Faction attributes:
{% for attr in data.data_preset.faction_attributes %}
- {{ attr.name }}
  Universal: {{ attr.universal }}
  Allowed values: {{ attr.values or "open" }}
  Creation instruction: {{ attr.creation_instruction }}
  Update instruction: {{ attr.update_instruction }}
{% else %}
None.
{% endfor %}

Faction stats:
{% for stat in data.data_preset.faction_stats %}
- {{ stat.name }}
  Universal: {{ stat.universal }}
  Creation instruction: {{ stat.creation_instruction }}
  Update instruction: {{ stat.update_instruction }}
{% else %}
None.
{% endfor %}

## Current sandbox state
{{ data.current_sandbox_state }}

## Mutation log so far
{{ data.mutation_log }}

## Previous validation
{{ data.previous_validation or "No previous validation." }}

## Previous tool results
{{ data.previous_tool_results or "No previous tool results." }}

# Task

Apply any missing sandbox state changes using tools.

Do not narrate.
Do not explain unless needed inside tool reason fields.
If no changes are needed, make no tool calls.
"""
            ),
        ],
        validation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the sandbox Committer Validator.

Your job is to inspect:
- what happened this turn;
- the current sandbox state;
- the mutation log.

Decide whether the state changes are complete and consistent.

You do not call tools.
You do not mutate state.
You do not write narration.
You only return CommitterValidationOutput.

Validation rules:
- ResolverOutput is authoritative.
- Successful and partially successful actions should be reflected in sandbox state where persistent.
- Failed/blocked/invalid actions should not be over-applied.
- Every turn should update SimulationState.state.
- DataPreset is authoritative for custom attributes, stats, and entity types.
- Created or updated character/faction attributes and stats should obey DataPreset creation/update instructions.
- Universal preset attributes/stats should be present when new character/faction objects are created.
- Entity type values should match DataPreset.entity_types exactly.
- Pending generated proposals should be accepted, rejected, or deferred if relevant.
- Persistent discoveries, memories, rumours, changed knowledge, or important events should have world-entry suggestions or actual mutations.
- Character public/private states should reflect meaningful social, physical, or investigative changes.
- Entity/item/location/task changes should be present when resolved events require them.
- Avoid over-mutating for trivial flavour.

If more changes are needed, set needs_more_changes=true and describe them.
If complete, set complete=true and needs_more_changes=false.

Output schema:
- complete: true only when no required state changes are missing.
- needs_more_changes: true when another mutation pass should run.
- missing_changes: required mutations that are absent.
- questionable_changes: mutations that may be wrong, excessive, or inconsistent.
- consistency_notes: observations about consistency and state quality.
- next_instruction: concise instruction for the next mutation pass, or null.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Committer Validation Pass

## User input
{{ data.user_input or "No user input." }}

## Character actions
{{ data.character_actions }}

## Resolver output
{{ data.resolver_output }}

## Pending generated proposals
{{ data.pending_generated_proposals }}

## Data preset constraints
Entity types:
{% for type_name, description in data.data_preset.entity_types.items() %}
- {{ type_name }}: {{ description }}
{% else %}
None.
{% endfor %}
Character attributes:
{% for attr in data.data_preset.character_attributes %}
- {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }} | update={{ attr.update_instruction }}
{% else %}
None.
{% endfor %}
Character stats:
{% for stat in data.data_preset.character_stats %}
- {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }} | update={{ stat.update_instruction }}
{% else %}
None.
{% endfor %}
Faction attributes:
{% for attr in data.data_preset.faction_attributes %}
- {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or "open" }} | creation={{ attr.creation_instruction }} | update={{ attr.update_instruction }}
{% else %}
None.
{% endfor %}
Faction stats:
{% for stat in data.data_preset.faction_stats %}
- {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }} | update={{ stat.update_instruction }}
{% else %}
None.
{% endfor %}

## Current sandbox state
{{ data.current_sandbox_state }}

## Mutation log
{{ data.mutation_log }}

## Tool results this pass
{{ data.tool_results or "No tool calls were made this pass." }}

# Required output

Return CommitterValidationOutput.
"""
            ),
        ],
        final_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the sandbox Committer Finalizer.

Your job is to summarize the final sandbox state and mutation log after validation.

You do not call tools.
You do not write narration for the player.
You only return CommitterFinalOutput.
DataPreset remains authoritative for the final state: custom attributes, stats, and entity types in the mutation log and final state should obey the supplied preset.

Output schema:
- ready_to_commit: true only if the validated sandbox state is coherent enough to persist.
- round_summary: compact internal summary of persistent changes this turn.
- mutation_log: complete list of sandbox mutations that led to the final state.
- warnings: consistency or uncertainty warnings, or [].
- final_state: the final sandbox state object.
- database_patch_preview: incremental mutation records needed by the DB layer, not the whole database.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Final Committer Output

## User input
{{ data.user_input or "No user input." }}

## Resolver output
{{ data.resolver_output }}

## Pending generated proposals
{{ data.pending_generated_proposals }}

## Data preset constraints
{{ data.data_preset }}

## Original state
{{ data.original_state }}

## Final sandbox state
{{ data.final_sandbox_state }}

## Mutation log
{{ data.mutation_log }}

## Last tool results
{{ data.tool_results or "No tool calls were made in the last mutation pass." }}

## Last validation
{{ data.last_validation }}

# Required output

Return CommitterFinalOutput only.
"""
            ),
        ],
    )


@pytest.fixture
def mock_narrator_agent_profile(inference_model) -> NarratorAgentProfile:
    return NarratorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
        ),
        narrate_resolved_turn_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

You write natural language narration for the player.

You receive resolved events from the resolver. These are authoritative.
Do not change outcomes.
Do not add new actions.
Do not make unresolved actions succeed.
Do not reveal hidden facts unless supplied world entries permit narration.

You are not the resolver.
You are not the committer.
You do not output JSON.
You do not describe database changes.
You do not mention internal agent names, resolver records, or system stages.

Narration rules:
- Describe what the player character can perceive.
- Include successful and failed actions as visible events.
- Preserve uncertainty when facts are not confirmed.
- If a character failed or was blocked, narrate the attempt and the visible reason.
- Do not over-explain private motives.
- Use concise but atmospheric prose.
- End with a natural opening for the player to respond.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Resolved Turn Narration

## Simulation
{{ data.simulation.name }}
{{ data.simulation.description }}

## Current state
Time: {{ data.state.time_label }}
State summary:
{{ data.state.state }}

## Location
{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}

{{ data.current_location.description }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## User input
{{ data.user_input or "No explicit user input." }}

## Recent history
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.long_term_history_summary or "No long-term history summary." }}

## Present characters
{% for c in data.characters %}
- {{ c.name }}: {{ c.public_state }}
{% endfor %}

## Character attempted actions
{% for a in data.character_actions %}
- {{ a.character_name }} attempted: {{ a.intent }}
  Visible behaviour: {{ a.visible_behavior }}
{% else %}
None.
{% endfor %}

## Resolver output
{{ data.resolver_output }}

## Narrator-visible world entries
Use these only according to their narration permission.
{% for e in data.world_entries_for_narrator %}
- {{ e.content }}
  Permission: {{ e.narration_permission }}
  Visibility: {{ e.visibility }}
{% else %}
None.
{% endfor %}

## Pending generated proposals
These are not canonical unless the resolver output accepted them.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required narration

Write the narration for this resolved turn.

Output natural language only.
"""
            ),
        ],
        narrate_wait_for_user_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

This mode is used when the Director determines the scene cannot continue meaningfully without player input.

Your job:
- briefly restate the immediate situation;
- make clear that the scene is waiting on the player character;
- do not progress NPC actions;
- do not resolve new events;
- do not invent new facts.

Do not output JSON.
Do not mention Director, scheduler, agents, or system stages.

Narration rules:
- Keep it short.
- Focus on the immediate social or physical pressure.
- The final sentence should naturally invite player action or response.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Wait For User Narration

## Simulation
{{ data.simulation.name }}
{{ data.simulation.description }}

## Current state
Time: {{ data.state.time_label }}
State summary:
{{ data.state.state }}

## Location
{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}

{{ data.current_location.description }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## User input
{{ data.user_input or "No explicit user input." }}

## Recent history
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.long_term_history_summary or "No long-term history summary." }}

## Present characters
{% for c in data.characters %}
- {{ c.name }}: {{ c.public_state }}
{% endfor %}

## Director output
Use this only to understand why the scene is waiting.
{{ data.director_output }}

## Narrator-visible world entries
{% for e in data.world_entries_for_narrator %}
- {{ e.content }}
  Permission: {{ e.narration_permission }}
  Visibility: {{ e.visibility }}
{% else %}
None.
{% endfor %}

# Required narration

Write a short narration indicating the scene is waiting for the player.

Output natural language only.
"""
            ),
        ],
        narrate_user_input_failure_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

This narration is for an early user-input validation failure.

The user's attempted action was not accepted as stated.
Your job is to narrate the failed or blocked attempt in-world, while preserving player agency.

Do not punish the player harshly unless the resolver output says so.
Do not invent major consequences.
Do not make the action succeed.
Do not reveal hidden facts.
Do not output JSON.
Do not mention validation, resolver, legality checks, or system rules.

Narration rules:
- Show the player character attempting or reconsidering the action.
- Explain the immediate in-world obstacle.
- Keep the tone immersive.
- End with the player still able to choose another action.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# User Input Failure Narration

## Simulation
{{ data.simulation.name }}
{{ data.simulation.description }}

## Current state
Time: {{ data.state.time_label }}
State summary:
{{ data.state.state }}

## Location
{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}

{{ data.current_location.description }}

## Player character
{{ data.player_character.name }}
Public state: {{ data.player_character.public_state }}

## User attempted input
{{ data.user_input }}

## Resolver validation output
{{ data.resolver_output }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Recent history
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.long_term_history_summary or "No long-term history summary." }}

## Narrator-visible world entries
{% for e in data.world_entries_for_narrator %}
- {{ e.content }}
  Permission: {{ e.narration_permission }}
  Visibility: {{ e.visibility }}
{% else %}
None.
{% endfor %}

# Required narration

Narrate the failed or blocked attempt naturally.

Output natural language only.
"""
            )
        ],
    )


@pytest.fixture
def mock_simulation(mock_director_profile,
                    mock_memory_agent_profile,
                    mock_character_agent_profile,
                    mock_resolver_agent_profile,
                    mock_committer_agent_profile,
                    mock_narrator_agent_profile,
                    mock_world_generator_profile,
                    mock_embedding_profile,
                    ) -> Simulation:
    return Simulation(
        id=1,
        name="The Blackwater Observatory",
        description="The year is 1912. The isolated mountain town of Blackwater Ridge was built around an "
                    "astronomical observatory that once conducted secret government-funded research.\n\n"
                    "Three weeks ago, the observatory's director vanished. Officially, he left without notice. "
                    "However, nobody believes that. The player arrives in town during the annual Founder's "
                    "Festival, where tensions between residents are beginning to surface.",
        agent_preset=AgentPreset(
            director=mock_director_profile,
            memory=mock_memory_agent_profile,
            character=mock_character_agent_profile,
            resolver=mock_resolver_agent_profile,
            committer=mock_committer_agent_profile,
            narrator=mock_narrator_agent_profile,
            world_generator=mock_world_generator_profile,
        ),
        data_preset=DataPreset(
            character_attributes=[
                ModelAttribute(
                    name="relationship",
                    values=None,
                    creation_instruction="",
                    update_instruction="",
                    universal=True,
                )
            ],
            character_stats=[],
            entity_types={
                "important-item": "An important item that is relevant to the story, and can be interacted with. It "
                                  "should remain relevant after multiple rounds, and may be acquired or used by "
                                  "characters."
            },
            faction_attributes=[],
            faction_stats=[],
        ),
        embedding_profile=mock_embedding_profile,
        language="en"
    )


@pytest.fixture
def mock_simulation_state_1() -> SimulationState:
    return SimulationState(
        id=1,
        scene=3,
        turn_number=0,
        time_label="Founder's Festival evening, three weeks after Director Harlan's disappearance",
        state="Arthur Moore has arrived at the Iron Stag Inn during the Founder's Festival. Clara Whitlock is behind "
              "the bar, managing guests while quietly observing Arthur. The inn is busy with locals and festival "
              "visitors, making it a useful place to gather rumours without drawing immediate attention. Arthur has "
              "not yet revealed the full contents of the anonymous letter. Eleanor Graves is aware that an outside "
              "investigator has arrived in town, but has not yet confronted him directly. Marcus Reed remains at or "
              "near the observatory, anxious about Harlan's missing notebook and the unauthorized signal experiments.",
        recent_history_summary="Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed "
                               "his controlled manner and suspected he was not merely a curious traveller. Eleanor "
                               "briefly greeted Arthur, presenting the town as orderly and festive while probing "
                               "his purpose. Arthur has not yet revealed the anonymous letter.",
        long_term_history_summary="Director Harlan disappeared three weeks ago. Officially he left without notice, "
                                  "but many residents doubt this. The observatory, the old mine, altered property "
                                  "records, the unknown visitor, and Harlan's missing notebook are all unresolved "
                                  "investigation threads."
    )


@pytest.fixture
def mock_characters() -> list[Character]:
    return [
        Character(
            id=1,
            name="Eleanor Graves",
            gender="female",
            age=42,
            description="Eleanor Graves is the mayor of Blackwater Ridge. She is calculating, practical, and deeply "
                        "attached to her office. It is difficult to tell whether she acts out of civic duty or personal "
                        "instinct, because the two have become almost indistinguishable. She is fiercely protective of "
                        "the town's reputation and prefers to contain trouble before it becomes public. Eleanor avoids "
                        "direct lies when possible, but is highly skilled at omission, selective framing, and presenting "
                        "the truth in whatever form best serves her interests.",
            appearance="A composed woman with sharp features, tired eyes, and an immaculate posture. She usually carries "
                       "herself with formal restraint, as if permanently standing before a public meeting.",
            public_state="Welcoming Arthur Moore to Blackwater Ridge while presenting the town as orderly, festive, and "
                         "untroubled by Director Harlan's disappearance.",
            private_state="Trying to determine what Arthur Moore is actually here for, whether he was truly hired as an "
                          "independent investigator, and whether his presence threatens the altered property records, "
                          "the town's finances, or her own position.",
            location=3,
            user_controlled=False,
            attributes={
                "relationship": [
                    "Marcus Reed:distrust",
                    "Clara Whitlock:wary respect",
                    "Arthur Moore:cautious scrutiny",
                    "Director Harlan:concern mixed with political fear",
                ],
            },
            stats={},
        ),
        Character(
            id=2,
            name="Marcus Reed",
            gender="male",
            age=35,
            description="Marcus Reed is the assistant at Blackwater Observatory. His work involves aiding astronomical "
                        "and radio-frequency research, maintaining equipment, and supporting Director Harlan's projects. "
                        "He is intelligent, well educated, technically capable, and deeply anxious. Marcus is prone to "
                        "fixation, especially when a problem appears to connect with his research. He often works through "
                        "the night, forgets meals, neglects social obligations, and treats sleep as an inconvenience. "
                        "His obsession with strange underground signals has begun to affect his judgement.",
            appearance="A thin, pale man with restless hands, ink-stained fingers, and dark circles under his eyes. His "
                       "hair is usually untidy, and he often appears as though he has dressed in haste after waking from "
                       "a troubled sleep.",
            public_state="Continuing limited observatory work while insisting that Director Harlan's disappearance must "
                         "have a rational explanation.",
            private_state="Desperate to recover Harlan's missing notebook before Eleanor, Arthur, or anyone else uses it "
                          "to expose his unauthorized experiments. He suspects the underground signals are connected to "
                          "Harlan's disappearance but fears admitting how much he knows.",
            location=1,
            user_controlled=False,
            attributes={
                "relationship": [
                    "Eleanor Graves:suspicion",
                    "Clara Whitlock:trust and reliance",
                    "Arthur Moore:intellectual curiosity mixed with caution",
                    "Director Harlan:guilt, loyalty, and unresolved dependence",
                ],
            },
            stats={},
        ),
        Character(
            id=3,
            name="Clara Whitlock",
            gender="female",
            age=29,
            description="Clara Whitlock is the innkeeper of the Iron Stag Inn. She is friendly, socially perceptive, "
                        "and outwardly cheerful, but much sharper than she first appears. Because many locals gather at "
                        "her inn, she hears rumours before officials do and remembers details others overlook. Clara "
                        "quietly keeps track of gossip, strange visitors, debts, arguments, and overheard remarks. She "
                        "enjoys knowing more than people think she knows, and she is willing to use that knowledge if "
                        "the truth is interesting enough.",
            appearance="A lively woman with attentive eyes, quick expressions, and a practiced welcoming smile. She "
                       "moves with the confidence of someone who knows every loose floorboard and every regular customer "
                       "in her own establishment.",
            public_state="Running the Iron Stag Inn during the Founder's Festival, serving guests, listening to rumours, "
                         "and presenting herself as merely curious about Arthur Moore's arrival.",
            private_state="Trying to uncover the truth behind Director Harlan's disappearance, partly out of concern and "
                          "partly because she believes the story could be valuable to a newspaper. She is also quietly "
                          "watching Marcus, whom she believes is frightened rather than malicious.",
            location=3,
            user_controlled=False,
            attributes={
                "relationship": [
                    "Eleanor Graves:wary",
                    "Marcus Reed:protective fondness",
                    "Arthur Moore:friendly curiosity",
                    "Director Harlan:concerned respect",
                ],
            },
            stats={},
        ),
        Character(
            id=4,
            name="Arthur Moore",
            gender="male",
            age=37,
            description="Arthur Moore is an independent investigator, sometimes called a private detective by those who "
                        "prefer the dramatic term. He is competent, observant, and experienced enough to read people "
                        "without immediately showing his conclusions. Arthur has solved several private and commercial "
                        "incidents, but has not yet achieved public recognition. He is good with people when he chooses "
                        "to be, though his politeness conceals a deep distrust. He believes anyone is capable of almost "
                        "anything under the right pressure.",
            appearance="A neatly kept man with a reserved expression, watchful eyes, and the habit of pausing before he "
                       "answers. His manner is calm rather than warm, giving the impression that he is always comparing "
                       "what is said with what is being hidden.",
            public_state="Arriving in Blackwater Ridge during the Founder's Festival as an independent investigator, "
                         "presenting himself as professionally interested in Director Harlan's disappearance.",
            private_state="Investigating who anonymously hired him, why payment depends on obtaining evidence, and "
                          "whether Harlan's disappearance is connected to the observatory, the old mine, or the town's "
                          "leadership.",
            location=3,
            user_controlled=True,
            attributes={
                "relationship": [
                    "Eleanor Graves:professionally cautious",
                    "Marcus Reed:unresolved suspicion",
                    "Clara Whitlock:tentative trust",
                    "Director Harlan:case subject",
                ],
            },
            stats={},
        ),
    ]


@pytest.fixture
def mock_factions() -> list[Faction]:
    return [
        Faction(
            id=1,
            name="Blackwater Observatory",
            description="The astronomical observatory overlooking Blackwater Ridge. Publicly, it studies stars and "
                        "celestial phenomena; privately, it has received secret government funding for unusual signal "
                        "research. Its reputation is scholarly, but its isolation and secrecy make it a source of local "
                        "suspicion.",
            attributes={},
            stats={},
        ),
        Faction(
            id=2,
            name="Blackwater Town Council",
            description="The municipal authority of Blackwater Ridge, responsible for town administration, public "
                        "records, festival arrangements and official decisions. It is closely associated with Mayor "
                        "Eleanor Graves and the public image of the town.",
            attributes={},
            stats={},
        ),
        Faction(
            id=3,
            name="Iron Stag Inn",
            description="The central inn and tavern of Blackwater Ridge. It is not a political institution, but it acts "
                        "as the town's informal information hub because locals, visitors and festival guests regularly "
                        "gather there.",
            attributes={},
            stats={},
        ),
        Faction(
            id=4,
            name="Unknown Government Contractor",
            description="A vague outside interest connected to the observatory's original secret funding. Its exact "
                        "identity, authority and current involvement are not publicly known, but it is relevant to "
                        "Director Harlan's past work and the unknown visitor who came before his disappearance.",
            attributes={},
            stats={},
        ),
        Faction(
            id=5,
            name="Mine Land Shell Companies",
            description="A set of obscure legal entities associated with property purchases around the abandoned old "
                        "mine. They may not operate openly in town, but they are repeatedly connected to altered records "
                        "and suspicious land transfers.",
            attributes={},
            stats={},
        ),
    ]

@pytest.fixture
def mock_faction_relationships() -> list[FactionRelationship]:
    return [
        FactionRelationship(
            from_type=FactionRelationshipEntity.CHARACTER,
            from_id=1,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=2,
            relationship="mayor",
            private=False,
        ),
        FactionRelationship(
            from_type=FactionRelationshipEntity.CHARACTER,
            from_id=2,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=1,
            relationship="employee",
            private=False,
        ),
        FactionRelationship(
            from_type=FactionRelationshipEntity.CHARACTER,
            from_id=3,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=3,
            relationship="proprietor",
            private=False,
        ),
        FactionRelationship(
            from_type=FactionRelationshipEntity.CHARACTER,
            from_id=1,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=5,
            relationship="concealed administrative connection",
            private=True,
        ),
        FactionRelationship(
            from_type=FactionRelationshipEntity.FACTION,
            from_id=4,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=1,
            relationship="secret research sponsor",
            private=True,
        ),
        FactionRelationship(
            from_type=FactionRelationshipEntity.FACTION,
            from_id=5,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=2,
            relationship="records irregularity subject",
            private=True,
        ),
    ]


@pytest.fixture
def mock_items_0() -> list[Item]:
    return [
        Item(
            id=1,
            name="Harlan's Notebook",
            description="Director Harlan's missing notebook, containing research notes, rough mine sketches, "
                        "observatory calculations, and several encoded entries.",
            quality=None,
            quantity=1,
            unique=True,
        ),
        Item(
            id=2,
            name="Brass Laboratory Key",
            description="A small brass key that opens the locked laboratory in Blackwater Observatory. It is "
                        "currently hidden inside the hollow festival monument in town square.",
            quality=None,
            quantity=1,
            unique=True,
        ),
        Item(
            id=3,
            name="Silver Pocket Watch",
            description="Director Harlan's silver pocket watch. It stopped at 11:17 PM and may indicate when "
                        "something significant happened.",
            quality="damaged",
            quantity=1,
            unique=True,
        ),
        Item(
            id=4,
            name="Unknown Visitor's Note Fragment",
            description="A torn fragment of paper connected to the unknown visitor who rented Room 7. It contains "
                        "only partial handwriting and is not enough to identify the writer by itself.",
            quality="torn",
            quantity=1,
            unique=True,
        ),
    ]


@pytest.fixture
def mock_items_1() -> list[Item]:
    return [
        Item(
            id=5,
            name="Surveyor's Map",
            description="An old surveyor's map of the mine and surrounding land. It shows a tunnel not present "
                        "on official town records.",
            quality="aged",
            quantity=1,
            unique=True,
        ),
        Item(
            id=6,
            name="Mayor's Administrative Seal",
            description="Eleanor Graves's official municipal seal, used to authenticate town documents and "
                        "records.",
            quality=None,
            quantity=1,
            unique=True,
        ),
    ]


@pytest.fixture
def mock_items_2() -> list[Item]:
    return [
        Item(
            id=7,
            name="Signal Recording Strip",
            description="A narrow paper strip from the observatory's recording apparatus, marked with irregular "
                        "signal patterns detected beneath Blackwater Ridge.",
            quality=None,
            quantity=1,
            unique=True,
        ),
        Item(
            id=8,
            name="Marcus's Calibration Notes",
            description="Marcus Reed's personal technical notes on telescope alignment, receiver behaviour, and "
                        "his unauthorized signal experiments.",
            quality=None,
            quantity=1,
            unique=True,
        ),
    ]


@pytest.fixture
def mock_items_3() -> list[Item]:
    return [
        Item(
            id=9,
            name="Clara's Gossip Notebook",
            description="Clara Whitlock's private notebook of rumours, guest observations, suspicious behaviour, "
                        "and overheard conversations at the Iron Stag Inn.",
            quality=None,
            quantity=1,
            unique=True,
        ),
        Item(
            id=10,
            name="Room 7 Cash Receipt",
            description="A receipt for the unknown visitor's payment for Room 7 at the Iron Stag Inn. The name "
                        "written on it is believed to be false.",
            quality=None,
            quantity=1,
            unique=True,
        ),
    ]


@pytest.fixture
def mock_items_4() -> list[Item]:
    return [
        Item(
            id=11,
            name="Anonymous Letter",
            description="The letter that brought Arthur Moore to Blackwater Ridge. It requests an investigation "
                        "into Director Harlan's disappearance and states that payment depends on obtaining "
                        "evidence.",
            quality=None,
            quantity=1,
            unique=True,
        ),
        Item(
            id=12,
            name="Investigator's Notebook",
            description="Arthur Moore's own notebook for case notes, witness statements, deductions, timelines, "
                        "and contradictions.",
            quality=None,
            quantity=1,
            unique=True,
        ),
    ]


@pytest.fixture
def mock_equipments_0() -> list[Equipment]:
    return []


@pytest.fixture
def mock_equipments_1() -> list[Equipment]:
    return []


@pytest.fixture
def mock_equipments_2() -> list[Equipment]:
    return []


@pytest.fixture
def mock_equipments_3() -> list[Equipment]:
    return []


@pytest.fixture
def mock_equipments_4() -> list[Equipment]:
    return [
        Equipment(
            id=1,
            name="Pocket Revolver",
            description="Arthur Moore's compact personal revolver, carried for protection rather than open "
                        "intimidation.",
            quality=None,
            status=EquipmentStatus.EQUIPPED,
        ),
        Equipment(
            id=2,
            name="Investigator's Coat",
            description="A practical dark travelling coat with deep pockets suitable for carrying papers, small "
                        "tools, and evidence.",
            quality=None,
            status=EquipmentStatus.EQUIPPED,
        ),
    ]


@pytest.fixture
def mock_locations() -> list[Location]:
    return [
        Location(
            id=1,
            primary_location="Blackwater Ridge",
            detailed_location="Blackwater Observatory",
            scene="Director's Office",
            description="The private office of the missing Director Harlan. It is orderly at first glance, but the room "
                        "has the uncomfortable feeling of a place recently searched and then carefully restored. Tall "
                        "windows face the mountains, while shelves of astronomical records, correspondence and field "
                        "notes line the walls.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=1,
                    name="Director's Desk",
                    type="important-item",
                    description="A heavy oak desk used by Director Harlan. Its drawers contain correspondence, old "
                                "stationery, and signs that some papers were recently removed.",
                    status="Closed. The surface is neat, but several documents appear to be missing from their usual "
                           "places.",
                    interactions=["inspect", "open drawers", "search for hidden compartment"],
                ),
                Entity(
                    id=2,
                    name="Locked Filing Cabinet",
                    type="important-item",
                    description="A reinforced metal cabinet containing observatory administrative records and archived "
                                "research paperwork.",
                    status="Locked. The lock is scratched, suggesting someone may have tried to open it without the key.",
                    interactions=["inspect", "attempt to unlock", "force open"],
                ),
            ],
        ),
        Location(
            id=2,
            primary_location="Blackwater Ridge",
            detailed_location="Blackwater Observatory",
            scene="Telescope Chamber",
            description="The main chamber of the observatory, dominated by a large brass-and-steel telescope mounted "
                        "beneath the rotating dome. The room smells of machine oil, cold stone and dust. Instruments, "
                        "calibration charts and star tables are arranged around the chamber.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=3,
                    name="Main Telescope",
                    type="important-item",
                    description="The observatory's primary telescope, a large and finely maintained astronomical "
                                "instrument aimed through the dome aperture.",
                    status="Functional, but currently misaligned from its standard calibration position.",
                    interactions=["inspect", "adjust alignment", "look through"],
                ),
                Entity(
                    id=4,
                    name="Signal Recording Apparatus",
                    type="important-item",
                    description="A collection of coils, receivers, paper rolls and improvised attachments used to record "
                                "unusual signal patterns alongside astronomical observations.",
                    status="Powered down. Several recent recording strips remain attached to the machine.",
                    interactions=["inspect", "read recording strips", "attempt to operate"],
                ),
            ],
        ),
        Location(
            id=3,
            primary_location="Blackwater Ridge",
            detailed_location="Iron Stag Inn",
            scene="Bar",
            description="The busy ground-floor bar of the Iron Stag Inn. Locals gather here for drink, gossip and "
                        "festival talk. The room is warm, noisy and crowded enough that a careful listener can overhear "
                        "many things without appearing suspicious.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=5,
                    name="Visitor's Room Ledger",
                    type="important-item",
                    description="The inn's room ledger, recording room usage, dates, names, payments and occasional "
                                "notes made by Clara Whitlock.",
                    status="Kept behind the bar. Room 7 contains an entry made under a false name and paid in cash.",
                    interactions=["read", "inspect Room 7 entry", "add entry"],
                ),
                Entity(
                    id=6,
                    name="Notice Board",
                    type="important-item",
                    description="A public notice board covered with festival announcements, missing notices, trade "
                                "offers and local messages.",
                    status="Crowded with new festival notices. Older papers are pinned underneath.",
                    interactions=["inspect", "read notices", "remove notice"],
                ),
            ],
        ),
        Location(
            id=4,
            primary_location="Blackwater Ridge",
            detailed_location="Iron Stag Inn",
            scene="Room 7",
            description="A modest guest room on the upper floor of the Iron Stag Inn. It appears unused at first, but "
                        "closer inspection reveals that someone stayed briefly and avoided leaving obvious traces.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=7,
                    name="Room 7 Writing Desk",
                    type="important-item",
                    description="A small guest writing desk with a worn surface, an ink bottle and a narrow drawer.",
                    status="Mostly clean, though faint pressure marks remain on the writing surface.",
                    interactions=["inspect", "search drawer", "take rubbing of writing marks"],
                ),
                Entity(
                    id=8,
                    name="Guest Room Window",
                    type="important-item",
                    description="A window overlooking the side alley beside the inn.",
                    status="Closed but not latched. The sill has faint scrape marks.",
                    interactions=["inspect", "open", "look outside"],
                ),
            ],
        ),
        Location(
            id=5,
            primary_location="Blackwater Ridge",
            detailed_location="Town Hall",
            scene="Mayor's Office",
            description="Eleanor Graves's office inside Town Hall. The room is formal, controlled and carefully arranged. "
                        "A locked cabinet, a polished desk and framed town charters communicate authority and civic "
                        "stability.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=9,
                    name="Mayor's Desk",
                    type="important-item",
                    description="A polished desk containing official correspondence, festival planning papers and sealed "
                                "municipal documents.",
                    status="Orderly and watched carefully by Eleanor when she is present.",
                    interactions=["inspect", "search", "read visible papers"],
                ),
                Entity(
                    id=10,
                    name="Municipal Lockbox",
                    type="important-item",
                    description="A compact iron lockbox used for sensitive town documents and private administrative "
                                "records.",
                    status="Locked and kept inside the mayor's office.",
                    interactions=["inspect", "attempt to unlock", "move"],
                ),
            ],
        ),
        Location(
            id=6,
            primary_location="Blackwater Ridge",
            detailed_location="Town Hall",
            scene="Records Room",
            description="A cramped archival room filled with shelves of deeds, survey papers, council minutes and tax "
                        "records. Dust hangs in the air, but some folders have clearly been handled recently.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=11,
                    name="Property Record Shelves",
                    type="important-item",
                    description="Shelves containing land ownership records for Blackwater Ridge and its surrounding "
                                "territory, including the old mine area.",
                    status="Several folders relating to mine-adjacent land show signs of recent removal and replacement.",
                    interactions=["inspect", "search records", "compare documents"],
                ),
                Entity(
                    id=12,
                    name="Survey Archive Cabinet",
                    type="important-item",
                    description="A cabinet containing older surveyor records and historical mine documentation.",
                    status="Closed but not locked. Older maps are filed inside.",
                    interactions=["open", "search", "retrieve map"],
                ),
            ],
        ),
        Location(
            id=7,
            primary_location="Blackwater Ridge",
            detailed_location="Town Square",
            scene="Festival Monument",
            description="The centre of Blackwater Ridge, currently decorated for the Founder's Festival. A stone monument "
                        "commemorates the town's founding and stands among bunting, stalls and temporary wooden stages.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=13,
                    name="Hollow Festival Monument",
                    type="important-item",
                    description="A commemorative stone monument with a concealed hollow space behind a loose plaque.",
                    status="Decorated for the festival. The loose plaque is not obvious without close inspection.",
                    interactions=["inspect", "remove plaque", "hide item", "retrieve hidden item"],
                ),
                Entity(
                    id=14,
                    name="Festival Stalls",
                    type="important-item",
                    description="Temporary market stalls set up for the Founder's Festival, selling food, trinkets and "
                                "local crafts.",
                    status="Active during the day and partly covered at night.",
                    interactions=["inspect", "ask vendors", "search after closing"],
                ),
            ],
        ),
        Location(
            id=8,
            primary_location="Blackwater Ridge",
            detailed_location="Old Mine",
            scene="Mine Entrance",
            description="The boarded entrance to the abandoned silver mine north of town. The official closure signs are "
                        "old and weathered, but the ground nearby shows more recent disturbance.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=15,
                    name="Boarded Mine Entrance",
                    type="important-item",
                    description="The sealed entrance to the old silver mine where eleven workers died twenty years ago.",
                    status="Officially closed, but several boards have been loosened and replaced more than once.",
                    interactions=["inspect", "remove boards", "enter mine"],
                ),
                Entity(
                    id=16,
                    name="Old Warning Sign",
                    type="important-item",
                    description="A weathered municipal warning sign declaring the mine unsafe and closed by town order.",
                    status="Faded and partially broken. Someone has recently cleared dirt from its base.",
                    interactions=["inspect", "read", "move aside"],
                ),
            ],
        ),
        Location(
            id=9,
            primary_location="Blackwater Ridge",
            detailed_location="Old Mine",
            scene="Main Tunnel",
            description="A dark, unstable tunnel inside the abandoned mine. The air is cold and mineral-heavy. Old rails "
                        "run into darkness, and sounds echo strangely through unseen side passages.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=17,
                    name="Collapsed Side Passage",
                    type="important-item",
                    description="A partially collapsed passage branching from the main tunnel. Loose stones and cracked "
                                "support beams make it dangerous to disturb.",
                    status="Blocked, but not completely sealed. Air can be felt moving faintly through the gaps.",
                    interactions=["inspect", "listen", "clear debris"],
                ),
                Entity(
                    id=18,
                    name="Rusting Mine Cart",
                    type="important-item",
                    description="An old ore cart sitting on warped rails, half-filled with stone fragments and rotting "
                                "wood.",
                    status="Stationary. Its wheels are rusted but may still move with effort.",
                    interactions=["inspect", "search", "push"],
                ),
            ],
        ),
        Location(
            id=10,
            primary_location="Blackwater Ridge",
            detailed_location="North Forest",
            scene="Abandoned Cabin",
            description="A small hunter's cabin hidden among the trees north of town. It has been abandoned for years, "
                        "but recent footprints and disturbed dust suggest someone has visited it recently.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=19,
                    name="Cabin Hearth",
                    type="important-item",
                    description="A stone hearth filled with old ash and traces of a more recent small fire.",
                    status="Cold. The ash has been disturbed recently.",
                    interactions=["inspect", "search ash", "light fire"],
                ),
                Entity(
                    id=20,
                    name="Loose Floorboard",
                    type="important-item",
                    description="A warped floorboard near the cabin wall, loose enough to conceal a small object beneath.",
                    status="Slightly raised from the surrounding floor.",
                    interactions=["inspect", "lift", "hide item", "retrieve hidden item"],
                ),
            ],
        ),
    ]


@pytest.fixture
def mock_world_entries() -> list[WorldEntry]:
    return [
        WorldEntry(
            id=1,
            scope=[0],
            content="Blackwater Ridge is an isolated mountain town built around Blackwater Observatory.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.ALWAYS,
            keywords=None,
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=2,
            scope=[0],
            content="The current year is 1912, and Blackwater Ridge is holding its annual Founder's Festival.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.ALWAYS,
            keywords=None,
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=3,
            scope=[0],
            content="Director Harlan, head of Blackwater Observatory, disappeared three weeks ago. Officially, he left without notice.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.ALWAYS,
            keywords=None,
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=4,
            scope=[0],
            content="Many residents of Blackwater Ridge do not believe the official explanation for Director Harlan's disappearance.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.SEMANTIC,
            keywords=None,
            chained_ids=None,
            semantic_instruction="Recall when the scene involves public mood, rumours, townspeople, the festival, or discussion of Harlan's disappearance.",
        ),

        WorldEntry(
            id=5,
            scope=[0],
            content="Twenty years ago, a collapse in the old silver mine killed eleven workers. The mine was officially closed after the incident.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="old mine", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine collapse", similarity=0.72),
                WorldEntryRecallKeyword(keyword="eleven workers", similarity=0.75),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=6,
            scope=[1, 2],
            content="Eight years ago, Blackwater Observatory began receiving secret government funding.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="government funding", similarity=0.72),
                WorldEntryRecallKeyword(keyword="observatory funding", similarity=0.72),
                WorldEntryRecallKeyword(keyword="secret funding", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=7,
            scope=[-1],
            content="The secret government funding for Blackwater Observatory was connected to unusual signal research rather than ordinary astronomy.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[6],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=8,
            scope=[1],
            content="Three years ago, property around the old mine was sold to shell companies through irregular transactions.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="property records", similarity=0.7),
                WorldEntryRecallKeyword(keyword="shell companies", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine land", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=9,
            scope=[1],
            content="Some town property records concerning land near the old mine were altered.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[8],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=10,
            scope=[-1],
            content="The altered property records are connected to the hidden mine tunnel and the underground chamber beneath the mine.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[8, 9],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=11,
            scope=[2],
            content="Six months ago, Marcus Reed began unauthorized experiments involving underground radio signals.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Marcus experiments", similarity=0.72),
                WorldEntryRecallKeyword(keyword="underground signals", similarity=0.72),
                WorldEntryRecallKeyword(keyword="radio signals", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=12,
            scope=[2],
            content="Marcus Reed has detected strange signal patterns that appear to originate from beneath Blackwater Ridge.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.9,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[11],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=13,
            scope=[1, 2],
            content="Five weeks ago, Director Harlan discovered irregularities in property records connected to land near the old mine.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan property records", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Harlan discovered", similarity=0.72),
                WorldEntryRecallKeyword(keyword="land records", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=14,
            scope=[0],
            content="Four weeks ago, Director Harlan began carrying a notebook everywhere.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.9,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan's Notebook", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Harlan carrying notebook", similarity=0.72),
                WorldEntryRecallKeyword(keyword="missing notebook", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=15,
            scope=[0],
            content="Harlan's Notebook is currently missing. It contains research notes, maps, and encoded entries.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan's Notebook", similarity=0.7),
                WorldEntryRecallKeyword(keyword="missing notebook", similarity=0.7),
                WorldEntryRecallKeyword(keyword="encoded entries", similarity=0.75),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),

        WorldEntry(
            id=16,
            scope=[2],
            content="Marcus knows that the brass laboratory key is hidden inside the hollow festival monument in town square.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="brass laboratory key", similarity=0.7),
                WorldEntryRecallKeyword(keyword="hollow festival monument", similarity=0.72),
                WorldEntryRecallKeyword(keyword="laboratory key", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=17,
            scope=[-1],
            content="The brass laboratory key opens the locked laboratory inside Blackwater Observatory.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[16],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=18,
            scope=[3],
            content="An unknown visitor arrived in Blackwater Ridge five days before Director Harlan disappeared.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="unknown visitor", similarity=0.7),
                WorldEntryRecallKeyword(keyword="Room 7", similarity=0.7),
                WorldEntryRecallKeyword(keyword="visitor before Harlan disappeared", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=19,
            scope=[3],
            content="The unknown visitor rented Room 7 at the Iron Stag Inn under a false name and paid in cash.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[18],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=20,
            scope=[3],
            content="Clara Whitlock knows the unknown visitor met secretly with Director Harlan before Harlan disappeared.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[18, 19],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=21,
            scope=[3],
            content="Clara does not know the unknown visitor's true identity.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[18, 19, 20],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=22,
            scope=[2],
            content="Marcus believes Director Harlan became increasingly paranoid before his disappearance.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan paranoid", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Marcus Harlan", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=23,
            scope=[1],
            content="Eleanor publicly presents Director Harlan as overworked rather than frightened or endangered.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan overworked", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Eleanor Harlan", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=24,
            scope=[3],
            content="Clara believes Director Harlan seemed frightened of someone shortly before he vanished.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Harlan frightened", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Clara Harlan", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),

        WorldEntry(
            id=25,
            scope=[4],
            content="Arthur Moore was anonymously hired to investigate Director Harlan's disappearance.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.ALWAYS,
            keywords=None,
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=26,
            scope=[4],
            content="Arthur's payment will only be delivered if he obtains evidence concerning Harlan's disappearance.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[25],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=27,
            scope=[4],
            content="Arthur does not know the identity of the person who hired him.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[25],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=28,
            scope=[0],
            content="The Visitor's Room Ledger at the Iron Stag Inn records the Room 7 rental under a false name.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Visitor's Room Ledger", similarity=0.7),
                WorldEntryRecallKeyword(keyword="Room 7 ledger", similarity=0.7),
                WorldEntryRecallKeyword(keyword="false name", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=29,
            scope=[0],
            content="The Surveyor's Map shows an old mine tunnel that is not present on official records.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Surveyor's Map", similarity=0.7),
                WorldEntryRecallKeyword(keyword="hidden tunnel", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine map", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=30,
            scope=[0],
            content="Director Harlan's silver pocket watch stopped at 11:17 PM.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="silver pocket watch", similarity=0.7),
                WorldEntryRecallKeyword(keyword="11:17 PM", similarity=0.8),
                WorldEntryRecallKeyword(keyword="Harlan's watch", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=31,
            scope=[-1],
            content="Director Harlan's silver pocket watch will be found in the abandoned cabin in the North Forest unless events change its location.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[30],
            semantic_instruction=None,
        ),

        WorldEntry(
            id=32,
            scope=[0],
            content="Locals sometimes report seeing lights inside the old mine despite its official closure.",
            visibility=WorldEntryVisibility.SUSPECTED,
            confidence=0.7,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="lights in the mine", similarity=0.72),
                WorldEntryRecallKeyword(keyword="old mine rumours", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine entrance", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=33,
            scope=[0],
            content="Fresh footprints were recently found near the abandoned cabin in the North Forest.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.VISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="North Forest cabin", similarity=0.72),
                WorldEntryRecallKeyword(keyword="fresh footprints", similarity=0.72),
                WorldEntryRecallKeyword(keyword="abandoned cabin", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),

        WorldEntry(
            id=34,
            scope=[-1],
            content="Director Harlan discovered illegal land sales, a hidden mine tunnel, and an underground chamber beneath the old mine.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.SEMANTIC,
            keywords=None,
            chained_ids=None,
            semantic_instruction="Recall only for GM-side reasoning when resolving the true cause of Harlan's disappearance, the mine mystery, the shell companies, or the hidden underground chamber.",
        ),
        WorldEntry(
            id=35,
            scope=[-1],
            content="The unknown visitor was a government contractor connected to Blackwater Observatory's original secret funding.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.SEMANTIC,
            keywords=None,
            chained_ids=None,
            semantic_instruction="Recall only for GM-side reasoning involving the unknown visitor, secret funding, government contractors, or Harlan's final meeting.",
        ),
        WorldEntry(
            id=36,
            scope=[-1],
            content="Director Harlan entered the hidden mine tunnel during his investigation and was trapped by a tunnel collapse.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.SEMANTIC,
            keywords=None,
            chained_ids=None,
            semantic_instruction="Recall only for GM-side reasoning when determining Harlan's true fate, mine exploration outcomes, or clues pointing to a collapse.",
        ),
        WorldEntry(
            id=37,
            scope=[-1],
            content="Director Harlan is still alive but stranded underground.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.CHAINED,
            keywords=None,
            chained_ids=[36],
            semantic_instruction=None,
        ),
    ]


@pytest.fixture
def mock_tasks() -> list[Task]:
    return [
        Task(
            id=1,
            character_ids=[4],
            private=False,
            priority=TaskPriority.URGENT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.MAIN_QUEST,
            goal="Determine what happened to Director Harlan.",
            progress=0,
            source="Anonymous Letter",
            reward="Payment from the anonymous client, released only if evidence is obtained.",
        ),
        Task(
            id=2,
            character_ids=[4],
            private=True,
            priority=TaskPriority.IMPORTANT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Identify who anonymously hired Arthur Moore.",
            progress=0,
            source="Arthur Moore's professional suspicion",
            reward="The identity and motive of Arthur's anonymous client.",
        ),
        Task(
            id=3,
            character_ids=[4],
            private=False,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Locate Harlan's missing notebook.",
            progress=0,
            source="Investigation into Harlan's final movements",
            reward="Harlan's notebook and the facts recorded inside it.",
        ),
        Task(
            id=4,
            character_ids=[4],
            private=False,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Discover the identity of the unknown visitor who stayed in Room 7.",
            progress=0,
            source="The suspicious Room 7 ledger entry",
            reward="A lead connecting the visitor to Harlan's disappearance.",
        ),

        Task(
            id=5,
            character_ids=[1],
            private=True,
            priority=TaskPriority.URGENT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.MAIN_QUEST,
            goal="Prevent public panic regarding Director Harlan's disappearance.",
            progress=70,
            source="Mayoral duty and concern for the town's reputation",
            reward="Continued public confidence in Eleanor's leadership.",
        ),
        Task(
            id=6,
            character_ids=[1],
            private=True,
            priority=TaskPriority.IMPORTANT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Determine why Arthur Moore has come to Blackwater Ridge and whether he is a threat.",
            progress=10,
            source="Eleanor's suspicion of outside investigators",
            reward="Enough knowledge to manipulate, delay, or redirect Arthur.",
        ),
        Task(
            id=7,
            character_ids=[1],
            private=True,
            priority=TaskPriority.IMPORTANT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Prevent investigation of irregular land transactions near the old mine.",
            progress=60,
            source="Eleanor's connection to the altered property records",
            reward="Protection from exposure and preservation of Eleanor's political position.",
        ),

        Task(
            id=8,
            character_ids=[2],
            private=True,
            priority=TaskPriority.URGENT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.MAIN_QUEST,
            goal="Recover Harlan's notebook before anyone else obtains it.",
            progress=15,
            source="Marcus's fear that the notebook exposes his unauthorized experiments",
            reward="Control over evidence that could implicate Marcus.",
        ),
        Task(
            id=9,
            character_ids=[2],
            private=True,
            priority=TaskPriority.IMPORTANT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Conceal evidence of unauthorized signal experiments.",
            progress=80,
            source="Marcus's self-preservation",
            reward="Reduced suspicion from Eleanor, Arthur, and the town authorities.",
        ),
        Task(
            id=10,
            character_ids=[2],
            private=True,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.PAUSED,
            type=TaskType.SIDE_QUEST,
            goal="Determine the source of the underground radio signals.",
            progress=None,
            source="Marcus's scientific obsession",
            reward="Proof that the signals are real and an explanation for their origin.",
        ),

        Task(
            id=11,
            character_ids=[3],
            private=True,
            priority=TaskPriority.IMPORTANT,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Learn the truth about Director Harlan's disappearance.",
            progress=20,
            source="Clara's curiosity and concern",
            reward="The truth about Harlan and a story valuable enough to sell to a newspaper.",
        ),
        Task(
            id=12,
            character_ids=[3],
            private=True,
            priority=TaskPriority.NORMAL,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Identify the unknown visitor who rented Room 7.",
            progress=30,
            source="Clara's inn records and memory of the visitor",
            reward="A dangerous but valuable piece of gossip.",
        ),
        Task(
            id=13,
            character_ids=[3],
            private=True,
            priority=TaskPriority.BACKGROUND,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.DAILY,
            goal="Collect and organize rumours heard at the Iron Stag Inn.",
            progress=None,
            source="Clara's occupation and habits",
            reward="Better leverage over guests, locals, and officials.",
        ),

        Task(
            id=14,
            character_ids=[1, 2],
            private=True,
            priority=TaskPriority.BACKGROUND,
            status=TaskStatus.IN_PROGRESS,
            type=TaskType.SIDE_QUEST,
            goal="Keep the observatory operational despite Director Harlan's absence.",
            progress=65,
            source="Observatory responsibility and town reputation",
            reward="The appearance that Blackwater Observatory remains stable and functional.",
        ),
    ]
