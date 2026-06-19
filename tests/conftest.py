import os
from collections.abc import AsyncGenerator
import pytest

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.misc.enums import MessageRole, LlmProvider, FactionRelationshipEntity, \
    EquipmentStatus, WorldEntryVisibility, WorldEntryRecallType, NarrationPermission, TaskType, TaskStatus, \
    TaskPriority
from world_simulation_engine.model import LlmConnectionProfile, EmbeddingProfile, WorldGeneratorAgentProfile, \
    OllamaAgentBackendConfiguration, PromptMessage, DirectorAgentProfile, MemoryAgentProfile, \
    CharacterAgentProfile, Simulation, AgentPreset, DataPreset, ModelAttribute, SimulationState, Character, \
    Faction, FactionRelationship, Item, Equipment, Location, Entity, WorldEntry, WorldEntryRecallKeyword, Task, \
    ResolverAgentProfile, CommitterAgentProfile, NarratorAgentProfile, CharacterInventory
from world_simulation_engine.model.world import WorldCreate
from world_simulation_engine.model.connection_profile import LlmConnectionCreate
from world_simulation_engine.service import DatabaseService


@pytest.fixture(autouse=True)
def disable_console_logger():
    if LOGGER.hasHandlers():
        for h in LOGGER.handlers[:]:
            LOGGER.removeHandler(h)


@pytest.fixture
async def db() -> AsyncGenerator[DatabaseService, None]:
    service = DatabaseService(
        database_path=":memory:",
        is_static=True,
    )

    await service.init()
    try:
        yield service
    finally:
        await service.close()


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
- Entity description and status must only contain objective observable/mechanical/physical state.
  Do not include inferred facts, hidden contents, clue interpretation, private knowledge, or deductions.
  They needed to be added to world entry, which is not in scope of this generation
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

Round: {{ data.generation_context.turn_number  }}
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
goal aligns. However, your proposed item must match the world style and is sensible.

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.turn_number  }}
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
        equipment_generation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are an equipment generation tool for a role-play simulation.

Generate exactly one ProposedEquipment.

Output schema:
- temp_id: temporary string ID for this proposal, for example "equip_temp_storm_lantern". Do not use a database ID.
- name: short equipment name.
- description: what the equipment is and what can be observed about it.
- status: current usable/equipped/damaged/stored condition.
- quality: optional condition label such as "worn", "damaged", "polished", or null.
- proposed_owner_id: existing character ID if the equipment clearly belongs to a present character; otherwise null.
- proposed_location_id: existing location ID if the equipment clearly belongs in a known location; otherwise null.
- reason: why this equipment is useful and how it satisfies the trigger.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Hard rules:
- The equipment is a pending proposal, not canonical.
- Do not duplicate existing equipment.
- Do not generate portable clue documents as equipment; use generate_item instead.
- Do not generate fixed environmental fixtures as equipment; use generate_entity instead.
- Do not solve major mysteries.
- Do not create final-answer evidence unless explicitly required.
- Use temp_id only.
- proposed_owner_id must be null unless clearly generated for one of the present character IDs.
- proposed_location_id must be null or one of the existing location IDs.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.

Equipment quality rules:
- Equipment should be repeatedly usable or have meaningful state/status.
- Description and status must not include hidden deductions, inferred facts, or private knowledge.
- If hidden meaning is needed, create a linked world entry using generate_generation_package instead.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate Equipment

## Goal
{{ data.goal }}

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.turn_number  }}
Time: {{ data.generation_context.time_label }}

State summary:
{{ data.generation_context.state_summary }}

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
- {{ i.id }}: {{ i.name }} | description={{ i.description }}
{% else %}
None.
{% endfor %}

Existing equipment:
{% for e in data.generation_context.existing_equipments %}
- {{ e.id }}: {{ e.name }} | status={{ e.status }} | quality={{ e.quality }} | description={{ e.description }}
{% else %}
None.
{% endfor %}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% else %}
None.
{% endfor %}

Generate exactly one ProposedEquipment.
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
- Entity description and status must only contain objective observable/mechanical/physical state.
  Do not include inferred facts, hidden contents, clue interpretation, private knowledge, or deductions.
  They are encoded in world entries, which is out of scope of this generation.

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

Round: {{ data.generation_context.turn_number  }}
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

Round: {{ data.generation_context.turn_number }}
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
        generation_package_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a linked world-generation package tool for a role-play simulation.

Generate exactly one ProposedGenerationPackage.

Use this tool when generated content is interdependent and must share temporary IDs:
- a location with entities inside it;
- an entity with hidden or scoped world-entry facts;
- a container with possible item contents;
- an item or equipment with associated knowledge;
- a clue that requires both a physical object and scoped memory/world entries.

Output schema:
- temp_id: temporary package ID, for example "pkg_temp_room_7_cache".
- title: short package title.
- package_type: one of "linked_discovery", "location_with_contents", "entity_with_clues", "item_with_knowledge", "equipment_with_knowledge", or "mixed".
- summary: concise summary of the package.
- locations: list of ProposedLocation objects.
- entities: list of ProposedEntity objects.
- items: list of ProposedItem objects.
- equipments: list of ProposedEquipment objects.
- world_entries: list of ProposedWorldEntry objects.
- links: list of ProposedLink objects.
- reason: why this package is useful and how it satisfies the trigger.
- commit_policy: "resolver_decides" unless a constraint explicitly says otherwise.

Temporary ID rules:
- Every generated object must have a temp_id.
- Use readable temporary IDs such as "entity_temp_locked_trunk" or "entry_temp_trunk_latent_clue".
- If one generated object refers to another generated object, use that object's temp_id exactly.
- Do not use database IDs for generated objects.
- Existing canonical objects may be referred to by their existing integer IDs only where the schema expects canonical IDs.
- The application will namespace temporary IDs after generation; your internal references must still be consistent.

Entity rules:
- Entity description and status must contain only objective, observable, mechanical, or physical state.
- Do not put inferred facts, hidden contents, clue interpretation, ownership deductions, or private knowledge into entity description/status.
- Put hidden facts, inferred facts, private knowledge, rumours, beliefs, or latent clue meaning into world_entries instead.

Item and equipment rules:
- Item description must describe the object, not narrate discovery or guarantee interpretation.
- Equipment is for worn, carried, installed, or repeatedly usable gear.
- Items are for portable objects, documents, clues, tokens, receipts, fragments, and consumables.

World-entry rules:
- World entries hold persistent knowledge, hidden facts, deductions, rumours, beliefs, memories, and clue meanings.
- scope must use [0] for public/common knowledge, [-1] for GM-only hidden facts, or present character IDs.
- Use confidence below 1.0 for rumours, suspicions, guesses, or unreliable testimony.
- If recall_type is "keyword", include useful keywords.
- If recall_type is "semantic", include semantic_instruction.
- If recall_type is "chained", chained_ids may refer only to existing canonical entry IDs supplied in context, not generated temp IDs.
- Use links to connect generated entries to generated objects.

Package quality rules:
- Keep the package minimal. Generate only what is needed now.
- Do not solve major mysteries unless explicitly required.
- Prefer partial, ambiguous, actionable clues.
- Do not duplicate existing locations, entities, items, equipment, or world entries.
- Do not decide whether the triggering action succeeds.
- Include commit_policy="resolver_decides" unless constraints specify otherwise.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Generate Linked Package

## Goal
{{ data.goal }}

## Canonical generation context
Simulation: {{ data.generation_context.simulation_name }}
Description:
{{ data.generation_context.simulation_description }}

Round: {{ data.generation_context.turn_number }}
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
{% else %}
None.
{% endfor %}

Generate exactly one ProposedGenerationPackage.

Use the package only for linked content. If only one independent object is required, this tool should not have been called; still produce the smallest valid package.
"""
            ),
        ]
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
- use world-entry generation only when a newly introduced fact must persist beyond this turn and is not
  already represented in state, history, tasks, entities, or character private/public state.
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
When uncertain, prefer NO_TOOL_NEEDED unless the next Director scheduling step cannot proceed without a concrete new object.

When generated content has linked parts, prefer generate_generation_package instead of multiple separate tool calls.

Use generate_generation_package for:
- a generated location with entities inside it;
- an entity that needs latent hidden facts or scoped knowledge entries;
- a container that may contain generated items;
- an item or equipment that needs associated world entries;
- any case where several generated objects must share temporary IDs.

Use single-object tools only for independent standalone proposals.
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
- decide whether the scene should wait for player input;
- provide internal activation reasons for audit;
- include pending generated proposals supplied in the input.

You are not the narrator.
You are not the resolver.
You are not a character agent.
You do not write character briefings.
You do not decide whether actions succeed.
You do not commit world state.
You do not write dialogue.
You do not call tools in this phase.

Core scheduling principle:
Activate characters based on:
1. opportunity in the current scene;
2. ability to influence the current scene;
3. motivation or obligation to act.

Do not activate a character merely because they have a relevant goal.
They must also be present and have a plausible opportunity to affect the current scene now.

Privacy rules:
- You may use private states, private tasks, and private motives for scheduling.
- If private data influenced activation, set private_motive_used=true.
- Record whether activation came from public state, private state, public task, private task, scene opportunity, or user input.
- Do not leak private information into scene_focus.
- ActivationDecision.reason and director_notes are internal audit text only.
- Do not put character instructions, dialogue instructions, or narration guidance in director_notes.
- Do not convert a task goal into progress or knowledge. If a task says the character wants to identify, find, confirm, 
  uncover, or investigate something, that means they do not necessarily know it yet.

Scheduling rules:
- Do not activate every character by default.
- If a character is absent from the current scene, and is clearly irrelevant for this turn, do not activate them.

Passive observation rule:
If a character merely remains present and does not meaningfully change position, speak, inspect, manipulate,
or pursue a goal, do not activate them. If a character actively repositions, eavesdrops, shadows, blocks,
signals, hides, searches, or otherwise changes the scene, activate them even if the action is quiet.

Priority scale:
- 100: immediate and scene-dominating need to act.
- 80-99: highly likely to act this turn.
- 60-79: likely to act this turn.
- 40-59: may act if the opportunity naturally arises.
- 20-39: mainly observing or waiting; usually do not activate unless needed.
- 0: inactive.

Priority rule:
- If activate=false, priority must be 0.
- Non-zero priority is allowed only for activated characters.
- Priority measures scheduling importance, not guaranteed action order.

Pending proposal rules:
- Pending generated proposals are not canonical.
- They may be referenced only as pending content for the resolver.
- Do not treat pending proposals as facts.

wait_for_user rules:

wait_for_user=true means the simulation should pause before any NPC action is generated.

Set wait_for_user=true only when:
- the player character must choose between materially different next actions before NPCs can proceed;
- the last resolved/narrated events directly addressed the player and require a player response;
- the scene has reached a natural decision point for the player;
- continuing NPC action would decide or skip the player character's agency.

Do not set wait_for_user=true merely because:
- the player asked an NPC a question;
- an NPC needs to answer the player's question;
- another NPC can observe, react, answer, move, or continue naturally;
- the scene will require the player's reaction after the NPC response.
- If user input says passive continuation is requested, do not wait for user unless the scene genuinely
  cannot continue.

If the user input directly asks or addresses an NPC, usually activate that NPC instead of waiting.

If wait_for_user=true:
- all activations must have activate=false;
- all activation priorities must be 0;
- reason_to_wait must describe the exact player decision needed now.

If any activation has activate=true:
- wait_for_user must be false;
- reason_to_wait must be null.

Important timing rule:
Do not wait for the player's reaction to an NPC response before the NPC response has happened.
First activate the NPC so the response can be resolved and narrated.
The next Director pass may wait for the player after that response.

Return only valid DirectorOutput.

Schema fields:
- scene_focus: concise public-safe instruction for what this scene is about now.
- activations: one ActivationDecision for each present character considered.
- ActivationDecision.character_id: existing character ID.
- ActivationDecision.character_name: matching character name.
- ActivationDecision.activate: true if this character should produce an action this turn.
- ActivationDecision.priority: integer from 0 to 100. Use 0 when activate=false.
- ActivationDecision.reason: internal reason for the activation decision.
- ActivationDecision.private_motive_used: true only if private state or private task affected the decision.
- ActivationDecision.activation_sources.public_state: true if public character state influenced activation.
- ActivationDecision.activation_sources.private_state: true if private character state influenced activation.
- ActivationDecision.activation_sources.public_task: true if a public task influenced activation.
- ActivationDecision.activation_sources.private_task: true if a private task influenced activation.
- ActivationDecision.activation_sources.scene_opportunity: true if current scene opportunity influenced activation.
- ActivationDecision.activation_sources.user_input: true if current user input influenced activation.
- wait_for_user: true only when the scene should pause for player input.
- reason_to_wait: required when wait_for_user=true; otherwise null.
- director_notes: internal audit notes only, or "" if none.
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

## Current state
Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}
Scene/location ID: {{ data.state.scene }}

State summary:
{{ data.state.state }}

## User input

The user controls these characters:
{{ data.user_characters | map(attribute='name') | join(', ') }}

And the user sent:
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

Visible entities:
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
  Description: {{ c.description }}
  Public state: {{ c.public_state }}
  Director-only private state: {{ c.private_state }}
  Location: {{ c.location }}
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

## Recalled scheduling-relevant world entries
Use these only if they affect who should act now.
Do not leak private information into scene_focus.
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
Do not write dialogue.
Do not write narration.
Do not give behavioural instructions to character agents.
Do not leak private information into scene_focus.
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
You are the Public Briefing Builder for a multi-agent role-play simulation.

Your job:
- build compact, safe public-context briefings for selected character agents;
- include only information available in the supplied input;
- summarise the immediate situation so character agents do not depend on chat history;
- preserve the distinction between established facts, current observations, and possible interactions.

You are not the character.
You are not the narrator.
You are not the resolver.
You are not the Director.
You do not decide whether actions succeed.
You do not add new world facts.
You do not write dialogue.
You do not choose the character's action.
You do not create new IDs.

Privacy rules:
- The supplied context has already been filtered, but you must still avoid leaking private information.
- Do not infer hidden motives beyond the supplied safe data.
- Do not include information belonging to another character unless it is public or explicitly supplied as safe.
- Do not expose private tasks, private motives, hidden facts, private relationships, or director-only reasoning unless explicitly present in the safe input.
- Director activation reasons are not character knowledge. Use only the public-safe scene focus, not private scheduling reasons.

Grounding rules:
- Every briefing statement must be directly supported by the supplied input.
- Do not convert available interactions into facts that have already happened.
- Do not say a character is holding, reading, revealing, moving, searching, opening, showing, or using an object unless the supplied input says so.
- If an object is available nearby, describe it as available, not already in use.
- Do not infer what a character sees unless they are present and the event is public or directly visible in the scene.
- Do not invent NPCs, items, locations, rumours, memories, clues, or actions.
- Do not add new facts to explain the scene.
- If a fact is uncertain, phrase it as uncertain.

ID rules:
- Existing IDs must be copied exactly from the input.
- CharacterBriefing.character_id must match a requested character ID.
- relevant_task_ids may contain only task IDs supplied in Safe tasks.
- relevant_world_entry_ids may contain only entry IDs supplied in Safe world entries.
- Entity IDs may be mentioned only if supplied in the current location.
- Pending generated proposal IDs, if any, are temporary but must be repeated exactly as supplied.
- Do not renumber, merge, reinterpret, or invent IDs.

Briefing rules:
- Build one briefing per requested character.
- Each requested character must have exactly one briefing.
- Keep each briefing compact but complete enough that the character agent does not need chat history.
- The briefing should orient the character to:
  - stable scene context;
  - recent public events;
  - safely known facts;
  - current public situation;
  - available scene/entity/social affordances.
- Do not write exact dialogue.
- Do not give tactical instructions disguised as briefing.
- The instruction field should restate the Director scene focus in character-neutral terms, not command a specific action.
- available_interactions must describe possibilities, not completed actions.
- constraints must contain hard limits only, not personality traits or goals.

Output rules:
Return only valid BriefingOutput.

Output schema:
- briefings: one CharacterBriefing for each requested character.
- CharacterBriefing.character_id: existing requested character ID.
- CharacterBriefing.character_name: matching character name.
- CharacterBriefing.scene_context: stable scene context visible/known to the character.
- CharacterBriefing.recent_context: compact recent public events relevant to this character.
- CharacterBriefing.known_relevant_facts: facts this character may safely know.
- CharacterBriefing.immediate_situation: what is happening right now from this character's safe perspective.
- CharacterBriefing.instruction: short, non-tactical orientation derived from Director scene focus.
- CharacterBriefing.available_interactions: possible scene/entity/social affordances, phrased as possibilities.
- CharacterBriefing.relevant_task_ids: supplied safe task IDs relevant to this character.
- CharacterBriefing.relevant_world_entry_ids: supplied safe world entry IDs relevant to this character.
- CharacterBriefing.constraints: hard limits the character agent must respect.
- notes: optional internal notes, or "".
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Public Briefing Builder Input

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

## Director scene focus
This is public-safe scheduling orientation. Do not treat it as a character command.
{{ data.director_output.scene_focus if data.director_output else "No Director scene focus supplied." }}

## Current location
Location ID: {{ data.location.id }}
Primary location: {{ data.location.primary_location }}
Detailed location: {{ data.location.detailed_location }}
Scene: {{ data.location.scene }}

Description:
{{ data.location.description }}

## Visible entities and possible interactions
These describe possible interactions, not actions already taken.
{% for entity in data.location.entities %}
- Entity {{ entity.id }}: {{ entity.name }}
  Type: {{ entity.type }}
  Description: {{ entity.description }}
  Status: {{ entity.status }}
  Possible interactions: {{ entity.interactions | join(", ") }}
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
Only include these if relevant to the requested character's safe briefing.
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
Only include supplied safe tasks. Do not invent, infer, or expose hidden tasks.
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
Only public faction relationships are provided here.
Treat private faction ties as unknown unless explicitly present in the safe input.
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
These are not canonical facts.
Mention only if relevant as pending or possible context.
Preserve any temporary proposal IDs exactly.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required output

Build safe briefings for the requested characters only.

Important:
- Do not say an interaction has happened unless it is explicitly stated in the input.
- Do not say a character is holding, reading, showing, moving, searching, opening, revealing, or using an object unless explicitly stated.
- Phrase available interactions as possibilities.
- Do not write dialogue.
- Do not choose the character's action.
- Do not create new IDs.
- Use only supplied IDs in relevant_task_ids and relevant_world_entry_ids.
- Produce BriefingOutput only.
"""
            ),
        ],
        summary_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Memory Summariser for a role-play simulation.

Your job is to create user-perceived memory summaries from narration records only.

You do not resolve actions.
You do not decide outcomes.
You do not mutate world state.
You do not create hidden facts.
You do not use private state unless it was explicitly narrated to the player.
You only summarise what the player could perceive from narration.

You return MemorySummaryOutput only.

Definitions:

1. scene_summary
- Summary of the latest narrated round only.
- 1 to 3 sentences.
- Concrete and precise.
- Include who acted, what visibly happened, and what immediate player-facing situation remains.
- Do not include hidden causes, private motives, or GM-only facts.
- Do not include broad backstory unless it was part of the latest narration.

2. short_term_memory
- Rolling summary of roughly the last 3 narrated rounds.
- This is not just the latest scene summary.
- Preserve immediate conversational context, visible actions, unresolved prompts, and recent changes in the scene.
- Should be useful for the next turn's Director, Memory Briefing, Narrator, and Character agents.
- Keep it compact.

3. long_term_memory
- Rolling summary of roughly the last 10 to 20 narrated rounds.
- Preserve durable user-facing story progress.
- Include discovered facts, important conversations, visible relationship shifts, open mysteries, current investigation direction, and resolved scene transitions.
- Remove repeated minor details.
- Keep unresolved threads if they remain relevant.
- Do not overwrite long-term memory with only the latest scene.

4. active_scene
- A short label for the current scene or location, if clear.
- Example: "Iron Stag Inn bar during the Founder's Festival".
- Use null if unclear.

5. open_threads
- Short list of unresolved player-facing questions, hooks, or immediate next-turn tensions.
- Include only things that are visible/perceived or directly implied by narration.
- Do not include hidden facts.

6. continuity_notes
- Internal continuity reminders based only on narrated facts.
- Use these to avoid contradictions in upcoming narration.
- Do not include secret/private state unless narrated.

Rules:
- Use only the supplied narration records and previous memory summaries.
- Do not use hidden world state.
- Do not infer private motives unless the narration explicitly revealed them.
- Do not invent facts to fill gaps.
- Preserve names, locations, and concrete objects precisely.
- Keep wording neutral and compact.
- If a fact is uncertain in narration, keep it uncertain.
- If a question remains unanswered, present it as unresolved rather than answering it.
- If previous long-term memory is supplied, update it rather than replacing it with only the new records.
- If previous short-term memory is supplied, use it only as context; the new short-term memory should mostly reflect the recent record window.

Return MemorySummaryOutput only.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Memory Summarisation Input

## Latest narration

{{ data.narration }}

## Previous short-term memory

{{ data.previous_short_term_memory or "None." }}

## Previous long-term memory

{{ data.previous_long_term_memory or "None." }}

## Recent turns

{{ data.last_turns_narrations }}

# Required output

Return MemorySummaryOutput only.

Remember:
- scene_summary summarises only the latest narrated round.
- short_term_memory summarises the recent 3-round window.
- long_term_memory summarises the broader 10-20-round window plus relevant prior long-term memory.
- Use only user-perceived narration.
- Do not include hidden state or private motives unless narrated.
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
            context_window=65536,
        ),
        action_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a character decision agent in a multi-agent role-play simulation.

You act only as the specified character.

Your job:
- decide what this character attempts to do now;
- express the action as structured intent for the Resolver;
- use only this character's personality, state, goals, memories, knowledge, inventory, and current perception.

You are not the narrator.
You are not the resolver.
You are not the Director.
You do not decide whether the action succeeds.
You do not write final prose.
You do not control other characters.
You do not decide how other characters react.
You do not commit world state.
You do not create new IDs.

Knowledge rules:
- You may use the acting character's own private state, own tasks, own inventory, own equipment, and own scoped world entries.
- You may use public/visible scene information.
- You must not use private tasks, private motives, private state, or scoped world entries belonging only to other characters.
- You must not assume hidden facts that are not supplied as known to this character.
- If entity, item, faction, or location information is not clearly visible or known to this character, do not treat it as known.
- If you use private knowledge to motivate the action, set uses_private_knowledge=true and explain it only in private_reason_for_system.
- Do not put private motives into visible_behavior or spoken_intent unless the character intentionally reveals them.

Attempt rules:
- Output what the character attempts, not what definitely happens.
- Use words such as "attempts", "tries", "moves to", "reaches for", "asks", or "offers" where appropriate.
- Do not state that another character allows, believes, notices, accepts, reveals, understands, or reacts.
- Do not state that information is successfully learned, transferred, or exposed; the Resolver decides that.
- Do not force confrontation unless the character has enough reason.

Action rules:
- Choose exactly one primary action.
- The action should be plausible for the character now.
- Prefer behaviour over exposition.
- Do not write exact dialogue unless the action requires a short phrase.
- Use spoken_intent to express the meaning of speech, not a polished line of dialogue.
- If the character would stay still, observe, or wait, output action_type="wait" or "observe".
- Do not solve conflicts; the Resolver will decide ordering and outcome.
- If the action targets a character, entity, location, or item, include the appropriate ID in the target fields.
- Use [] for empty target lists and null for no target location.

Resolver constraint rules:
- constraints_for_resolver must contain factual limits or dependencies only.
- Do not include narrative preferences, desired dramatic focus, or instructions about how other characters should react.
- Good constraints: "The ledger is behind the bar"; "Clara is not handing over the ledger"; "Eleanor is trying not to be obvious."
- Bad constraints: "Arthur's reaction should be the focus"; "This should increase tension"; "Clara should seem mysterious."

ID rules:
- Use only IDs supplied in the input.
- Do not invent, renumber, or reinterpret IDs.
- target_character_ids must contain only visible character IDs directly targeted.
- target_entity_ids must contain only supplied current-location entity IDs directly targeted.
- target_item_ids must contain only supplied item IDs directly used or targeted.
- target_location_id must be a supplied/known location ID or null.

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
- method: how the character attempts the action, written as an attempted action.
- visible_behavior: what other characters could observe about the attempt, without private motives.
- spoken_intent: short meaning of any speech, or null.
- urgency: 0-100, how quickly the character tries to act.
- persistence: 0-100, how hard the character keeps trying if resisted or delayed.
- expected_outcome: what the character hopes will happen, not a guaranteed result.
- fallback_if_blocked: backup attempt if the action cannot proceed, or null.
- uses_private_knowledge: true if private state, private tasks, or scoped facts belonging to this character motivated the action.
- private_reason_for_system: private explanation when uses_private_knowledge=true; otherwise null.
- constraints_for_resolver: factual limits or dependencies the Resolver should respect.
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

## Public briefing
Scene context:
{{ data.briefing.scene_context }}

Recent context:
{{ data.briefing.recent_context }}

Known relevant facts:
{{ data.briefing.known_relevant_facts }}

Immediate situation:
{{ data.briefing.immediate_situation }}

Scene orientation:
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

## Current location as known/visible to this character
ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}
Description:
{{ data.current_location.description }}

Visible entities:
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status known to this character: {{ e.status }}
  Possible interactions: {{ e.interactions | join(", ") }}
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

## This character's relevant tasks
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

## This character's relevant world entries
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

## Relevant faction context known to this character
This may include private faction relationships involving {{ data.character.name }} or their inventory.
Do not reveal private ties in visible_behavior or spoken_intent unless the character intentionally exposes them.
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
These are pending and non-canonical.
Treat them only as possible content if the briefing makes them relevant.
Preserve any temporary proposal IDs exactly.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## User input
{{ data.user_input or "No explicit user input." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Previous public resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required output

Choose exactly one plausible attempted action for {{ data.character.name }} now.

Important:
- Output an attempt, not a resolved outcome.
- Use only supplied IDs.
- Include target IDs explicitly.
- Do not use private knowledge belonging only to other characters.
- Do not control Arthur Moore or any other character.
- Return only CharacterActionOutput.
"""
            )
        ],
        reaction_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a character reaction agent in a multi-agent role-play simulation.

You act only as the specified character.

This is a limited reaction pass after your previous action failed, was blocked, delayed, invalid, cancelled, or only partially succeeded.

Your job:
- understand what this character attempted;
- understand what the character can perceive about why it failed or was blocked;
- react plausibly based on the character's personality, state, goals, memories, knowledge, inventory, equipment, and current perception;
- produce exactly one new attempted action.

You are not the narrator.
You are not the resolver.
You are not the Director.
You do not decide whether the new action succeeds.
You do not write final prose.
You do not control other characters.
You do not decide how other characters react.
You do not mutate canonical state.
You do not create new IDs.
You do not rewrite already resolved events.
You do not undo another character's successful, partially successful, or delayed action.

Core principle:
This is not a full new turn.
The character is reacting to a failed or blocked attempt inside the same round.

Fixed-event rules:
- Events listed as fixed visible events already happened.
- You may react to them.
- You may not contradict them.
- You may not prevent them retroactively.
- You may not make another character's resolved action fail after it has already been fixed.
- Your new attempted action must start from the changed scene state.

Failure-context rules:
- The failure/block reason is system-side resolution context.
- Use only the parts of the failure/block reason that the character could plausibly perceive.
- Do not assume the character knows hidden causes, private motives, GM-only facts, or another character's private reasoning.
- If the failure reason reveals only that the attempt did not work, react to the visible failure, not to hidden mechanics.
- If the original action was invalid due to impossible assumptions or OOC/context-leak reasoning, choose a grounded fallback such as observe, wait, withdraw, ask, or attempt a different visible method.

Retry rules:
- Prefer a direct adjustment, fallback, response to being blocked, or withdrawal.
- Do not repeat the exact same failed action unless the method, target, or immediate purpose changes.
- Do not escalate unrealistically merely because the first attempt failed.
- If the sensible response is to stop, observe, recover, wait, or reassess, output action_type="wait" or "observe".
- This is the final retry for this character this round.

Knowledge rules:
- You may use the acting character's own private state, own tasks, own inventory, own equipment, own scoped world entries, fixed visible events, and private realisations explicitly supplied for this actor.
- You may use public/visible scene information.
- You must not use private tasks, private motives, private state, or scoped world entries belonging only to other characters.
- You must not assume hidden facts that are not supplied as known to this character.
- If entity, item, faction, or location information is not clearly visible or known to this character, do not treat it as known.
- If private knowledge motivates the reaction, set uses_private_knowledge=true and explain it only in private_reason_for_system.
- Do not put private motives into visible_behavior or spoken_intent unless the character intentionally reveals them.
- Do not convert a task goal into knowledge. Wanting to identify, uncover, confirm, find, or investigate something does not mean the character already knows it.

Attempt rules:
- Output what the character attempts next, not what definitely happens.
- Use words such as "attempts", "tries", "moves to", "reaches for", "asks", "offers", or "backs away" where appropriate.
- Do not state that another character allows, believes, notices, accepts, refuses, reveals, understands, or reacts.
- Do not state that information is successfully learned, transferred, exposed, concealed, or confirmed; the Resolver decides that.
- Do not decide whether the failure is overcome; the Resolver decides that.

Action rules:
- Choose exactly one primary reaction action.
- The action should be plausible for the character now.
- Prefer behaviour over exposition.
- Do not write exact dialogue unless the action requires a short phrase.
- Use spoken_intent to express the meaning of speech, not polished dialogue.
- If the action targets a character, entity, location, or item, include the appropriate ID in the target fields.
- Use [] for empty target lists and null for no target location.

Resolver constraint rules:
- constraints_for_resolver must contain factual limits or dependencies only.
- Do not include narrative preferences, desired dramatic focus, or instructions about how other characters should react.
- Good constraints: "The ledger remains behind the bar"; "The character is reacting after being blocked"; "The previous successful actions cannot be undone."
- Bad constraints: "This should increase tension"; "Arthur should become suspicious"; "The scene should focus on Clara."

ID rules:
- Use only IDs supplied in the input.
- Do not invent, renumber, merge, or reinterpret IDs.
- target_character_ids must contain only visible character IDs directly targeted.
- target_entity_ids must contain only supplied current-location entity IDs directly targeted.
- target_item_ids must contain only supplied inventory item IDs directly used or targeted.
- target_location_id must be a supplied/known location ID or null.
- Pending generated proposal IDs, if any, are temporary but must be repeated exactly if referenced.

Return only CharacterActionOutput.

Output schema:
- character_id: the acting character ID.
- character_name: the acting character name.
- intent: the character's immediate reaction goal in plain language.
- action_type: one of speak, move, inspect, manipulate_entity, use_item, give_item, take_item, observe, wait, leave_scene, custom.
- target_character_ids: IDs of characters directly targeted, or [].
- target_entity_ids: IDs of entities directly targeted, or [].
- target_location_id: destination location ID for movement, or null.
- target_item_ids: IDs of inventory/world items directly used or targeted, or [].
- method: how the character attempts the reaction, written as an attempted action.
- visible_behavior: what other characters could observe about the attempt, without private motives.
- spoken_intent: short meaning of any speech, or null.
- urgency: 0-100, how quickly the character tries to react.
- persistence: 0-100, how hard the character keeps trying if resisted or delayed.
- expected_outcome: what the character hopes will happen, not a guaranteed result.
- fallback_if_blocked: backup attempt if the reaction cannot proceed, or null.
- uses_private_knowledge: true if private state, private tasks, or scoped facts belonging to this character motivated the reaction.
- private_reason_for_system: private explanation when uses_private_knowledge=true; otherwise null.
- constraints_for_resolver: factual limits or dependencies the Resolver should respect.
- notes: optional internal notes, or "".
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Character Reaction Input

## Acting character
ID: {{ data.character.id }}
Name: {{ data.character.name }}
User controlled: {{ data.character.user_controlled }}
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

Current location ID: {{ data.character.location }}

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

## Reaction pass context

This is a limited retry/reaction inside the same round.
Already fixed events cannot be undone.
The new action must be a fresh attempted reaction, not a rewrite of the original action.

Retry number: {{ data.reaction_context.retry_number }}
Maximum retries this round: {{ data.reaction_context.max_retries_this_round }}
Allowed reaction scope: {{ data.reaction_context.allowed_reaction_scope }}

Reaction constraints:
{% for c in data.reaction_context.constraints %}
- {{ c }}
{% else %}
None.
{% endfor %}

## Original attempted action

Intent:
{{ data.reaction_context.original_action.intent }}

Action type:
{{ data.reaction_context.original_action.action_type }}

Target character IDs:
{{ data.reaction_context.original_action.target_character_ids }}

Target entity IDs:
{{ data.reaction_context.original_action.target_entity_ids }}

Target location ID:
{{ data.reaction_context.original_action.target_location_id }}

Target item IDs:
{{ data.reaction_context.original_action.target_item_ids }}

Method:
{{ data.reaction_context.original_action.method }}

Visible attempted behaviour:
{{ data.reaction_context.original_action.visible_behavior }}

Spoken intent:
{{ data.reaction_context.original_action.spoken_intent or "None." }}

Expected outcome:
{{ data.reaction_context.original_action.expected_outcome }}

Fallback if blocked:
{{ data.reaction_context.original_action.fallback_if_blocked or "None." }}

Used private knowledge:
{{ data.reaction_context.original_action.uses_private_knowledge }}

Original private reason for system:
{{ data.reaction_context.original_action.private_reason_for_system or "None." }}

## Failure / block / partial-success record

Failed action summary:
{{ data.reaction_context.failure_record.failed_action_summary }}

Retry allowed:
{{ data.reaction_context.failure_record.retry_allowed }}

System-side reason:
{{ data.reaction_context.failure_record.reason }}

Actor-visible retry context:
{{ data.reaction_context.failure_record.retry_context or "No additional retry context." }}

Important:
The system-side reason may include resolver judgement.
Only use what this character could plausibly perceive or infer.

## Fixed visible events

These already happened and cannot be undone.
{% for event in data.reaction_context.fixed_visible_events %}
- {{ event }}
{% else %}
None.
{% endfor %}

## Private realisations for this character

These are private to this actor and may be used for motivation.
{% for event in data.reaction_context.fixed_private_events_for_actor %}
- {{ event }}
{% else %}
None.
{% endfor %}

## Changed scene context

{{ data.reaction_context.changed_scene_context }}

## Immediate failure context

{{ data.reaction_context.immediate_failure_context }}

## Current location as known/visible to this character

Location ID: {{ data.current_location.id }}
Primary: {{ data.current_location.primary_location }}
Detailed: {{ data.current_location.detailed_location }}
Scene: {{ data.current_location.scene }}

Description:
{{ data.current_location.description }}

Visible entities:
{% for e in data.current_location.entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Description: {{ e.description }}
  Status known/visible to this character: {{ e.status }}
  Possible interactions: {{ e.interactions | join(", ") }}
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

## This character's tasks

Only use these as motivations. Do not treat task goals as already-known facts.
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
No active tasks.
{% endfor %}

## This character's recalled world entries

Only these entries are available as character knowledge.
{% for e in data.world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
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

## Relevant faction context known to this character

This may include private faction relationships involving {{ data.character.name }} or their inventory.
Do not reveal private ties in visible_behavior or spoken_intent unless the character intentionally exposes them.

Factions:
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
  Attributes: {{ f.attributes }}
  Stats: {{ f.stats }}
{% else %}
No relevant factions.
{% endfor %}

Faction relationships:
{% for r in data.faction_relationships %}
- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}
  Type: {{ r.relationship }}
  Private: {{ r.private }}
{% else %}
No relevant faction relationships.
{% endfor %}

## Pending generated proposals

These are pending and non-canonical.
Treat them only as possible content if explicitly relevant.
Preserve any temporary proposal IDs exactly.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## User input

{{ data.user_input or "No explicit user input." }}

## Last narration

{{ data.last_narration or "No previous narration." }}

## Previous public resolver notes

{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required output

Produce one CharacterActionOutput representing this character's attempted reaction.

Important:
- Output an attempt, not a resolved outcome.
- Do not repeat the same failed action unless the method, target, or immediate purpose changes.
- Do not contradict fixed events.
- Do not undo fixed successful, partially successful, or delayed actions.
- Do not use private knowledge belonging only to other characters.
- Do not use GM-only hidden facts unless explicitly supplied as this character's knowledge.
- Do not decide success.
- Use only supplied IDs.
- Include target IDs explicitly.
- Return only CharacterActionOutput.
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
            context_window=65536,
        ),
        resolve_character_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Resolver for a multi-agent role-play simulation.

Your job:
- evaluate attempted character actions;
- determine ordering when ordering matters;
- detect conflicts;
- decide whether actions succeed, partially succeed, fail, are blocked, delayed, invalid, or cancelled;
- produce structured event results for Narrator and Committer.

This is role-play resolution, not a tabletop rules engine.
Use reasonable fictional causality, character positioning, timing, attention, access, and available objects.

You are not the narrator.
You do not write literary prose.
You do not decide future character actions.
You do not mutate canonical state directly.
You do not invent major new facts unless they are supplied as pending proposals or are direct consequences of resolved actions.
You do not control user-controlled character responses unless explicitly supplied.

Core resolution rule:
Character actions are attempts. You decide what actually happens.

Resolution rules:
- Higher urgency generally acts earlier when timing matters.
- Persistence indicates how strongly an actor continues if delayed or resisted.
- A lower-urgency action may still complete if it does not conflict.
- If two actions require the same exclusive target, item, position, or attention, mark a conflict.
- If an action depends on unavailable knowledge, unavailable item, wrong location, blocked access, or impossible timing, mark it failed, blocked, delayed, or invalid.
- If an action is plausible but only partly completed, mark it partially_succeeded.
- If nothing meaningfully blocks a simple plausible action, allow it to succeed.
- Do not generate exact dialogue.
- Do not decide how a user-controlled character reacts, answers, believes, accepts, refuses, or feels unless the user supplied that response.

Privacy rules:
- You may use private character state, private tasks, and private faction context only for adjudicating plausibility and private results.
- Do not copy private motives into visible_result, narrator_context, or public state suggestions unless the action visibly reveals them.
- private_result_for_actor may include actor-only realisation, but only for that actor.
- If another character may notice something, phrase it as visible possibility unless perception is obvious or directly resolved.

Entity and clue rules:
- Entity description/status describe physical or observable state only.
- Hidden meaning, deductions, clue interpretation, and character knowledge belong in world_entry_hints or pending_world_entry_suggestions.
- Do not treat a hidden or scoped world entry as public knowledge.
- Do not reveal pending generated proposals unless an action successfully reveals or uses them.

Result-writing rules:
- visible_result must describe only observable outcomes in plain event terms.
- visible_result must not contain private motives, hidden facts, or future reactions.
- private_result_for_actor may describe what the actor privately realises, notices, or fails to achieve.
- state_change_hints must be atomic model-level suggestions: position, object state, possession, task progress, scene status.
- world_entry_hints must be atomic knowledge/memory suggestions caused by the action.
- narrator_context must contain only safe facts the narrator may use without adding outcomes.
- state_update_suggestions must aggregate physical/model changes for the Committer.
- pending_world_entry_suggestions must aggregate persistent knowledge/memory facts for the Committer.
- Do not use vague phrases such as "details discussed" unless you specify which details.

Retry rules:
- If a character failed due to conflict, interruption, or blocked access, add them to failed_characters.
- Set requires_actor_retry=true only when a retry/revision pass is useful.
- Do not request a retry for simple success, harmless delay, or narrative preference.
- One retry pass per character per round is assumed.

Pending generation rules:
- Pending generated proposals are not canonical.
- You may accept, reject, or defer them by suggesting state updates.
- Do not treat pending proposals as existing unless an action successfully reveals or uses them.

Output completeness rules:
- Produce one ResolvedAction for each attempted character action.
- Every ResolvedAction must include final_status, visible_result, state_change_hints, and world_entry_hints.
- Use [] for empty lists and null for absent optional values.
- If final_status is failed, blocked, invalid, or cancelled, failure_reason is required.
- If final_status is succeeded or partially_succeeded, failure_reason must be null unless there is a partial limitation to explain.

Omniscient resolver context:
- You may receive GM-only entries, private character entries, private faction context, and hidden facts.
- This does not mean every character knows those facts.
- Use actor_knowledge_index to determine what each actor may legitimately know.
- Use hidden/GM-only entries to judge reality, plausibility, contradiction, and consequences.
- If an action appears motivated by information not available to the actor, mark it invalid, failed, or partially_succeeded as appropriate.
- Explain suspected out-of-character/context-leak reasoning in private_result_for_actor or notes, not visible_result.
- Do not expose GM-only or private facts in visible_result, narrator_context, or public state suggestions unless a resolved action reveals them.

OOC/context-leak rules:
- A character may act on their own private state, own tasks, own inventory, own equipment, own scoped world entries, public scene information, and visible behaviour.
- A character may not act on another character's private task, hidden GM-only fact, or scoped entry they do not know.
- If the action's stated intent or method relies on unknown information, mark it invalid unless there is a plausible public-facing reason for the same behaviour.
- If the action itself is plausible but the private reasoning is contaminated, allow the visible action but note the OOC contamination and do not grant hidden knowledge benefits.
- Do not convert a task goal into knowledge. Wanting to identify X does not mean the character knows X.

Return only ResolverOutput.
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
  Target character IDs: {{ a.target_character_ids }}
  Target entity IDs: {{ a.target_entity_ids }}
  Target location ID: {{ a.target_location_id }}
  Target item IDs: {{ a.target_item_ids }}
  Method: {{ a.method }}
  Visible attempted behaviour: {{ a.visible_behavior }}
  Spoken intent: {{ a.spoken_intent }}
  Urgency: {{ a.urgency }}
  Persistence: {{ a.persistence }}
  Expected outcome: {{ a.expected_outcome }}
  Fallback if blocked: {{ a.fallback_if_blocked }}
  Uses private knowledge: {{ a.uses_private_knowledge }}
  Private reason for system:
  {{ a.private_reason_for_system or "None." }}
  Constraints for resolver:
  {% for c in a.constraints_for_resolver %}
  - {{ c }}
  {% else %}
  - None.
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
{% if data.round_constraints is defined and data.round_constraints.priority_order is defined %}
Suggested priority order:
{% for p in data.round_constraints.priority_order %}
- {{ p.character_id }}: {{ p.character_name }} | urgency={{ p.urgency }} | persistence={{ p.persistence }}
{% else %}
No priority entries.
{% endfor %}
{% else %}
Priority order is derived directly from CharacterActionOutput.urgency.
{% endif %}

## Resolver world entries
These may include public, character-scoped, and GM-only entries.
Use them to judge reality and plausibility.
Do not assume actors know entries unless listed in Actor knowledge index.
{% for e in data.world_entries %}
- Entry {{ e.id }}: {{ e.content }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
  Recall type: {{ e.recall_type }}
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

## Actor knowledge index
These are the world entries each actor may legitimately know.
GM-only entries with scope [-1] are intentionally not included here.
{% for actor_id, entry_ids in data.actor_knowledge_index.items() %}
- Actor {{ actor_id }} knows entries: {{ entry_ids }}
{% else %}
None.
{% endfor %}

## Action validation reports
These are code-side validation checks. Use them to detect impossible targets, missing IDs, and possible OOC/context-leak issues.
{% for report in data.action_validation_reports %}
- Actor {{ report.actor_id }}: {{ report.actor_name }}
  Actor present: {{ report.actor_present }}
  Actor known world entry IDs: {{ report.actor_known_world_entry_ids }}
  Invalid target character IDs: {{ report.invalid_target_character_ids }}
  Invalid target entity IDs: {{ report.invalid_target_entity_ids }}
  Invalid target item IDs: {{ report.invalid_target_item_ids }}
  Mentioned entities without target IDs: {{ report.mentioned_entities_without_target }}
  Mentioned characters without target IDs: {{ report.mentioned_characters_without_target }}
  Actor inventory item IDs: {{ report.actor_inventory_item_ids }}
  Actor equipment IDs: {{ report.actor_equipment_ids }}
  Notes:
  {% for note in report.notes %}
  - {{ note }}
  {% else %}
  - None.
  {% endfor %}
  Possible OOC flags:
  {% for flag in report.possible_ooc_flags %}
  - {{ flag }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
No validation reports.
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

## Resolution guardrails

- Treat character actions as attempts, not already-completed outcomes.
- Validate target IDs against visible entities, present characters, known inventory, and known locations.
- Do not infer a user-controlled character reaction unless provided in User input or attempted actions.
- If an action reveals information, specify exactly what information may now be known and by whom.
- If a character overhears, specify whether they definitely overheard or were merely in a position to overhear.
"""
            )
        ],
        resolve_reaction_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Resolver for a second-pass character reaction in a multi-agent role-play simulation.

A previous resolver pass already produced fixed resolved actions.
Some characters failed, were blocked, delayed, invalid, cancelled, or only partially succeeded.
Those characters have now produced reaction actions.

Your job:
- resolve only the supplied reaction actions;
- respect previous resolved actions as fixed truth;
- detect conflicts between reaction actions;
- detect conflicts between reaction actions and fixed previous results;
- decide whether each reaction succeeds, partially succeeds, fails, is blocked, delayed, invalid, or cancelled;
- produce structured event results for Narrator and Committer using the same ResolverOutput schema as normal resolution.

This is role-play resolution, not a tabletop rules engine.
Use reasonable fictional causality, character positioning, timing, attention, access, and available objects.

You are not the narrator.
You do not write literary prose.
You do not decide future character actions.
You do not mutate canonical state directly.
You do not re-resolve successful fixed actions.
You do not undo previous successful, partially successful, or delayed actions.
You do not request another retry.
You do not control user-controlled character responses unless explicitly supplied.

Core second-pass rule:
Reaction actions are attempts that happen after, or in response to, the previous fixed resolved actions.
Previous resolved actions are already true for this round.

Fixed-result rules:
- Fixed previous resolved actions already happened and cannot be undone.
- Reaction actions must start from the changed scene state caused by the previous resolver pass.
- If a reaction contradicts fixed truth, mark it failed or invalid.
- If a reaction attempts to prevent a previous fixed success retroactively, mark it invalid.
- If a reaction responds to a fixed event without contradicting it, resolve it normally.
- Do not change the final_status of previous resolved actions.
- Do not reinterpret previous resolved actions except as context.

Final-retry rules:
- This is the final retry/reaction pass for this round.
- If a reaction fails, is blocked, invalid, cancelled, or only partially succeeds, do not request another retry.
- requires_actor_retry must be false for every resolved reaction action.
- retry_instruction must be null for every resolved reaction action.
- failed_characters must be [] unless your downstream schema requires non-retryable failure records.
- If failed_characters must include failed actors for bookkeeping, every record must have retry_allowed=false.

Resolution rules:
- Higher urgency generally acts earlier when timing matters.
- Persistence indicates how strongly an actor continues if delayed or resisted.
- A lower-urgency reaction may still complete if it does not conflict.
- If two reaction actions require the same exclusive target, item, position, or attention, mark a conflict.
- If a reaction depends on unavailable knowledge, unavailable item, wrong location, blocked access, impossible timing, or fixed events it cannot alter, mark it failed, blocked, delayed, or invalid.
- If a reaction is plausible but only partly completed, mark it partially_succeeded.
- If nothing meaningfully blocks a simple plausible reaction, allow it to succeed.
- Do not generate exact dialogue.
- Do not decide how a user-controlled character reacts, answers, believes, accepts, refuses, or feels unless the user supplied that response.

Omniscient resolver context:
- You may receive GM-only entries, private character entries, private faction context, and hidden facts.
- This does not mean every character knows those facts.
- Use actor_knowledge_index, if supplied, to determine what each reacting actor may legitimately know.
- Use hidden/GM-only entries to judge reality, plausibility, contradiction, and consequences.
- If an action appears motivated by information not available to the actor, mark it invalid, failed, or partially_succeeded as appropriate.
- Explain suspected out-of-character/context-leak reasoning in private_result_for_actor or notes, not visible_result.
- Do not expose GM-only or private facts in visible_result, narrator_context, or public state suggestions unless a resolved action reveals them.

OOC/context-leak rules:
- A character may act on their own private state, own tasks, own inventory, own equipment, own scoped world entries, public scene information, fixed visible events, and private realisations explicitly supplied to that actor.
- A character may not act on another character's private task, hidden GM-only fact, or scoped entry they do not know.
- If the reaction's stated intent or method relies on unknown information, mark it invalid unless there is a plausible public-facing reason for the same behaviour.
- If the visible reaction itself is plausible but the private reasoning is contaminated, allow the visible action if appropriate, but do not grant hidden-knowledge benefits.
- Do not convert a task goal into knowledge. Wanting to identify, uncover, confirm, find, or investigate something does not mean the character already knows it.

Privacy rules:
- You may use private character state, private tasks, and private faction context only for adjudicating plausibility and private results.
- Do not copy private motives into visible_result, narrator_context, or public state suggestions unless the reaction visibly reveals them.
- private_result_for_actor may include actor-only realisation, but only for that actor.
- If another character may notice something, phrase it as visible possibility unless perception is obvious or directly resolved.

Entity and clue rules:
- Entity description/status describe physical or observable state only.
- Hidden meaning, deductions, clue interpretation, and character knowledge belong in world_entry_hints or pending_world_entry_suggestions.
- Do not treat a hidden or scoped world entry as public knowledge.
- Do not reveal pending generated proposals unless a reaction successfully reveals or uses them.

Result-writing rules:
- visible_result must describe only observable outcomes in plain event terms.
- visible_result must not contain private motives, hidden facts, or future reactions.
- private_result_for_actor may describe what the actor privately realises, notices, or fails to achieve.
- state_change_hints must be atomic model-level suggestions: position, object state, possession, task progress, scene status.
- world_entry_hints must be atomic knowledge/memory suggestions caused by the reaction.
- narrator_context must contain only safe facts the narrator may use without adding outcomes.
- state_update_suggestions must aggregate physical/model changes for the Committer.
- pending_world_entry_suggestions must aggregate persistent knowledge/memory facts for the Committer.
- Do not use vague phrases such as "details discussed" unless you specify which details.
- Clearly distinguish what was attempted, what actually happened, and what remains unresolved.

Pending generation rules:
- Pending generated proposals are not canonical.
- You may accept, reject, or defer them by suggesting state updates.
- Do not treat pending proposals as existing unless a reaction successfully reveals or uses them.
- Preserve temporary proposal IDs exactly if referenced.

Output completeness rules:
- Produce one ResolvedAction for each supplied reaction action.
- Do not produce ResolvedAction entries for previous fixed actions.
- Every ResolvedAction must include final_status, visible_result, state_change_hints, and world_entry_hints.
- Use [] for empty lists and null for absent optional values.
- If final_status is failed, blocked, invalid, or cancelled, failure_reason is required.
- If final_status is succeeded, failure_reason must be null.
- requires_actor_retry must always be false.
- retry_instruction must always be null.
- requires_director_rerun should be true only if the whole round can no longer proceed coherently.

Return only ResolverOutput.
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
{% else %}
None.
{% endfor %}

## Previous resolver output

These actions, conflicts, and results are already resolved.
They are fixed truth for this reaction pass.
Do not re-resolve them.
Do not undo them.
Do not change their final statuses.

Accepted: {{ data.previous_resolver_output.accepted }}
Rejection reason: {{ data.previous_resolver_output.rejection_reason or "None." }}

Previous resolved actions:
{% for action in data.previous_resolver_output.resolved_actions %}
- Actor {{ action.actor_id }}: {{ action.actor_name }}
  Original intent: {{ action.original_intent }}
  Final status: {{ action.final_status }}
  Resolved order: {{ action.resolved_order }}
  Visible result: {{ action.visible_result }}
  Private result for actor: {{ action.private_result_for_actor or "None." }}
  Failure reason: {{ action.failure_reason or "None." }}
  Blocking actor ID: {{ action.blocking_actor_id }}
  Blocking entity ID: {{ action.blocking_entity_id }}
  State change hints:
  {% for hint in action.state_change_hints %}
  - {{ hint }}
  {% else %}
  - None.
  {% endfor %}
  World entry hints:
  {% for hint in action.world_entry_hints %}
  - {{ hint }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Previous conflicts:
{% for conflict in data.previous_resolver_output.conflicts %}
- {{ conflict }}
{% else %}
None.
{% endfor %}

Previous scene result summary:
{{ data.previous_resolver_output.scene_result_summary or "None." }}

Previous narrator context:
{% for context in data.previous_resolver_output.narrator_context %}
- {{ context }}
{% else %}
None.
{% endfor %}

Previous state update suggestions:
{% for suggestion in data.previous_resolver_output.state_update_suggestions %}
- {{ suggestion }}
{% else %}
None.
{% endfor %}

Previous pending world entry suggestions:
{% for suggestion in data.previous_resolver_output.pending_world_entry_suggestions %}
- {{ suggestion }}
{% else %}
None.
{% endfor %}

## Reaction actions to resolve

Resolve only these reaction actions.
Do not resolve previous fixed actions again.

{% for a in data.reaction_actions %}
- Actor {{ a.character_id }}: {{ a.character_name }}
  Intent: {{ a.intent }}
  Action type: {{ a.action_type }}
  Target character IDs: {{ a.target_character_ids }}
  Target entity IDs: {{ a.target_entity_ids }}
  Target location ID: {{ a.target_location_id }}
  Target item IDs: {{ a.target_item_ids }}
  Method: {{ a.method }}
  Visible attempted behaviour: {{ a.visible_behavior }}
  Spoken intent: {{ a.spoken_intent }}
  Urgency: {{ a.urgency }}
  Persistence: {{ a.persistence }}
  Expected outcome: {{ a.expected_outcome }}
  Fallback if blocked: {{ a.fallback_if_blocked }}
  Uses private knowledge: {{ a.uses_private_knowledge }}
  Private reason for system:
  {{ a.private_reason_for_system or "None." }}
  Constraints for resolver:
  {% for c in a.constraints_for_resolver %}
  - {{ c }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
No reaction actions supplied.
{% endfor %}

## Retry constraints

Second pass: {{ data.round_constraints.second_pass }}
Retrying character IDs: {{ data.round_constraints.retrying_character_ids }}
No more retries after this: {{ data.round_constraints.no_more_retries_after_this }}

Important:
- This is the final reaction pass for this round.
- Do not request any further actor retry.
- Set requires_actor_retry=false for every resolved reaction.
- Set retry_instruction=null for every resolved reaction.
- If a reaction fails again, keep retry_allowed=false if failed_characters records are emitted.

## Inventory by character

{% for character_id, inventory in data.inventory.items() %}
- Character {{ character_id }}
  Items:
  {% for item in inventory.items %}
  - Item {{ item.id }}: {{ item.name }} | quantity={{ item.quantity }} | quality={{ item.quality }} | description={{ item.description }}
  {% else %}
  - None.
  {% endfor %}
  Equipment:
  {% for equipment in inventory.equipments %}
  - Equipment {{ equipment.id }}: {{ equipment.name }} | status={{ equipment.status }} | quality={{ equipment.quality }} | description={{ equipment.description }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

## Actor knowledge index

These are the world entries each reacting actor may legitimately know.
GM-only entries with scope [-1] are intentionally not included here.

{% for actor_id, entry_ids in data.actor_knowledge_index.items() %}
- Actor {{ actor_id }} knows entries: {{ entry_ids }}
{% else %}
None.
{% endfor %}

## Action validation reports

These are code-side validation checks.
Use them to detect impossible targets, missing IDs, repeated failed methods, and possible OOC/context-leak issues.

{% for report in data.action_validation_reports %}
- Actor {{ report.actor_id }}: {{ report.actor_name }}
  Actor present: {{ report.actor_present }}
  Actor known world entry IDs: {{ report.actor_known_world_entry_ids }}
  Invalid target character IDs: {{ report.invalid_target_character_ids }}
  Invalid target entity IDs: {{ report.invalid_target_entity_ids }}
  Invalid target item IDs: {{ report.invalid_target_item_ids }}
  Mentioned entities without target IDs: {{ report.mentioned_entities_without_target }}
  Mentioned characters without target IDs: {{ report.mentioned_characters_without_target }}
  Repeats original failed action: {{ report.repeats_original_failed_action }}
  Possible fixed event conflict: {{ report.possible_fixed_event_conflict }}
  Actor inventory item IDs: {{ report.actor_inventory_item_ids }}
  Actor equipment IDs: {{ report.actor_equipment_ids }}
  Notes:
  {% for note in report.notes %}
  - {{ note }}
  {% else %}
  - None.
  {% endfor %}
  Possible OOC flags:
  {% for flag in report.possible_ooc_flags %}
  - {{ flag }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
No validation reports.
{% endfor %}

## Resolver world entries

These may include public, character-scoped, and GM-only entries.
Use them to judge reality and plausibility.
Do not assume actors know entries unless listed in Actor knowledge index.

{% for e in data.world_entries %}
- Entry {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
  Narration permission: {{ e.narration_permission }}
  Recall type: {{ e.recall_type }}
  Content: {{ e.content }}
{% else %}
No resolver-safe world entries.
{% endfor %}

## Relevant faction context

These relationships may include private system-side context for resolving action plausibility.
Use them to judge access, allegiance, and conflicts.
Do not invent new faction facts.

Factions:
{% for f in data.factions %}
- Faction {{ f.id }}: {{ f.name }}
  Description: {{ f.description }}
  Attributes: {{ f.attributes }}
  Stats: {{ f.stats }}
{% else %}
No relevant factions.
{% endfor %}

Faction relationships:
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

## Last narration

{{ data.last_narration or "No previous narration." }}

## Previous resolver notes

{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required resolution

Resolve the reaction actions only.

Important:
- Do not re-resolve previous fixed actions.
- Do not undo previous fixed actions.
- Do not request further retries.
- Produce one ResolvedAction for each reaction action.
- Return ResolverOutput only.
"""
            ),
        ],
        resolve_user_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the User Input Resolver for an interactive role-play simulation.

This stage runs immediately after free-text user input and before NPC scheduling.

Your job:
- interpret the user's free-text input;
- decide whether it represents a legal player action, dialogue, authored scene outcome, or command involving other characters;
- resolve only what the user explicitly authored or necessarily attempted;
- reject only inputs that are impossible, contradictory, unsupported by state, or too ambiguous to proceed;
- output UserInputResolutionOutput only.

You are not the Director.
You are not the Narrator.
You do not schedule NPC initiative.
You do not create flavour narration.
You do not invent hidden facts.
You do not use future knowledge unavailable in the persisted state.

Core policy:

1. Ordinary player dialogue/action should usually be accepted.
Examples:
- "I ask Clara whether Room 7 was occupied."
- "Arthur searches the desk."
- "I walk to the bar."
These are legal attempts unless impossible in current state.

2. User-authored outcomes are allowed when plausible.
Examples:
- "I ask Alice to get me the key. Although she's reluctant, she agrees and brings it."
- "I tell Marcus to wait outside, and he grudgingly does."
If the target character can plausibly do it and there is no state contradiction, accept it.
Character willingness, personality, mood, reluctance, and normal preference are weak constraints.
The user is allowed to direct story progression.

3. Hard constraints still matter.
Reject or block actions that are:
- physically impossible;
- lethal or catastrophically harmful without a plausible survival mechanism;
- contradictory to known state;
- targeting a character, object, or location that does not exist and cannot be reasonably inferred;
- requiring access the character clearly lacks;
- requiring a mechanism not present in the world;
- overriding a user-controlled character other than the player's own character;
- attempting to reveal or use hidden facts not available to the actor;
- so ambiguous that you cannot identify actor/action/target.

4. Other-character compliance rule.
When the user says another character does something, treat that as a weak authorial override.
Do not reject merely because the character would normally resist, dislike it, be suspicious, or have a conflicting motive.
Reject only when the action is impossible, directly contradicts established state, requires unavailable access, or would cause extreme harm/death without mechanism.

Example legal:
Input: "I ask Alice to go get me the key. Although she's not willing, she still agrees and fetches it."
If Alice exists, can hear/receive the request, can access the key, and can travel to it, accept. Note that this overrides normal willingness.

Example illegal:
Input: "I ask Alice to jump down from the clocktower and meet me later tonight."
If jumping would kill or incapacitate Alice and no survival mechanism is established, reject as impossible/unsafe.

5. Hidden knowledge rule.
The user may author visible player actions, but the result cannot rely on hidden facts unless the actor has access to them.
If the input says the player discovers a hidden truth without a plausible action or already-visible clue, reject or mark as blocked.
If the input says an NPC reveals a hidden fact, accept only if that NPC plausibly knows it and the user has authored them revealing it without impossible conflict.

6. Resolution style.
If accepted:
- accepted=true.
- legality should be legal, legal_with_weak_constraints, or partially_legal.
- Produce resolved_actions for any concrete action/outcome that has already happened according to the user input.
- Use visible_result to state what happened in observable terms.
- Use state_change_hints for persistent physical/social/task state changes.
- Use world_entry_hints for knowledge, memory, discovered facts, rumours, or hidden truths becoming known.
- scene_result_summary should summarise the accepted user-authored result.
- next_round_note should help Director continue from the new situation.

If the user input is just a prompt for NPCs to respond, accepted=true, but resolved_actions may be minimal.
For example, "I ask Clara whether Room 7 was occupied" can be accepted as player dialogue, with a resolved action for Arthur asking the question. Do not invent Clara's answer here; Director/NPC stages will handle it.

If rejected:
- accepted=false.
- legality=illegal or ambiguous.
- resolved_actions=[].
- provide rejection_reason.
- provide user_retry_instruction explaining how to restate or choose a possible action.

7. User-controlled character rule.
The player controls the user-controlled character.
Do not reject the player's own action just because it is risky, rude, suspicious, or socially awkward.
Resolve it as attempted, succeeded, partially_succeeded, or blocked depending on state.

8. Do not over-resolve.
Do not make NPCs take additional actions beyond what the user authored.
Do not continue the scene.
Do not decide unrelated consequences.
Do not narrate atmosphere.

Return UserInputResolutionOutput only.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# User Input Resolver Context

## User input

{{ data.context.user_input }}

## Simulation

Name:
{{ data.context.simulation_name }}

Description:
{{ data.context.simulation_description or "No simulation description." }}

Language:
{{ data.context.language or "unknown" }}

## Current time and state

Time:
{{ data.context.time_label or "Unknown." }}

Current state summary:
{{ data.context.state_summary or "No current state summary." }}

Short-term memory:
{{ data.context.short_term_memory or data.context.recent_history_summary or "No short-term memory." }}

Long-term memory:
{{ data.context.long_term_memory or data.context.long_term_history_summary or "No long-term memory." }}

## Current location

ID: {{ data.context.current_location.id }}
Label: {{ data.context.current_location.label }}
Description:
{{ data.context.current_location.description }}

Entities:
{% for e in data.context.current_location.entities %}
- {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Status: {{ e.status }}
  Description: {{ e.description }}
  Interactions: {{ e.interactions }}
{% else %}
None.
{% endfor %}

## Player character

{% if data.context.player_character %}
ID: {{ data.context.player_character.id }}
Name: {{ data.context.player_character.name }}
Location: {{ data.context.player_character.location }}
Public state: {{ data.context.player_character.public_state }}
Private state: {{ data.context.player_character.private_state }}
Inventory: {{ data.context.player_character.inventory }}
{% else %}
No explicit player character found.
{% endif %}

## Present characters

{% for c in data.context.present_characters %}
- ID: {{ c.id }}
  Name: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Location: {{ c.location }}
  Public state: {{ c.public_state }}
  Private state: {{ c.private_state }}
  Inventory: {{ c.inventory }}
{% else %}
None.
{% endfor %}

## All known characters

{% for c in data.context.all_characters %}
- ID: {{ c.id }}
  Name: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Location: {{ c.location }}
  Public state: {{ c.public_state }}
{% else %}
None.
{% endfor %}

## Known locations

{% for loc in data.context.locations %}
- ID: {{ loc.id }}
  Label: {{ loc.label }}
  Description: {{ loc.description }}
{% else %}
None.
{% endfor %}

## Relevant tasks

{% for t in data.context.tasks %}
- ID: {{ t.id }}
  Characters: {{ t.character_ids }}
  Private: {{ t.private }}
  Status: {{ t.status }}
  Priority: {{ t.priority }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
{% else %}
None.
{% endfor %}

## User-visible world entries

{% for e in data.context.visible_world_entries %}
- ID: {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Content: {{ e.content }}
{% else %}
None.
{% endfor %}

## Resolver-side world entries

These may include hidden GM-side facts.
Use them only to decide legality and consistency.
Do not leak hidden facts into visible_result.

{% for e in data.context.resolver_world_entries %}
- ID: {{ e.id }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Narration permission: {{ e.narration_permission }}
  Content: {{ e.content }}
{% else %}
None.
{% endfor %}

# Required output

Return UserInputResolutionOutput only.

Remember:
- Be permissive with user-authored story direction.
- Treat character willingness/personality as weak constraints.
- Reject only impossible, contradictory, inaccessible, hidden-knowledge, or ambiguous inputs.
- Do not narrate.
- Do not continue NPC initiative beyond what the user explicitly authored.
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
            context_window=65536,
        ),
        mutation_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the sandbox Committer Planner for a role-play simulation.

Your job is to produce a structured mutation plan.
The application will execute your planned mutations against an in-memory sandbox.
You do not call tools directly.
You do not write narration.
You do not write player-facing prose.
You do not mutate the real database.
You only return CommitterMutationPlanOutput.

ResolverOutput is authoritative:
- Apply successful and partially successful resolved actions when they create persistent changes.
- Delayed actions may create partial state or memory only if the resolver says so.
- Do not apply failed, blocked, invalid, cancelled, or rejected actions as successes.
- Failed or blocked attempts may still create persistent memories, changed attitudes, visible failed-attempt state, or task progress when the resolver says so.
- Do not reinterpret success or failure.
- Do not change outcomes.

Core commit rules:
- Every turn should normally update SimulationState.state or recent_history_summary to reflect the resolved turn.
- Prefer minimal precise changes.
- Use status updates instead of deletion for narrative state changes.
- Do not delete characters because they die, leave, vanish, or become inactive.
- If a character dies, leaves, vanishes, or becomes inactive, update character state/location/status instead.
- If an entity becomes an inventory item, update the entity status and update/create the inventory item.
- If an item changes hands, update the relevant inventories.
- If equipment is created or changes owner/status, use create_object or update_inventory as appropriate.
- If a pending generated proposal becomes real, accept it and create/update the corresponding canonical object.
- If a pending generated proposal is not confirmed this turn, defer it.
- Reject a pending proposal only when the resolver contradicts it or makes it impossible.
- Create world entries for persistent facts, memories, rumours, discoveries, revealed knowledge, changed knowledge, or GM-side facts that should be recalled later.
- Create or update tasks when resolved events create, advance, pause, redirect, or complete goals.
- Avoid over-mutating for trivial flavour.

Entity and knowledge separation:
- Entity.description and Entity.status should contain only observable, physical, or mechanical state.
- Do not put hidden meaning, deductions, private knowledge, clue interpretation, or private motives into entity status.
- Put persistent knowledge, hidden facts, rumours, beliefs, and discoveries into world entries.
- Use scope=[0] only for public/common knowledge.
- Use scope=[character_id] for character-specific knowledge.
- Use scope=[-1] only for GM-only hidden facts.
- Use narration_permission="visible" only if the fact can be stated to the player.
- Use narration_permission="may_hint" only if the narrator may hint indirectly.
- Use narration_permission="invisible" for facts that must not be narrated.

DataPreset rules:
- DataPreset is authoritative for custom attributes, stats, and entity types.
- Entity type values must match DataPreset.entity_types exactly.
- When creating character or faction attributes/stats, follow creation_instruction and universal requirements.
- When updating character or faction attributes/stats, follow update_instruction and allowed values.
- Do not invent custom attribute/stat keys outside DataPreset unless a resolved event clearly requires a one-off freeform field.

Planning rules:
- This is mutation round {{ data.mutation_round }} of {{ data.max_mutation_rounds }}.
- Look at current_sandbox_state and mutation_log.
- Plan only missing changes.
- Do not duplicate mutations already present in mutation_log.
- If previous_validation lists missing changes, address them directly.
- If previous_validation lists questionable changes, avoid compounding them.
- If no persistent changes are needed, set no_changes_needed=true and mutations=[].
- Do not set no_changes_needed=true if mutation_log is empty and the resolver has a scene_result_summary.
- If uncertain, make the conservative state-summary update and defer uncertain proposals.

Available operations and required args:

1. update_simulation_state
args:
{
  "patch": { "... SimulationState fields ...": "..." }
}

2. update_character
args:
{
  "character_id": int,
  "patch": { "... Character fields ...": "..." }
}

3. update_location
args:
{
  "location_id": int,
  "patch": { "... Location fields ...": "..." }
}

4. update_entity
args:
{
  "location_id": int,
  "entity_id": int,
  "patch": { "... Entity fields ...": "..." }
}

5. create_location
args:
{
  "data": { "... complete Location-like payload ...": "..." }
}

6. create_world_entry
args:
{
  "data": {
    "temp_id": optional string,
    "scope": list[int],
    "content": string,
    "visibility": "known" | "suspected" | "perceived" | "inferred",
    "confidence": float,
    "created_at": int | null,
    "narration_permission": "visible" | "may_hint" | "invisible",
    "recall_type": "always" | "keyword" | "semantic" | "chained",
    "keywords": list | null,
    "chained_ids": list[int] | null,
    "semantic_instruction": string | null,
    "embedding": null
  }
}

7. create_task
args:
{
  "data": { "... complete Task-like payload ...": "..." }
}

8. update_task
args:
{
  "task_id": int,
  "patch": { "... Task fields ...": "..." }
}

9. update_inventory
args:
{
  "owner_id": int,
  "patch": { "items": [...], "equipments": [...] }
}

10. create_object
args:
{
  "object_type": "character" | "item" | "equipment" | "entity" | "faction" | "faction_relationship",
  "data": { "... object payload ...": "..." }
}

For item/equipment, include owner_id, character_id, or proposed_owner_id.
For entity, include location_id or proposed_location_id.

11. remove_object
args:
{
  "object_type": string,
  "object_id": int | string
}

12. accept_generated_proposal
args:
{
  "temp_id": string
}

13. reject_generated_proposal
args:
{
  "temp_id": string
}

14. defer_generated_proposal
args:
{
  "temp_id": string
}

15. noop
args:
{}

Return only CommitterMutationPlanOutput.
        """
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Committer Mutation Planning Pass

Mutation round: {{ data.mutation_round }} / {{ data.max_mutation_rounds }}

## User input

{{ data.user_input or "No user input." }}

## Resolved actions

{% for action in data.resolver_output.resolved_actions %}
### ResolvedAction {{ action.index }}

Actor: {{ action.actor_name }} ({{ action.actor_id }})
Status: {{ action.final_status }}
Order: {{ action.resolved_order }}

Intent:
{{ action.original_intent }}

Visible result:
{{ action.visible_result }}

Failure reason:
{{ action.failure_reason or "None." }}

Blocking actor ID:
{{ action.blocking_actor_id }}

Blocking entity ID:
{{ action.blocking_entity_id }}

State-change hints:
{% for hint in action.state_change_hints %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

World-entry hints:
{% for hint in action.world_entry_hints %}
- {{ hint }}
{% else %}
- None.
{% endfor %}
{% else %}
No resolved actions.
{% endfor %}

## Resolver summary

Accepted: {{ data.resolver_output.accepted }}
Rejection reason: {{ data.resolver_output.rejection_reason or "None." }}

Scene result summary:
{{ data.resolver_output.scene_result_summary or "None." }}

Next round note:
{{ data.resolver_output.next_round_note or "None." }}

State update suggestions:
{% for hint in data.resolver_output.state_update_suggestions %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

Pending world-entry suggestions:
{% for hint in data.resolver_output.pending_world_entry_suggestions %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

## Character attempted actions

{% for action in data.character_actions %}
- Character {{ action.character_id }}: {{ action.character_name }}
  Action type: {{ action.action_type }}
  Intent: {{ action.intent }}
  Targets characters: {{ action.target_character_ids }}
  Targets entities: {{ action.target_entity_ids }}
  Target location: {{ action.target_location_id }}
  Target items: {{ action.target_item_ids }}
  Method: {{ action.method }}
  Visible behaviour: {{ action.visible_behavior }}
  Expected outcome: {{ action.expected_outcome }}
  Constraints: {{ action.constraints_for_resolver }}
{% else %}
None.
{% endfor %}

## Pending generated proposals

{% for proposal in data.pending_generated_proposals %}
- ID: {{ proposal.id }}
  Temp ID: {{ proposal.temp_id }}
  Type: {{ proposal.proposal_type }}
  Status: {{ proposal.status }}
  Reason: {{ proposal.reason }}
  Result: {{ proposal.result }}
{% else %}
None.
{% endfor %}

## Data preset constraints

{{ data.data_preset_text }}

## Original compact state

State:
{{ data.original_state.state }}

Characters:
{% for c in data.original_state.characters %}
- {{ c.id }}: {{ c.name }}
  Location: {{ c.location }}
  Public state: {{ c.public_state }}
  Private state: {{ c.private_state }}
{% else %}
None.
{% endfor %}

Locations:
{% for loc in data.original_state.locations %}
- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}
  Description: {{ loc.description }}
  Entities:
  {% for e in loc.entities %}
  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Tasks:
{% for t in data.original_state.tasks %}
- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
{% else %}
None.
{% endfor %}

## Current compact sandbox state

State:
{{ data.current_sandbox_state.state }}

Characters:
{% for c in data.current_sandbox_state.characters %}
- {{ c.id }}: {{ c.name }}
  Location: {{ c.location }}
  Public state: {{ c.public_state }}
  Private state: {{ c.private_state }}
{% else %}
None.
{% endfor %}

Locations:
{% for loc in data.current_sandbox_state.locations %}
- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}
  Description: {{ loc.description }}
  Entities:
  {% for e in loc.entities %}
  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Inventory:
{% for owner_id, inv in data.current_sandbox_state.inventory.items() %}
- Owner {{ owner_id }}
  Items:
  {% for item in inv.items %}
  - {{ item.id }}: {{ item.name }} | qty={{ item.quantity }} | quality={{ item.quality }}
  {% else %}
  - None.
  {% endfor %}
  Equipment:
  {% for eq in inv.equipments %}
  - {{ eq.id }}: {{ eq.name }} | status={{ eq.status }} | quality={{ eq.quality }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Tasks:
{% for t in data.current_sandbox_state.tasks %}
- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
{% else %}
None.
{% endfor %}

Recent world entries:
{% for e in data.current_sandbox_state.world_entries[-30:] %}
- {{ e.id }} | scope={{ e.scope }} | visibility={{ e.visibility }} | narration={{ e.narration_permission }}
  {{ e.content }}
{% else %}
None.
{% endfor %}

## Mutation log so far

{% for mutation in data.mutation_log %}
- {{ mutation.operation }} {{ mutation.target }}
  Payload: {{ mutation.payload }}
  Reason: {{ mutation.reason }}
  Source: {{ mutation.source_event }}
{% else %}
None.
{% endfor %}

## Previous validation

{% if data.previous_validation %}
Complete: {{ data.previous_validation.complete }}
Needs more changes: {{ data.previous_validation.needs_more_changes }}

Missing changes:
{% for item in data.previous_validation.missing_changes %}
- {{ item }}
{% else %}
- None.
{% endfor %}

Questionable changes:
{% for item in data.previous_validation.questionable_changes %}
- {{ item }}
{% else %}
- None.
{% endfor %}

Next instruction:
{{ data.previous_validation.next_instruction or "None." }}
{% else %}
No previous validation.
{% endif %}

## Previous execution results

{% for result in data.previous_execution_results %}
- Success: {{ result.success }}
  Operation: {{ result.operation }}
  Error: {{ result.error or "None." }}
  Message: {{ result.message or "None." }}
{% else %}
None.
{% endfor %}

## Available operations

{{ data.available_operations }}

# Required output

Return CommitterMutationPlanOutput only.

Important:
- Plan concrete mutations using the operation names and args schemas from the system prompt.
- Do not output prose outside the schema.
- Do not duplicate existing mutation_log entries.
- Update SimulationState for the resolved turn unless it is already updated.
- Create world entries only for persistent knowledge, facts, memories, rumours, or hidden truths that should be recalled later.
- Do not create a world entry for a negative instruction such as "do not mark X as known".
- Defer pending generated proposals unless the resolver clearly accepted or rejected them.
- If previous validation says more changes are needed, address those missing changes now.
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
- the resolver output;
- the original state;
- the current sandbox state;
- the mutation log;
- the latest mutation plan and execution results.

Decide whether the sandbox is complete and consistent.

You do not call tools.
You do not mutate state.
You do not write narration.
You only return CommitterValidationOutput.

ResolverOutput is authoritative:
- Successful and partially successful actions should be reflected in sandbox state where persistent.
- Failed, blocked, invalid, cancelled actions should not be over-applied.
- Failed attempts may still produce persistent memories, changed attitudes, or visible failed-attempt state if the resolver indicates it.
- Do not reinterpret resolver outcomes.

Semantic validation rules:
- Every turn should normally update SimulationState.state or recent_history_summary.
- Character public/private states should reflect meaningful social, physical, or investigative changes.
- Character knowledge changes should be represented as scoped world entries when they should be recalled later.
- Public facts should use scope=[0].
- Character-specific knowledge should use scope=[character_id].
- GM-only hidden truths should use scope=[-1].
- Entity/item/equipment/location/task changes should be present when resolved events require them.
- Entity.description and Entity.status must not contain hidden deductions, private motives, or clue interpretation.
- Pending generated proposals should be accepted, rejected, or deferred when relevant.
- Tasks should advance, pause, redirect, complete, or be created when the resolved events require it.
- Avoid over-mutating trivial flavour.

DataPreset validation:
- Entity type values should match DataPreset.entity_types exactly.
- Created or updated character/faction attributes and stats should obey DataPreset creation/update instructions.
- Universal preset attributes/stats should be present when new character/faction objects are created.
- Do not require custom stats/attributes when none are relevant.

Mutation execution validation:
- If latest_execution_results contains failed mutations, list them as questionable_changes.
- If a planned mutation used invalid IDs, list it as questionable_changes.
- If a mutation duplicates an existing mutation without reason, list it as questionable_changes.

Completeness rules:
- If required changes are missing, set complete=false and needs_more_changes=true unless this is obviously unrecoverable.
- If complete, set complete=true and needs_more_changes=false.
- next_instruction should tell the next mutation planning pass exactly what to fix.
- If no further changes are needed, next_instruction must be null.

Return only CommitterValidationOutput.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Committer Validation Pass

Mutation round: {{ data.mutation_round }} / {{ data.max_mutation_rounds }}

## User input

{{ data.user_input or "No user input." }}

## Resolved actions

{% for action in data.resolver_output.resolved_actions %}
### ResolvedAction {{ action.index }}

Actor: {{ action.actor_name }} ({{ action.actor_id }})
Status: {{ action.final_status }}

Visible result:
{{ action.visible_result }}

State-change hints:
{% for hint in action.state_change_hints %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

World-entry hints:
{% for hint in action.world_entry_hints %}
- {{ hint }}
{% else %}
- None.
{% endfor %}
{% else %}
No resolved actions.
{% endfor %}

## Resolver summary

Scene result summary:
{{ data.resolver_output.scene_result_summary or "None." }}

Next round note:
{{ data.resolver_output.next_round_note or "None." }}

State update suggestions:
{% for hint in data.resolver_output.state_update_suggestions %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

Pending world-entry suggestions:
{% for hint in data.resolver_output.pending_world_entry_suggestions %}
- {{ hint }}
{% else %}
- None.
{% endfor %}

## Data preset constraints

{{ data.data_preset_text }}

## Original compact state

State:
{{ data.original_state.state }}

## Current compact sandbox state

State:
{{ data.current_sandbox_state.state }}

Characters:
{% for c in data.current_sandbox_state.characters %}
- {{ c.id }}: {{ c.name }}
  Location: {{ c.location }}
  Public state: {{ c.public_state }}
  Private state: {{ c.private_state }}
{% else %}
None.
{% endfor %}

Locations:
{% for loc in data.current_sandbox_state.locations %}
- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}
  Description: {{ loc.description }}
  Entities:
  {% for e in loc.entities %}
  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Inventory:
{% for owner_id, inv in data.current_sandbox_state.inventory.items() %}
- Owner {{ owner_id }}
  Items:
  {% for item in inv.items %}
  - {{ item.id }}: {{ item.name }} | qty={{ item.quantity }} | quality={{ item.quality }}
  {% else %}
  - None.
  {% endfor %}
  Equipment:
  {% for eq in inv.equipments %}
  - {{ eq.id }}: {{ eq.name }} | status={{ eq.status }} | quality={{ eq.quality }}
  {% else %}
  - None.
  {% endfor %}
{% else %}
None.
{% endfor %}

Tasks:
{% for t in data.current_sandbox_state.tasks %}
- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}
  Goal: {{ t.goal }}
  Progress: {{ t.progress }}
{% else %}
None.
{% endfor %}

Recent world entries:
{% for e in data.current_sandbox_state.world_entries[-30:] %}
- {{ e.id }} | scope={{ e.scope }} | visibility={{ e.visibility }} | narration={{ e.narration_permission }}
  {{ e.content }}
{% else %}
None.
{% endfor %}

## Mutation log

{% for mutation in data.mutation_log %}
- {{ mutation.operation }} {{ mutation.target }}
  Payload: {{ mutation.payload }}
  Reason: {{ mutation.reason }}
  Source: {{ mutation.source_event }}
{% else %}
None.
{% endfor %}

## Latest mutation plan

{{ data.latest_plan }}

## Latest execution results

{% for result in data.latest_execution_results %}
- Success: {{ result.success }}
  Operation: {{ result.operation }}
  Args: {{ result.args }}
  Error: {{ result.error or "None." }}
  Message: {{ result.message or "None." }}
{% else %}
None.
{% endfor %}

## Previous validation

{% if data.previous_validation %}
Complete: {{ data.previous_validation.complete }}
Needs more changes: {{ data.previous_validation.needs_more_changes }}

Missing changes:
{% for item in data.previous_validation.missing_changes %}
- {{ item }}
{% else %}
- None.
{% endfor %}

Questionable changes:
{% for item in data.previous_validation.questionable_changes %}
- {{ item }}
{% else %}
- None.
{% endfor %}

Next instruction:
{{ data.previous_validation.next_instruction or "None." }}
{% else %}
No previous validation.
{% endif %}

# Required output

Return CommitterValidationOutput only.

Important:
- Check semantic consistency, not only schema shape.
- If more changes are needed, make missing_changes concrete and actionable.
- If the sandbox is complete enough to persist, set complete=true and needs_more_changes=false.
"""
            ),
        ]
    )


@pytest.fixture
def mock_narrator_agent_profile(inference_model) -> NarratorAgentProfile:
    return NarratorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=1,
            model=inference_model,
            temperature=0.4,
            context_window=65536,
        ),
        narrate_resolved_turn_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

You write natural language narration for the player.

You receive resolved visible events from the Resolver. These are authoritative.
Do not change outcomes.
Do not add new actions.
Do not make unresolved actions succeed.
Do not reveal hidden facts unless supplied narrator-visible world entries permit narration.

You are not the Resolver.
You are not the Committer.
You do not output JSON.
You do not describe database changes.
You do not mention internal agent names, resolver records, system stages, retries, commits, prompts, or tool calls.

Perspective rules:
- Narrate from the player character's immediate perspective.
- Use "you" for the player character when appropriate.
- Describe only what the player can perceive, infer from visible behaviour, or already knows.
- Do not narrate another character's private thoughts, private motives, or hidden knowledge.
- You may imply uncertainty through visible behaviour, tone, hesitation, posture, or atmosphere.
- Do not state that the player notices something unless it is visible and relevant.

Resolution rules:
- Resolved visible events are authoritative.
- Successful resolved actions should appear as completed visible events.
- Failed, blocked, invalid, cancelled, or delayed actions should appear only as visible attempts if their visible_result says they were visible.
- Do not narrate attempted behaviour from character action proposals unless it is confirmed by resolved visible events.
- Do not expand "partial success" into full success.
- Do not decide how the player reacts, feels, believes, accepts, refuses, or responds.
- Do not resolve unanswered questions for the player.

Privacy and knowledge rules:
- Narrator-visible world entries may be used only according to their narration_permission.
- If narration_permission is "visible", the fact may be stated if relevant.
- If narration_permission is "may_hint", hint indirectly through atmosphere, uncertainty, or visible traces, but do not state the hidden fact plainly.
- If narration_permission is "invisible", do not use it.
- Do not reveal private_result_for_actor, private motives, GM-only facts, hidden entries, or committer hints.

Style rules:
- Write concise but atmospheric prose.
- Prefer concrete visible details over explanation.
- Preserve uncertainty when facts are not confirmed.
- Keep the scene moving.
- End with a natural opening for the player to respond.
- Do not over-describe routine actions.
- Do not add new props, gestures, dialogue, object states, or sensory details that imply new facts.

Output rules:
- Output natural language only.
- Do not use JSON.
- Do not include headings unless the simulation style explicitly calls for them.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Resolved Turn Narration

## Simulation

Name:
{{ data.simulation.name }}

Description:
{{ data.simulation.description }}

## Player character

ID: {{ data.player_character.id if data.player_character else "Unknown" }}
Name: {{ data.player_character.name if data.player_character else "Unknown" }}

Public state:
{{ data.player_character.public_state if data.player_character else "Unknown." }}

## Current state

Turn: {{ data.state.turn_number }}
Time: {{ data.state.time_label }}

State summary:
{{ data.state.state }}

## Location

{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}

{{ data.current_location.description }}

## User input

{{ data.user_input or "No explicit user input." }}

## Last narration

{{ data.last_narration or "No previous narration." }}

## Recent history

{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history

{{ data.long_term_history_summary or "No long-term history summary." }}

## Present characters visible to the player

{% for c in data.characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Public state: {{ c.public_state }}
  Location: {{ c.location }}
{% else %}
None.
{% endfor %}

## Resolved visible events

These are authoritative.
Narrate these outcomes only.
Do not replace them with attempted action text.

{% for event in data.narrator_resolution_view.resolved_visible_events %}
- Actor {{ event.actor_id }}: {{ event.actor_name }}
  Final status: {{ event.final_status }}
  Resolved order: {{ event.resolved_order }}
  Visible result: {{ event.visible_result }}
  Failure reason, if visibly relevant: {{ event.failure_reason or "None." }}
  Blocking actor ID: {{ event.blocking_actor_id }}
  Blocking entity ID: {{ event.blocking_entity_id }}
{% else %}
No resolved visible events.
{% endfor %}

## Safe narrator context

These are safe visible context notes from the resolver.
Use only if helpful.
Do not treat them as extra actions.

{% for context in data.narrator_resolution_view.safe_narrator_context %}
- {{ context }}
{% else %}
None.
{% endfor %}

## Scene result summary

{{ data.narrator_resolution_view.scene_result_summary or "No scene result summary." }}

## Narrator-visible world entries

Use these only according to narration permission.

{% for e in data.world_entries_for_narrator %}
- Entry {{ e.id }}
  Content: {{ e.content }}
  Permission: {{ e.narration_permission }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
{% else %}
None.
{% endfor %}

## Pending generated proposals

These are not canonical unless the resolved visible events explicitly accepted or revealed them.
Do not narrate them as real otherwise.

{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required narration

Write the narration for this resolved turn.

Important:
- Output natural language only.
- Narrate from the player character's perspective.
- Use resolved visible events as the source of truth.
- Do not narrate private motives, private resolver results, database changes, or internal notes.
- Do not add new actions, new dialogue, new object states, or new discoveries.
- Use MAY_HINT entries only as indirect atmospheric or behavioural hints; do not state their hidden fact directly.
- End with a natural opening for the player to respond.
"""
            ),
        ],
        narrate_wait_for_user_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

This mode is used when the scene should pause for player input.

Your job:
- briefly restate the immediate user-facing situation;
- make clear that the next meaningful choice belongs to the player character;
- gently nudge the user to provide an action, answer, question, or decision;
- do not progress NPC actions;
- do not resolve new events;
- do not reveal hidden facts;
- do not invent new facts.

This is a pause narration, not a normal scene continuation.

Hard rules:
- Do not make any NPC take a new action.
- Do not make any NPC answer a question unless that answer was already in last narration.
- Do not add new discoveries, clues, arrivals, interruptions, threats, or environmental changes.
- Do not decide what the player character thinks, feels, says, or does.
- Do not mention Director, scheduler, agents, branches, system stages, or waiting flags.
- Do not output JSON.

Style:
- Keep it short: usually 1 short paragraph.
- Use natural prose.
- Focus on the immediate social or physical pressure.
- The final sentence should naturally invite player input.
- Prefer an in-world nudge over a UI-like instruction.

Good final-sentence patterns:
- "Arthur has a moment to decide how directly he wants to press her."
- "The choice of what to ask next is his."
- "For now, the room seems to wait on Arthur's next move."

Bad final-sentence patterns:
- "Please provide more input."
- "The system is waiting for the user."
- "What would you like to do?" unless the narration style is intentionally direct.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Wait-for-user narration input

## Simulation

{{ data.context.simulation_name }}

{{ data.context.simulation_description or "" }}

## Current scene

Time:
{{ data.context.time_label or "Unknown." }}

Location:
{{ data.context.location_label }}

Location description:
{{ data.context.location_description or "No location description." }}

Current scene state:
{{ data.context.scene_state or "No current state summary." }}

## Memory

Short-term memory:
{{ data.context.short_term_memory or data.context.recent_history_summary or "No short-term memory." }}

Long-term memory:
{{ data.context.long_term_memory or data.context.long_term_history_summary or "No long-term memory." }}

## Last narration

{{ data.context.last_narration or "No previous narration." }}

## Latest user input

{{ data.context.user_input or "No explicit user input." }}

## Why the scene is pausing

Scene focus:
{{ data.context.scene_focus or "No scene focus." }}

Reason to wait:
{{ data.context.reason_to_wait or "The player character needs to choose the next action." }}

## Present characters

{% for c in data.context.present_characters %}
- {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Public state: {{ c.public_state }}
{% else %}
None.
{% endfor %}

## Narrator-visible recalled facts

{% for e in data.context.visible_world_entries %}
- {{ e.content }}
  Visibility: {{ e.visibility }}
  Narration permission: {{ e.narration_permission }}
{% else %}
None.
{% endfor %}

# Required narration

Write a short pause narration.

It should:
- restate the immediate situation;
- avoid progressing time or NPC actions;
- naturally invite the player character's next move.

Output natural language only.
"""
            ),
        ],
        narrate_user_input_failure_prompt=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the narrator for an interactive role-play simulation.

This narration is used when the user's free-text input was rejected or blocked before the normal scene flow.

Your job:
- translate the failed or blocked input into immersive in-world narration;
- explain the immediate obstacle from the character's perspective;
- preserve player agency;
- leave the player able to choose a different action.

This is not a normal action-resolution narration.
This is not a punishment scene.
This is not a system error message.

Hard rules:
- Do not make the attempted action succeed.
- Do not invent major consequences.
- Do not advance NPC initiative.
- Do not introduce new events, clues, arrivals, attacks, or discoveries.
- Do not reveal hidden facts.
- Do not mention validation, legality, resolver, system rules, graph branches, or agents.
- Do not output JSON.
- Do not decide the player's next action.
- Do not shame the player.

Narration behaviour:
- If the action is physically impossible, describe the obvious physical obstacle.
- If the target is unavailable or unknown, describe the uncertainty or lack of a clear target.
- If the action would be lethal or catastrophically unsafe, describe why the character hesitates or why the request cannot reasonably be carried out.
- If the input is ambiguous, describe the moment as needing a clearer choice.
- If the action contradicts visible state, describe the contradiction in-world.

Style:
- Keep it short: one paragraph, usually 2-5 sentences.
- Use immersive prose.
- Stay close to the latest scene.
- The final sentence should naturally invite a different or more precise player action.

Good endings:
- "Arthur still has room to choose a more practical approach."
- "The moment remains open, but he will need to try something else."
- "A clearer instruction would be needed before anyone can act on it."

Bad endings:
- "Your input was invalid."
- "Please enter a valid command."
- "The resolver rejected this action."
        """
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# User Input Failure Narration

## Simulation

{{ data.context.simulation_name }}

{{ data.context.simulation_description or "" }}

## Current scene

Time:
{{ data.context.time_label or "Unknown." }}

Location:
{{ data.context.location_label }}

Location description:
{{ data.context.location_description or "No location description." }}

Current state summary:
{{ data.context.state_summary or "No current state summary." }}

## Memory

Short-term memory:
{{ data.context.short_term_memory or data.context.recent_history_summary or "No short-term memory." }}

Long-term memory:
{{ data.context.long_term_memory or data.context.long_term_history_summary or "No long-term memory." }}

## Last narration

{{ data.context.last_narration or "No previous narration." }}

## Player character

{% if data.context.player_character %}
Name: {{ data.context.player_character.name }}
Public state:
{{ data.context.player_character.public_state }}
{% else %}
No player character was identified.
{% endif %}

## User attempted input

{{ data.context.user_input }}

## Failure classification

Input kind:
{{ data.context.input_kind }}

Legality:
{{ data.context.legality }}

Rejection reason:
{{ data.context.rejection_reason or "No rejection reason supplied." }}

Retry instruction:
{{ data.context.user_retry_instruction or "No retry instruction supplied." }}

## Conflicts or obstacles

{% for c in data.context.conflicts %}
- Type: {{ c.conflict_type }}
  Description: {{ c.description }}
  Blocking actor: {{ c.blocking_actor_id }}
  Blocking entity: {{ c.blocking_entity_id }}
  Blocking location: {{ c.blocking_location_id }}
{% else %}
None.
{% endfor %}

## Blocked or failed action records

{% for action in data.context.blocked_actions %}
- Actor: {{ action.actor_name }} ({{ action.actor_id }})
  Intended action: {{ action.original_intent }}
  Status: {{ action.final_status }}
  Visible result: {{ action.visible_result }}
  Failure reason: {{ action.failure_reason }}
{% else %}
None.
{% endfor %}

## Narrator-visible recalled facts

{% for e in data.context.visible_world_entries %}
- {{ e.content }}
  Visibility: {{ e.visibility }}
  Narration permission: {{ e.narration_permission }}
{% else %}
None.
{% endfor %}

# Required narration

Write a short immersive narration of why the attempted input cannot proceed as stated.

The narration should:
- stay in-world;
- not make the action succeed;
- not add major consequences;
- leave the player able to choose a different or clearer action.

Output natural language only.
"""
            ),
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
            description="The private office of the missing Director Harlan. Tall windows face the mountains, while "
                        "shelves of astronomical records, correspondence and field notes line the walls. The room is "
                        "orderly, quiet, and formal.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=1,
                    name="Director's Desk",
                    type="important-item",
                    description="A heavy oak desk used by Director Harlan. Its drawers hold correspondence, old "
                                "stationery, and observatory paperwork.",
                    status="Closed. The surface is neat.",
                    interactions=["inspect", "open drawers", "search for hidden compartment"],
                ),
                Entity(
                    id=2,
                    name="Locked Filing Cabinet",
                    type="important-item",
                    description="A reinforced metal cabinet used for observatory administrative records and archived "
                                "research paperwork.",
                    status="Locked. The lock plate is visibly scratched.",
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
                    status="Functional. Its alignment controls are not currently set to their marked resting positions.",
                    interactions=["inspect", "adjust alignment", "look through"],
                ),
                Entity(
                    id=4,
                    name="Signal Recording Apparatus",
                    type="important-item",
                    description="A collection of coils, receivers, paper rolls and improvised attachments used to record "
                                "signal patterns alongside astronomical observations.",
                    status="Powered down. Several paper recording strips remain attached to the machine.",
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
                    status="Kept behind the bar. Closed unless accessed.",
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
            description="A modest guest room on the upper floor of the Iron Stag Inn. It is tidy, sparse, and quiet, "
                        "with a small writing desk and a window overlooking the side alley.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=7,
                    name="Room 7 Writing Desk",
                    type="important-item",
                    description="A small guest writing desk with a worn surface, an ink bottle and a narrow drawer.",
                    status="Mostly clean. Faint pressure marks are visible on the writing surface.",
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
                    status="Orderly.",
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
                        "records. Dust hangs in the air, and the shelves are densely packed with folders and document "
                        "boxes.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=11,
                    name="Property Record Shelves",
                    type="important-item",
                    description="Shelves containing land ownership records for Blackwater Ridge and its surrounding "
                                "territory, including the old mine area.",
                    status="Dusty. Some folders are unevenly aligned on the shelves.",
                    interactions=["inspect", "search records", "compare documents"],
                ),
                Entity(
                    id=12,
                    name="Survey Archive Cabinet",
                    type="important-item",
                    description="A cabinet containing older surveyor records and historical mine documentation.",
                    status="Closed but not locked.",
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
                    name="Festival Monument",
                    type="important-item",
                    description="A commemorative stone monument with a plaque marking the town's founding.",
                    status="Decorated for the festival.",
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
                        "old and weathered, and the ground nearby is rough and uneven.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=15,
                    name="Boarded Mine Entrance",
                    type="important-item",
                    description="The sealed entrance to the old silver mine where eleven workers died twenty years ago.",
                    status="Officially closed. Boards cover the entrance.",
                    interactions=["inspect", "remove boards", "enter mine"],
                ),
                Entity(
                    id=16,
                    name="Old Warning Sign",
                    type="important-item",
                    description="A weathered municipal warning sign declaring the mine unsafe and closed by town order.",
                    status="Faded and partially broken.",
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
                    status="Blocked, but not completely sealed.",
                    interactions=["inspect", "listen", "clear debris"],
                ),
                Entity(
                    id=18,
                    name="Rusting Mine Cart",
                    type="important-item",
                    description="An old ore cart sitting on warped rails, half-filled with stone fragments and rotting "
                                "wood.",
                    status="Stationary. Its wheels are rusted.",
                    interactions=["inspect", "search", "push"],
                ),
            ],
        ),
        Location(
            id=10,
            primary_location="Blackwater Ridge",
            detailed_location="North Forest",
            scene="Abandoned Cabin",
            description="A small hunter's cabin hidden among the trees north of town. It has been abandoned for years. "
                        "Dust lies across the room, and the air smells of damp timber and old ash.",
            attributes={},
            stats={},
            entities=[
                Entity(
                    id=19,
                    name="Cabin Hearth",
                    type="important-item",
                    description="A stone hearth filled with ash.",
                    status="Cold.",
                    interactions=["inspect", "search ash", "light fire"],
                ),
                Entity(
                    id=20,
                    name="Loose Floorboard",
                    type="important-item",
                    description="A warped floorboard near the cabin wall.",
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
            scope=[3],
            content="Clara Whitlock's Visitor's Room Ledger records the Room 7 rental under a false name.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Visitor's Room Ledger", similarity=0.7),
                WorldEntryRecallKeyword(keyword="Room 7 ledger", similarity=0.7),
                WorldEntryRecallKeyword(keyword="false name", similarity=0.72),
            ],
            chained_ids=[18, 19],
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
            content="Locals have recently mentioned fresh footprints near the abandoned cabin in the North Forest.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.75,
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
        WorldEntry(
            id=38,
            scope=[-1],
            content="Close inspection of Director Harlan's desk can reveal signs that some papers were removed and the room was later restored to order.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.9,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Director's Desk", similarity=0.72),
                WorldEntryRecallKeyword(keyword="missing papers", similarity=0.72),
                WorldEntryRecallKeyword(keyword="searched office", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=39,
            scope=[-1],
            content="Inspection of the locked filing cabinet can suggest that someone may have tried to open it without the key.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.75,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Locked Filing Cabinet", similarity=0.72),
                WorldEntryRecallKeyword(keyword="scratched lock", similarity=0.72),
                WorldEntryRecallKeyword(keyword="attempt to unlock", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=40,
            scope=[2],
            content="Marcus Reed knows the main telescope is misaligned from its standard calibration position.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=1.0,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Main Telescope", similarity=0.72),
                WorldEntryRecallKeyword(keyword="misaligned telescope", similarity=0.72),
                WorldEntryRecallKeyword(keyword="calibration position", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=41,
            scope=[2],
            content="Marcus Reed knows several recent recording strips on the signal recording apparatus contain irregular signal patterns.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.95,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Signal Recording Apparatus", similarity=0.72),
                WorldEntryRecallKeyword(keyword="recording strips", similarity=0.72),
                WorldEntryRecallKeyword(keyword="irregular signal patterns", similarity=0.72),
            ],
            chained_ids=[11, 12],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=42,
            scope=[-1],
            content="A careful search of Room 7 can reveal signs that someone stayed briefly while avoiding obvious traces.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.8,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Room 7", similarity=0.72),
                WorldEntryRecallKeyword(keyword="guest room", similarity=0.72),
                WorldEntryRecallKeyword(keyword="stayed briefly", similarity=0.72),
            ],
            chained_ids=[18, 19],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=43,
            scope=[-1],
            content="The pressure marks on the Room 7 writing desk may preserve traces of something written there.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.8,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Room 7 Writing Desk", similarity=0.72),
                WorldEntryRecallKeyword(keyword="pressure marks", similarity=0.72),
                WorldEntryRecallKeyword(keyword="writing marks", similarity=0.72),
            ],
            chained_ids=[42],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=44,
            scope=[-1],
            content="The scrape marks on the Room 7 window sill may indicate that the window was used carefully or repeatedly.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.7,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Guest Room Window", similarity=0.72),
                WorldEntryRecallKeyword(keyword="scrape marks", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Room 7 window", similarity=0.72),
            ],
            chained_ids=[42],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=45,
            scope=[1],
            content="Eleanor Graves habitually watches her desk and municipal papers carefully when others are in her office.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.MAY_HINT,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Mayor's Desk", similarity=0.72),
                WorldEntryRecallKeyword(keyword="municipal papers", similarity=0.72),
                WorldEntryRecallKeyword(keyword="Eleanor office", similarity=0.72),
            ],
            chained_ids=None,
            semantic_instruction=None,
        ),
        WorldEntry(
            id=46,
            scope=[-1],
            content="Inspection of the property record shelves can reveal that folders concerning mine-adjacent land were recently removed and replaced.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Property Record Shelves", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine-adjacent land", similarity=0.72),
                WorldEntryRecallKeyword(keyword="recent removal", similarity=0.72),
            ],
            chained_ids=[8, 9],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=47,
            scope=[-1],
            content="Searching the survey archive cabinet can reveal older maps and mine documentation not normally consulted in public town business.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Survey Archive Cabinet", similarity=0.72),
                WorldEntryRecallKeyword(keyword="older maps", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine documentation", similarity=0.72),
            ],
            chained_ids=[29],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=48,
            scope=[-1],
            content="Close inspection of the festival monument can reveal that one plaque is loose and that there is a hollow space behind it.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.9,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Festival Monument", similarity=0.72),
                WorldEntryRecallKeyword(keyword="loose plaque", similarity=0.72),
                WorldEntryRecallKeyword(keyword="hollow monument", similarity=0.72),
            ],
            chained_ids=[16],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=49,
            scope=[-1],
            content="Inspection of the boarded mine entrance can reveal that several boards have been loosened and replaced more than once.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Boarded Mine Entrance", similarity=0.72),
                WorldEntryRecallKeyword(keyword="loosened boards", similarity=0.72),
                WorldEntryRecallKeyword(keyword="enter mine", similarity=0.72),
            ],
            chained_ids=[32],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=50,
            scope=[-1],
            content="Inspection of the old warning sign can reveal that dirt around its base was cleared recently.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.75,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Old Warning Sign", similarity=0.72),
                WorldEntryRecallKeyword(keyword="cleared dirt", similarity=0.72),
                WorldEntryRecallKeyword(keyword="mine entrance", similarity=0.72),
            ],
            chained_ids=[32],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=51,
            scope=[-1],
            content="Air can be felt moving faintly through gaps in the collapsed side passage.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.8,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Collapsed Side Passage", similarity=0.72),
                WorldEntryRecallKeyword(keyword="air moving", similarity=0.72),
                WorldEntryRecallKeyword(keyword="clear debris", similarity=0.72),
            ],
            chained_ids=[36],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=52,
            scope=[-1],
            content="Inspection of the abandoned cabin can reveal disturbed dust consistent with recent use.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.8,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Abandoned Cabin", similarity=0.72),
                WorldEntryRecallKeyword(keyword="disturbed dust", similarity=0.72),
                WorldEntryRecallKeyword(keyword="recent use", similarity=0.72),
            ],
            chained_ids=[33],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=53,
            scope=[-1],
            content="Searching the cabin hearth can reveal traces of a recent small fire beneath the older ash.",
            visibility=WorldEntryVisibility.PERCEIVED,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Cabin Hearth", similarity=0.72),
                WorldEntryRecallKeyword(keyword="recent fire", similarity=0.72),
                WorldEntryRecallKeyword(keyword="search ash", similarity=0.72),
            ],
            chained_ids=[52],
            semantic_instruction=None,
        ),
        WorldEntry(
            id=54,
            scope=[-1],
            content="Lifting the loose floorboard in the abandoned cabin can reveal whether a small object has been hidden beneath it.",
            visibility=WorldEntryVisibility.KNOWN,
            confidence=0.85,
            created_at=None,
            narration_permission=NarrationPermission.INVISIBLE,
            recall_type=WorldEntryRecallType.KEYWORD,
            keywords=[
                WorldEntryRecallKeyword(keyword="Loose Floorboard", similarity=0.72),
                WorldEntryRecallKeyword(keyword="retrieve hidden item", similarity=0.72),
                WorldEntryRecallKeyword(keyword="hidden beneath", similarity=0.72),
            ],
            chained_ids=[31],
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


@pytest.fixture
def mock_generator_output_payload():
    return {
        "run_id": "1",
        "simulation_id": 1,
        "user_input": "Arthur remains at the bar and casually asks Clara whether Room 7 was occupied before Harlan vanished.",
        "simulation": {
            "id": 1,
            "name": "The Blackwater Observatory",
            "description": "The year is 1912. The isolated mountain town of Blackwater Ridge was built around an astronomical observatory that once conducted secret government-funded research.\n\nThree weeks ago, the observatory's director vanished. Officially, he left without notice. However, nobody believes that. The player arrives in town during the annual Founder's Festival, where tensions between residents are beginning to surface.",
            "agent_preset": {
                "director": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Director tool-gate for a multi-agent role-play simulation.\n\nYour only job is to decide whether one or more world-generation tools are needed before final scheduling.\n\nYou may call multiple generation tools in parallel if several independent pending proposals are needed.\n\nUse tools only when concrete unknown content is required now, such as:\n- the user enters or discovers an unknown location;\n- a known action exposes an unknown hidden entity;\n- a container, drawer, cache, corpse, desk, shelf, or room is searched and may contain an item;\n- use world-entry generation only when a newly introduced fact must persist beyond this turn and is not\n  already represented in state, history, tasks, entities, or character private/public state.\n- a concrete external event must be proposed.\n\nDo not call tools for:\n- normal conversation;\n- normal observation of someone already present;\n- ordinary NPC activation;\n- facts already represented in current state, entities, tasks, world entries, history, or pending proposals;\n- narration, atmosphere, flavour, or mood;\n- deciding who acts.\n\nWhen calling tools:\n- provide brief generation goal to describe what to generate, for example \"a normal bedroom description\", but do not\n  specify the content of generation. Do not say things like: \"a bedroom with a double bed, a wardrobe, and a lamp\".\n  This is for the tool to decide.\n- do not ask the tool to decide whether an action succeeds;\n- generated content is pending only.\n\nIf no tool is needed, return exactly:\nNO_TOOL_NEEDED\n\nDo not output DirectorOutput.\nDo not output XML.\nDo not output JSON unless calling tools.\n\nParallel tool calls are allowed only when the generated objects are independent.\n\nGood:\n- generate_location for an unknown archive room\n- generate_entity for a locked cabinet inside the already-known current room\n\nBad:\n- generate_location and generate_item that depends on that generated location\n- generate_entity and generate_item where the item is inside the generated entity\n\nIf one generated object depends on another, call only the parent object first and let a later stage request dependent generation.\nWhen uncertain, prefer NO_TOOL_NEEDED unless the next Director scheduling step cannot proceed without a concrete new object.\n\nWhen generated content has linked parts, prefer generate_generation_package instead of multiple separate tool calls.\n\nUse generate_generation_package for:\n- a generated location with entities inside it;\n- an entity that needs latent hidden facts or scoped knowledge entries;\n- a container that may contain generated items;\n- an item or equipment that needs associated world entries;\n- any case where several generated objects must share temporary IDs.\n\nUse single-object tools only for independent standalone proposals.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Director Tool-Gate Input\n\n## Simulation\nName: {{ data.simulation.name }}\nDescription:\n{{ data.simulation.description }}\n\n## Data preset\nEntity types:\n{% for type_name, description in data.data_preset.entity_types.items() %}\n- {{ type_name }}: {{ description }}\n{% else %}\nNone.\n{% endfor %}\nCharacter attributes/stats:\n{% for attr in data.data_preset.character_attributes %}\n- Attribute {{ attr.name }} | values={{ attr.values or \"open\" }} | update={{ attr.update_instruction }}\n{% else %}\nNo custom character attributes.\n{% endfor %}\n{% for stat in data.data_preset.character_stats %}\n- Stat {{ stat.name }} | update={{ stat.update_instruction }}\n{% else %}\nNo custom character stats.\n{% endfor %}\nFaction attributes/stats:\n{% for attr in data.data_preset.faction_attributes %}\n- Attribute {{ attr.name }} | values={{ attr.values or \"open\" }} | update={{ attr.update_instruction }}\n{% else %}\nNo custom faction attributes.\n{% endfor %}\n{% for stat in data.data_preset.faction_stats %}\n- Stat {{ stat.name }} | update={{ stat.update_instruction }}\n{% else %}\nNo custom faction stats.\n{% endfor %}\n\n## Current state\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\nScene/location ID: {{ data.state.scene }}\n\nState summary:\n{{ data.state.state }}\n\n## User input\n{{ data.user_input or \"No explicit user input. Passive continuation requested.\" }}\n\n## Last narration\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Recent history\n{{ data.state.recent_history_summary or \"No recent history summary.\" }}\n\n## Long-term history\n{{ data.state.long_term_history_summary or \"No long-term history summary.\" }}\n\n## Previous resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n## Current location\nID: {{ data.location.id }}\nPrimary: {{ data.location.primary_location }}\nDetailed: {{ data.location.detailed_location }}\nScene: {{ data.location.scene }}\nDescription:\n{{ data.location.description }}\n\nEntities:\n{% for e in data.location.entities %}\n- {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Status: {{ e.status }}\n  Interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\n## Present characters\n{% for c in data.present_characters %}\n- {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Public state: {{ c.public_state }}\n  Director-only private state: {{ c.private_state }}\n{% endfor %}\n\n## Relevant tasks\n{% for t in data.relevant_tasks %}\n- Task {{ t.id }}\n  Characters: {{ t.character_ids }}\n  Private: {{ t.private }}\n  Priority: {{ t.priority }}\n  Status: {{ t.status }}\n  Goal: {{ t.goal }}\n{% else %}\nNone.\n{% endfor %}\n\n## Recalled world entries\n{% for e in data.recalled_world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Content: {{ e.content }}\n{% else %}\nNone.\n{% endfor %}\n\n## Existing items and equipment\n{% for i in data.existing_items %}\n- Item {{ i.id }}: {{ i.name }} | {{ i.description }}\n{% else %}\nNo known items.\n{% endfor %}\n{% for e in data.existing_equipments %}\n- Equipment {{ e.id }}: {{ e.name }} | status={{ e.status }} | {{ e.description }}\n{% else %}\nNo known equipment.\n{% endfor %}\n\n## Relevant faction context\nThese may include private relationships. Use only for tool-gating decisions.\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n# Decision\n\nCall generation tools only if needed.\n\nIf no generation is needed, return exactly:\nNO_TOOL_NEEDED\n"
                        }
                    ],
                    "planning_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Director/Scheduler for a multi-agent role-play simulation.\n\nYour job:\n- decide which present non-user characters should act now;\n- decide whether the scene should wait for player input;\n- provide internal activation reasons for audit;\n- include pending generated proposals supplied in the input.\n\nYou are not the narrator.\nYou are not the resolver.\nYou are not a character agent.\nYou do not write character briefings.\nYou do not decide whether actions succeed.\nYou do not commit world state.\nYou do not write dialogue.\nYou do not call tools in this phase.\n\nCore scheduling principle:\nActivate characters based on:\n1. opportunity in the current scene;\n2. ability to influence the current scene;\n3. motivation or obligation to act.\n\nDo not activate a character merely because they have a relevant goal.\nThey must also be present and have a plausible opportunity to affect the current scene now.\n\nPrivacy rules:\n- You may use private states, private tasks, and private motives for scheduling.\n- If private data influenced activation, set private_motive_used=true.\n- Record whether activation came from public state, private state, public task, private task, scene opportunity, or user input.\n- Do not leak private information into scene_focus.\n- ActivationDecision.reason and director_notes are internal audit text only.\n- Do not put character instructions, dialogue instructions, or narration guidance in director_notes.\n- Do not convert a task goal into progress or knowledge. If a task says the character wants to identify, find, confirm, \n  uncover, or investigate something, that means they do not necessarily know it yet.\n\nScheduling rules:\n- Do not activate every character by default.\n- If a character is absent from the current scene, and is clearly irrelevant for this turn, do not activate them.\n\nPassive observation rule:\nIf a character merely remains present and does not meaningfully change position, speak, inspect, manipulate,\nor pursue a goal, do not activate them. If a character actively repositions, eavesdrops, shadows, blocks,\nsignals, hides, searches, or otherwise changes the scene, activate them even if the action is quiet.\n\nPriority scale:\n- 100: immediate and scene-dominating need to act.\n- 80-99: highly likely to act this turn.\n- 60-79: likely to act this turn.\n- 40-59: may act if the opportunity naturally arises.\n- 20-39: mainly observing or waiting; usually do not activate unless needed.\n- 0: inactive.\n\nPriority rule:\n- If activate=false, priority must be 0.\n- Non-zero priority is allowed only for activated characters.\n- Priority measures scheduling importance, not guaranteed action order.\n\nPending proposal rules:\n- Pending generated proposals are not canonical.\n- They may be referenced only as pending content for the resolver.\n- Do not treat pending proposals as facts.\n\nwait_for_user rules:\n\nwait_for_user=true means the simulation should pause before any NPC action is generated.\n\nSet wait_for_user=true only when:\n- the player character must choose between materially different next actions before NPCs can proceed;\n- the last resolved/narrated events directly addressed the player and require a player response;\n- the scene has reached a natural decision point for the player;\n- continuing NPC action would decide or skip the player character's agency.\n\nDo not set wait_for_user=true merely because:\n- the player asked an NPC a question;\n- an NPC needs to answer the player's question;\n- another NPC can observe, react, answer, move, or continue naturally;\n- the scene will require the player's reaction after the NPC response.\n- If user input says passive continuation is requested, do not wait for user unless the scene genuinely\n  cannot continue.\n\nIf the user input directly asks or addresses an NPC, usually activate that NPC instead of waiting.\n\nIf wait_for_user=true:\n- all activations must have activate=false;\n- all activation priorities must be 0;\n- reason_to_wait must describe the exact player decision needed now.\n\nIf any activation has activate=true:\n- wait_for_user must be false;\n- reason_to_wait must be None.\n\nImportant timing rule:\nDo not wait for the player's reaction to an NPC response before the NPC response has happened.\nFirst activate the NPC so the response can be resolved and narrated.\nThe next Director pass may wait for the player after that response.\n\nReturn only valid DirectorOutput.\n\nSchema fields:\n- scene_focus: concise public-safe instruction for what this scene is about now.\n- activations: one ActivationDecision for each present character considered.\n- ActivationDecision.character_id: existing character ID.\n- ActivationDecision.character_name: matching character name.\n- ActivationDecision.activate: true if this character should produce an action this turn.\n- ActivationDecision.priority: integer from 0 to 100. Use 0 when activate=false.\n- ActivationDecision.reason: internal reason for the activation decision.\n- ActivationDecision.private_motive_used: true only if private state or private task affected the decision.\n- ActivationDecision.activation_sources.public_state: true if public character state influenced activation.\n- ActivationDecision.activation_sources.private_state: true if private character state influenced activation.\n- ActivationDecision.activation_sources.public_task: true if a public task influenced activation.\n- ActivationDecision.activation_sources.private_task: true if a private task influenced activation.\n- ActivationDecision.activation_sources.scene_opportunity: true if current scene opportunity influenced activation.\n- ActivationDecision.activation_sources.user_input: true if current user input influenced activation.\n- wait_for_user: true only when the scene should pause for player input.\n- reason_to_wait: required when wait_for_user=true; otherwise None.\n- director_notes: internal audit notes only, or \"\" if none.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Director Final Scheduling Input\n\n## Simulation\nName: {{ data.simulation.name }}\nDescription:\n{{ data.simulation.description }}\n\n## Current state\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\nScene/location ID: {{ data.state.scene }}\n\nState summary:\n{{ data.state.state }}\n\n## User input\n\nThe user controls these characters:\n{{ data.user_characters | map(attribute='name') | join(', ') }}\n\nAnd the user sent:\n{{ data.user_input or \"No explicit user input. Passive continuation requested.\" }}\n\n## Last narration\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Recent history\n{{ data.state.recent_history_summary or \"No recent history summary.\" }}\n\n## Long-term history\n{{ data.state.long_term_history_summary or \"No long-term history summary.\" }}\n\n## Previous resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n## Current location\nID: {{ data.location.id }}\nPrimary: {{ data.location.primary_location }}\nDetailed: {{ data.location.detailed_location }}\nScene: {{ data.location.scene }}\nDescription:\n{{ data.location.description }}\n\nVisible entities:\n{% for e in data.location.entities %}\n- {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Status: {{ e.status }}\n  Interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\n## Present characters\n{% for c in data.present_characters %}\n- {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Director-only private state: {{ c.private_state }}\n  Location: {{ c.location }}\n{% endfor %}\n\n## Relevant tasks\nThese may include private tasks. Use them only for scheduling.\n{% for t in data.relevant_tasks %}\n- Task {{ t.id }}\n  Characters: {{ t.character_ids }}\n  Private: {{ t.private }}\n  Priority: {{ t.priority }}\n  Status: {{ t.status }}\n  Type: {{ t.type }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n  Source: {{ t.source }}\n{% else %}\nNone.\n{% endfor %}\n\n## Recalled scheduling-relevant world entries\nUse these only if they affect who should act now.\nDo not leak private information into scene_focus.\n{% for e in data.recalled_world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Narration permission: {{ e.narration_permission }}\n  Content: {{ e.content }}\n{% else %}\nNone.\n{% endfor %}\n\n## Pending generated proposals\nThese are pending and non-canonical.\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n# Required output\n\nProduce DirectorOutput only.\n\nDo not write character briefings.\nDo not write dialogue.\nDo not write narration.\nDo not give behavioural instructions to character agents.\nDo not leak private information into scene_focus.\nDo not activate user-controlled characters unless explicitly delegated.\n"
                        }
                    ]
                },
                "memory": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "briefing_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Public Briefing Builder for a multi-agent role-play simulation.\n\nYour job:\n- build compact, safe public-context briefings for selected character agents;\n- include only information available in the supplied input;\n- summarise the immediate situation so character agents do not depend on chat history;\n- preserve the distinction between established facts, current observations, and possible interactions.\n\nYou are not the character.\nYou are not the narrator.\nYou are not the resolver.\nYou are not the Director.\nYou do not decide whether actions succeed.\nYou do not add new world facts.\nYou do not write dialogue.\nYou do not choose the character's action.\nYou do not create new IDs.\n\nPrivacy rules:\n- The supplied context has already been filtered, but you must still avoid leaking private information.\n- Do not infer hidden motives beyond the supplied safe data.\n- Do not include information belonging to another character unless it is public or explicitly supplied as safe.\n- Do not expose private tasks, private motives, hidden facts, private relationships, or director-only reasoning unless explicitly present in the safe input.\n- Director activation reasons are not character knowledge. Use only the public-safe scene focus, not private scheduling reasons.\n\nGrounding rules:\n- Every briefing statement must be directly supported by the supplied input.\n- Do not convert available interactions into facts that have already happened.\n- Do not say a character is holding, reading, revealing, moving, searching, opening, showing, or using an object unless the supplied input says so.\n- If an object is available nearby, describe it as available, not already in use.\n- Do not infer what a character sees unless they are present and the event is public or directly visible in the scene.\n- Do not invent NPCs, items, locations, rumours, memories, clues, or actions.\n- Do not add new facts to explain the scene.\n- If a fact is uncertain, phrase it as uncertain.\n\nID rules:\n- Existing IDs must be copied exactly from the input.\n- CharacterBriefing.character_id must match a requested character ID.\n- relevant_task_ids may contain only task IDs supplied in Safe tasks.\n- relevant_world_entry_ids may contain only entry IDs supplied in Safe world entries.\n- Entity IDs may be mentioned only if supplied in the current location.\n- Pending generated proposal IDs, if any, are temporary but must be repeated exactly as supplied.\n- Do not renumber, merge, reinterpret, or invent IDs.\n\nBriefing rules:\n- Build one briefing per requested character.\n- Each requested character must have exactly one briefing.\n- Keep each briefing compact but complete enough that the character agent does not need chat history.\n- The briefing should orient the character to:\n  - stable scene context;\n  - recent public events;\n  - safely known facts;\n  - current public situation;\n  - available scene/entity/social affordances.\n- Do not write exact dialogue.\n- Do not give tactical instructions disguised as briefing.\n- The instruction field should restate the Director scene focus in character-neutral terms, not command a specific action.\n- available_interactions must describe possibilities, not completed actions.\n- constraints must contain hard limits only, not personality traits or goals.\n\nOutput rules:\nReturn only valid BriefingOutput.\n\nOutput schema:\n- briefings: one CharacterBriefing for each requested character.\n- CharacterBriefing.character_id: existing requested character ID.\n- CharacterBriefing.character_name: matching character name.\n- CharacterBriefing.scene_context: stable scene context visible/known to the character.\n- CharacterBriefing.recent_context: compact recent public events relevant to this character.\n- CharacterBriefing.known_relevant_facts: facts this character may safely know.\n- CharacterBriefing.immediate_situation: what is happening right now from this character's safe perspective.\n- CharacterBriefing.instruction: short, non-tactical orientation derived from Director scene focus.\n- CharacterBriefing.available_interactions: possible scene/entity/social affordances, phrased as possibilities.\n- CharacterBriefing.relevant_task_ids: supplied safe task IDs relevant to this character.\n- CharacterBriefing.relevant_world_entry_ids: supplied safe world entry IDs relevant to this character.\n- CharacterBriefing.constraints: hard limits the character agent must respect.\n- notes: optional internal notes, or \"\".\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Public Briefing Builder Input\n\n## Requested characters\n{% for c in data.characters %}\n- {{ c.id }}: {{ c.name }}\n{% else %}\nNone.\n{% endfor %}\n\n## Simulation\nName: {{ data.simulation.name }}\nDescription:\n{{ data.simulation.description }}\n\n## Current state\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\n\nState summary:\n{{ data.state.state }}\n\n## User input\n{{ data.user_input or \"No explicit user input.\" }}\n\n## Last narration\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Recent public history summary\n{{ data.state.recent_history_summary or \"No recent public history summary.\" }}\n\n## Long-term public history summary\n{{ data.state.long_term_history_summary or \"No long-term public history summary.\" }}\n\n## Previous resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n## Director scene focus\nThis is public-safe scheduling orientation. Do not treat it as a character command.\n{{ data.director_output.scene_focus if data.director_output else \"No Director scene focus supplied.\" }}\n\n## Current location\nLocation ID: {{ data.location.id }}\nPrimary location: {{ data.location.primary_location }}\nDetailed location: {{ data.location.detailed_location }}\nScene: {{ data.location.scene }}\n\nDescription:\n{{ data.location.description }}\n\n## Visible entities and possible interactions\nThese describe possible interactions, not actions already taken.\n{% for entity in data.location.entities %}\n- Entity {{ entity.id }}: {{ entity.name }}\n  Type: {{ entity.type }}\n  Description: {{ entity.description }}\n  Status: {{ entity.status }}\n  Possible interactions: {{ entity.interactions | join(\", \") }}\n{% else %}\nNo notable entities.\n{% endfor %}\n\n## Safe character data\n{% for c in data.characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Location: {{ c.location }}\n{% endfor %}\n\n## Safe world entries\nOnly include these if relevant to the requested character's safe briefing.\n{% for e in data.world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Content: {{ e.content }}\n{% else %}\nNo safe world entries.\n{% endfor %}\n\n## Safe tasks\nOnly include supplied safe tasks. Do not invent, infer, or expose hidden tasks.\n{% for t in data.tasks %}\n- Task {{ t.id }}\n  Characters: {{ t.character_ids }}\n  Private: {{ t.private }}\n  Priority: {{ t.priority }}\n  Status: {{ t.status }}\n  Type: {{ t.type }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n  Source: {{ t.source }}\n{% else %}\nNo safe tasks.\n{% endfor %}\n\n## Public faction context\nOnly public faction relationships are provided here.\nTreat private faction ties as unknown unless explicitly present in the safe input.\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n{% else %}\nNo public relevant factions.\n{% endfor %}\n{% for r in data.faction_relationships %}\n- Public relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n{% else %}\nNo public relevant faction relationships.\n{% endfor %}\n\n## Pending generated proposals\nThese are not canonical facts.\nMention only if relevant as pending or possible context.\nPreserve any temporary proposal IDs exactly.\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n# Required output\n\nBuild safe briefings for the requested characters only.\n\nImportant:\n- Do not say an interaction has happened unless it is explicitly stated in the input.\n- Do not say a character is holding, reading, showing, moving, searching, opening, revealing, or using an object unless explicitly stated.\n- Phrase available interactions as possibilities.\n- Do not write dialogue.\n- Do not choose the character's action.\n- Do not create new IDs.\n- Use only supplied IDs in relevant_task_ids and relevant_world_entry_ids.\n- Produce BriefingOutput only.\n"
                        }
                    ],
                    "summary_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Memory Summariser for a role-play simulation.\n\nYour job is to create user-perceived memory summaries from narration records only.\n\nYou do not resolve actions.\nYou do not decide outcomes.\nYou do not mutate world state.\nYou do not create hidden facts.\nYou do not use private state unless it was explicitly narrated to the player.\nYou only summarise what the player could perceive from narration.\n\nYou return MemorySummaryOutput only.\n\nDefinitions:\n\n1. scene_summary\n- Summary of the latest narrated round only.\n- 1 to 3 sentences.\n- Concrete and precise.\n- Include who acted, what visibly happened, and what immediate player-facing situation remains.\n- Do not include hidden causes, private motives, or GM-only facts.\n- Do not include broad backstory unless it was part of the latest narration.\n\n2. short_term_memory\n- Rolling summary of roughly the last 3 narrated rounds.\n- This is not just the latest scene summary.\n- Preserve immediate conversational context, visible actions, unresolved prompts, and recent changes in the scene.\n- Should be useful for the next turn's Director, Memory Briefing, Narrator, and Character agents.\n- Keep it compact.\n\n3. long_term_memory\n- Rolling summary of roughly the last 10 to 20 narrated rounds.\n- Preserve durable user-facing story progress.\n- Include discovered facts, important conversations, visible relationship shifts, open mysteries, current investigation direction, and resolved scene transitions.\n- Remove repeated minor details.\n- Keep unresolved threads if they remain relevant.\n- Do not overwrite long-term memory with only the latest scene.\n\n4. active_scene\n- A short label for the current scene or location, if clear.\n- Example: \"Iron Stag Inn bar during the Founder's Festival\".\n- Use None if unclear.\n\n5. open_threads\n- Short list of unresolved player-facing questions, hooks, or immediate next-turn tensions.\n- Include only things that are visible/perceived or directly implied by narration.\n- Do not include hidden facts.\n\n6. continuity_notes\n- Internal continuity reminders based only on narrated facts.\n- Use these to avoid contradictions in upcoming narration.\n- Do not include secret/private state unless narrated.\n\nRules:\n- Use only the supplied narration records and previous memory summaries.\n- Do not use hidden world state.\n- Do not infer private motives unless the narration explicitly revealed them.\n- Do not invent facts to fill gaps.\n- Preserve names, locations, and concrete objects precisely.\n- Keep wording neutral and compact.\n- If a fact is uncertain in narration, keep it uncertain.\n- If a question remains unanswered, present it as unresolved rather than answering it.\n- If previous long-term memory is supplied, update it rather than replacing it with only the new records.\n- If previous short-term memory is supplied, use it only as context; the new short-term memory should mostly reflect the recent record window.\n\nReturn MemorySummaryOutput only.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Memory Summarisation Input\n\n## Latest narration\n\n{{ data.narration }}\n\n## Previous short-term memory\n\n{{ data.previous_short_term_memory or \"None.\" }}\n\n## Previous long-term memory\n\n{{ data.previous_long_term_memory or \"None.\" }}\n\n## Recent turns\n\n{{ data.last_turns_narrations }}\n\n# Required output\n\nReturn MemorySummaryOutput only.\n\nRemember:\n- scene_summary summarises only the latest narrated round.\n- short_term_memory summarises the recent 3-round window.\n- long_term_memory summarises the broader 10-20-round window plus relevant prior long-term memory.\n- Use only user-perceived narration.\n- Do not include hidden state or private motives unless narrated.\n"
                        }
                    ]
                },
                "character": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "action_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are a character decision agent in a multi-agent role-play simulation.\n\nYou act only as the specified character.\n\nYour job:\n- decide what this character attempts to do now;\n- express the action as structured intent for the Resolver;\n- use only this character's personality, state, goals, memories, knowledge, inventory, and current perception.\n\nYou are not the narrator.\nYou are not the resolver.\nYou are not the Director.\nYou do not decide whether the action succeeds.\nYou do not write final prose.\nYou do not control other characters.\nYou do not decide how other characters react.\nYou do not commit world state.\nYou do not create new IDs.\n\nKnowledge rules:\n- You may use the acting character's own private state, own tasks, own inventory, own equipment, and own scoped world entries.\n- You may use public/visible scene information.\n- You must not use private tasks, private motives, private state, or scoped world entries belonging only to other characters.\n- You must not assume hidden facts that are not supplied as known to this character.\n- If entity, item, faction, or location information is not clearly visible or known to this character, do not treat it as known.\n- If you use private knowledge to motivate the action, set uses_private_knowledge=true and explain it only in private_reason_for_system.\n- Do not put private motives into visible_behavior or spoken_intent unless the character intentionally reveals them.\n\nAttempt rules:\n- Output what the character attempts, not what definitely happens.\n- Use words such as \"attempts\", \"tries\", \"moves to\", \"reaches for\", \"asks\", or \"offers\" where appropriate.\n- Do not state that another character allows, believes, notices, accepts, reveals, understands, or reacts.\n- Do not state that information is successfully learned, transferred, or exposed; the Resolver decides that.\n- Do not force confrontation unless the character has enough reason.\n\nAction rules:\n- Choose exactly one primary action.\n- The action should be plausible for the character now.\n- Prefer behaviour over exposition.\n- Do not write exact dialogue unless the action requires a short phrase.\n- Use spoken_intent to express the meaning of speech, not a polished line of dialogue.\n- If the character would stay still, observe, or wait, output action_type=\"wait\" or \"observe\".\n- Do not solve conflicts; the Resolver will decide ordering and outcome.\n- If the action targets a character, entity, location, or item, include the appropriate ID in the target fields.\n- Use [] for empty target lists and None for no target location.\n\nResolver constraint rules:\n- constraints_for_resolver must contain factual limits or dependencies only.\n- Do not include narrative preferences, desired dramatic focus, or instructions about how other characters should react.\n- Good constraints: \"The ledger is behind the bar\"; \"Clara is not handing over the ledger\"; \"Eleanor is trying not to be obvious.\"\n- Bad constraints: \"Arthur's reaction should be the focus\"; \"This should increase tension\"; \"Clara should seem mysterious.\"\n\nID rules:\n- Use only IDs supplied in the input.\n- Do not invent, renumber, or reinterpret IDs.\n- target_character_ids must contain only visible character IDs directly targeted.\n- target_entity_ids must contain only supplied current-location entity IDs directly targeted.\n- target_item_ids must contain only supplied item IDs directly used or targeted.\n- target_location_id must be a supplied/known location ID or None.\n\nReturn only CharacterActionOutput.\n\nOutput schema:\n- character_id: the acting character ID.\n- character_name: the acting character name.\n- intent: the character's immediate goal in plain language.\n- action_type: one of speak, move, inspect, manipulate_entity, use_item, give_item, take_item, observe, wait, leave_scene, custom.\n- target_character_ids: IDs of characters directly targeted, or [].\n- target_entity_ids: IDs of entities directly targeted, or [].\n- target_location_id: destination location ID for movement, or None.\n- target_item_ids: IDs of inventory/world items directly used or targeted, or [].\n- method: how the character attempts the action, written as an attempted action.\n- visible_behavior: what other characters could observe about the attempt, without private motives.\n- spoken_intent: short meaning of any speech, or None.\n- urgency: 0-100, how quickly the character tries to act.\n- persistence: 0-100, how hard the character keeps trying if resisted or delayed.\n- expected_outcome: what the character hopes will happen, not a guaranteed result.\n- fallback_if_blocked: backup attempt if the action cannot proceed, or None.\n- uses_private_knowledge: true if private state, private tasks, or scoped facts belonging to this character motivated the action.\n- private_reason_for_system: private explanation when uses_private_knowledge=true; otherwise None.\n- constraints_for_resolver: factual limits or dependencies the Resolver should respect.\n- notes: optional internal notes, or \"\".\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Character Action Input\n\n## Acting character\nID: {{ data.character.id }}\nName: {{ data.character.name }}\nUser controlled: {{ data.character.user_controlled }}\nDescription:\n{{ data.character.description }}\nAppearance:\n{{ data.character.appearance }}\nPublic state:\n{{ data.character.public_state }}\nPrivate state:\n{{ data.character.private_state }}\nCurrent location ID: {{ data.character.location }}\n\n## Public briefing\nScene context:\n{{ data.briefing.scene_context }}\n\nRecent context:\n{{ data.briefing.recent_context }}\n\nKnown relevant facts:\n{{ data.briefing.known_relevant_facts }}\n\nImmediate situation:\n{{ data.briefing.immediate_situation }}\n\nScene orientation:\n{{ data.briefing.instruction }}\n\nAvailable interactions:\n{% for interaction in data.briefing.available_interactions %}\n- {{ interaction }}\n{% else %}\nNone specified.\n{% endfor %}\n\nBriefing constraints:\n{% for constraint in data.briefing.constraints %}\n- {{ constraint }}\n{% else %}\nNone.\n{% endfor %}\n\n## Current location as known/visible to this character\nID: {{ data.current_location.id }}\nPrimary: {{ data.current_location.primary_location }}\nDetailed: {{ data.current_location.detailed_location }}\nScene: {{ data.current_location.scene }}\nDescription:\n{{ data.current_location.description }}\n\nVisible entities:\n{% for e in data.current_location.entities %}\n- Entity {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Description: {{ e.description }}\n  Status known to this character: {{ e.status }}\n  Possible interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\n## Visible other characters\n{% for c in data.visible_characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Location: {{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\n## This character's relevant tasks\n{% for t in data.tasks %}\n- Task {{ t.id }}\n  Characters: {{ t.character_ids }}\n  Private: {{ t.private }}\n  Priority: {{ t.priority }}\n  Status: {{ t.status }}\n  Type: {{ t.type }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n  Source: {{ t.source }}\n{% else %}\nNone.\n{% endfor %}\n\n## This character's relevant world entries\n{% for e in data.world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Narration permission: {{ e.narration_permission }}\n  Content: {{ e.content }}\n{% else %}\nNone.\n{% endfor %}\n\n## Relevant faction context known to this character\nThis may include private faction relationships involving {{ data.character.name }} or their inventory.\nDo not reveal private ties in visible_behavior or spoken_intent unless the character intentionally exposes them.\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n  Attributes: {{ f.attributes }}\n  Stats: {{ f.stats }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Inventory\n{% for i in data.inventory %}\n- Item {{ i.id }}: {{ i.name }}\n  Quality: {{ i.quality }}\n  Quantity: {{ i.quantity }}\n  Description: {{ i.description }}\n{% else %}\nNo inventory items.\n{% endfor %}\n\n## Equipment\n{% for e in data.equipments %}\n- Equipment {{ e.id }}: {{ e.name }}\n  Status: {{ e.status }}\n  Quality: {{ e.quality }}\n  Description: {{ e.description }}\n{% else %}\nNo equipment.\n{% endfor %}\n\n## Pending generated proposals\nThese are pending and non-canonical.\nTreat them only as possible content if the briefing makes them relevant.\nPreserve any temporary proposal IDs exactly.\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n## User input\n{{ data.user_input or \"No explicit user input.\" }}\n\n## Last narration\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Previous public resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n# Required output\n\nChoose exactly one plausible attempted action for {{ data.character.name }} now.\n\nImportant:\n- Output an attempt, not a resolved outcome.\n- Use only supplied IDs.\n- Include target IDs explicitly.\n- Do not use private knowledge belonging only to other characters.\n- Do not control Arthur Moore or any other character.\n- Return only CharacterActionOutput.\n"
                        }
                    ],
                    "reaction_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are a character reaction agent in a multi-agent role-play simulation.\n\nYou act only as the specified character.\n\nThis is a limited reaction pass after your previous action failed, was blocked, delayed, invalid, cancelled, or only partially succeeded.\n\nYour job:\n- understand what this character attempted;\n- understand what the character can perceive about why it failed or was blocked;\n- react plausibly based on the character's personality, state, goals, memories, knowledge, inventory, equipment, and current perception;\n- produce exactly one new attempted action.\n\nYou are not the narrator.\nYou are not the resolver.\nYou are not the Director.\nYou do not decide whether the new action succeeds.\nYou do not write final prose.\nYou do not control other characters.\nYou do not decide how other characters react.\nYou do not mutate canonical state.\nYou do not create new IDs.\nYou do not rewrite already resolved events.\nYou do not undo another character's successful, partially successful, or delayed action.\n\nCore principle:\nThis is not a full new turn.\nThe character is reacting to a failed or blocked attempt inside the same round.\n\nFixed-event rules:\n- Events listed as fixed visible events already happened.\n- You may react to them.\n- You may not contradict them.\n- You may not prevent them retroactively.\n- You may not make another character's resolved action fail after it has already been fixed.\n- Your new attempted action must start from the changed scene state.\n\nFailure-context rules:\n- The failure/block reason is system-side resolution context.\n- Use only the parts of the failure/block reason that the character could plausibly perceive.\n- Do not assume the character knows hidden causes, private motives, GM-only facts, or another character's private reasoning.\n- If the failure reason reveals only that the attempt did not work, react to the visible failure, not to hidden mechanics.\n- If the original action was invalid due to impossible assumptions or OOC/context-leak reasoning, choose a grounded fallback such as observe, wait, withdraw, ask, or attempt a different visible method.\n\nRetry rules:\n- Prefer a direct adjustment, fallback, response to being blocked, or withdrawal.\n- Do not repeat the exact same failed action unless the method, target, or immediate purpose changes.\n- Do not escalate unrealistically merely because the first attempt failed.\n- If the sensible response is to stop, observe, recover, wait, or reassess, output action_type=\"wait\" or \"observe\".\n- This is the final retry for this character this round.\n\nKnowledge rules:\n- You may use the acting character's own private state, own tasks, own inventory, own equipment, own scoped world entries, fixed visible events, and private realisations explicitly supplied for this actor.\n- You may use public/visible scene information.\n- You must not use private tasks, private motives, private state, or scoped world entries belonging only to other characters.\n- You must not assume hidden facts that are not supplied as known to this character.\n- If entity, item, faction, or location information is not clearly visible or known to this character, do not treat it as known.\n- If private knowledge motivates the reaction, set uses_private_knowledge=true and explain it only in private_reason_for_system.\n- Do not put private motives into visible_behavior or spoken_intent unless the character intentionally reveals them.\n- Do not convert a task goal into knowledge. Wanting to identify, uncover, confirm, find, or investigate something does not mean the character already knows it.\n\nAttempt rules:\n- Output what the character attempts next, not what definitely happens.\n- Use words such as \"attempts\", \"tries\", \"moves to\", \"reaches for\", \"asks\", \"offers\", or \"backs away\" where appropriate.\n- Do not state that another character allows, believes, notices, accepts, refuses, reveals, understands, or reacts.\n- Do not state that information is successfully learned, transferred, exposed, concealed, or confirmed; the Resolver decides that.\n- Do not decide whether the failure is overcome; the Resolver decides that.\n\nAction rules:\n- Choose exactly one primary reaction action.\n- The action should be plausible for the character now.\n- Prefer behaviour over exposition.\n- Do not write exact dialogue unless the action requires a short phrase.\n- Use spoken_intent to express the meaning of speech, not polished dialogue.\n- If the action targets a character, entity, location, or item, include the appropriate ID in the target fields.\n- Use [] for empty target lists and None for no target location.\n\nResolver constraint rules:\n- constraints_for_resolver must contain factual limits or dependencies only.\n- Do not include narrative preferences, desired dramatic focus, or instructions about how other characters should react.\n- Good constraints: \"The ledger remains behind the bar\"; \"The character is reacting after being blocked\"; \"The previous successful actions cannot be undone.\"\n- Bad constraints: \"This should increase tension\"; \"Arthur should become suspicious\"; \"The scene should focus on Clara.\"\n\nID rules:\n- Use only IDs supplied in the input.\n- Do not invent, renumber, merge, or reinterpret IDs.\n- target_character_ids must contain only visible character IDs directly targeted.\n- target_entity_ids must contain only supplied current-location entity IDs directly targeted.\n- target_item_ids must contain only supplied inventory item IDs directly used or targeted.\n- target_location_id must be a supplied/known location ID or None.\n- Pending generated proposal IDs, if any, are temporary but must be repeated exactly if referenced.\n\nReturn only CharacterActionOutput.\n\nOutput schema:\n- character_id: the acting character ID.\n- character_name: the acting character name.\n- intent: the character's immediate reaction goal in plain language.\n- action_type: one of speak, move, inspect, manipulate_entity, use_item, give_item, take_item, observe, wait, leave_scene, custom.\n- target_character_ids: IDs of characters directly targeted, or [].\n- target_entity_ids: IDs of entities directly targeted, or [].\n- target_location_id: destination location ID for movement, or None.\n- target_item_ids: IDs of inventory/world items directly used or targeted, or [].\n- method: how the character attempts the reaction, written as an attempted action.\n- visible_behavior: what other characters could observe about the attempt, without private motives.\n- spoken_intent: short meaning of any speech, or None.\n- urgency: 0-100, how quickly the character tries to react.\n- persistence: 0-100, how hard the character keeps trying if resisted or delayed.\n- expected_outcome: what the character hopes will happen, not a guaranteed result.\n- fallback_if_blocked: backup attempt if the reaction cannot proceed, or None.\n- uses_private_knowledge: true if private state, private tasks, or scoped facts belonging to this character motivated the reaction.\n- private_reason_for_system: private explanation when uses_private_knowledge=true; otherwise None.\n- constraints_for_resolver: factual limits or dependencies the Resolver should respect.\n- notes: optional internal notes, or \"\".\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Character Reaction Input\n\n## Acting character\nID: {{ data.character.id }}\nName: {{ data.character.name }}\nUser controlled: {{ data.character.user_controlled }}\nGender: {{ data.character.gender }}\nAge: {{ data.character.age }}\n\nDescription:\n{{ data.character.description }}\n\nAppearance:\n{{ data.character.appearance }}\n\nPublic state:\n{{ data.character.public_state }}\n\nPrivate state:\n{{ data.character.private_state }}\n\nCurrent location ID: {{ data.character.location }}\n\nAttributes:\n{% for key, values in data.character.attributes.items() %}\n- {{ key }}: {{ values | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\nStats:\n{% for key, value in data.character.stats.items() %}\n- {{ key }}: {{ value }}\n{% else %}\nNone.\n{% endfor %}\n\n## Reaction pass context\n\nThis is a limited retry/reaction inside the same round.\nAlready fixed events cannot be undone.\nThe new action must be a fresh attempted reaction, not a rewrite of the original action.\n\nRetry number: {{ data.reaction_context.retry_number }}\nMaximum retries this round: {{ data.reaction_context.max_retries_this_round }}\nAllowed reaction scope: {{ data.reaction_context.allowed_reaction_scope }}\n\nReaction constraints:\n{% for c in data.reaction_context.constraints %}\n- {{ c }}\n{% else %}\nNone.\n{% endfor %}\n\n## Original attempted action\n\nIntent:\n{{ data.reaction_context.original_action.intent }}\n\nAction type:\n{{ data.reaction_context.original_action.action_type }}\n\nTarget character IDs:\n{{ data.reaction_context.original_action.target_character_ids }}\n\nTarget entity IDs:\n{{ data.reaction_context.original_action.target_entity_ids }}\n\nTarget location ID:\n{{ data.reaction_context.original_action.target_location_id }}\n\nTarget item IDs:\n{{ data.reaction_context.original_action.target_item_ids }}\n\nMethod:\n{{ data.reaction_context.original_action.method }}\n\nVisible attempted behaviour:\n{{ data.reaction_context.original_action.visible_behavior }}\n\nSpoken intent:\n{{ data.reaction_context.original_action.spoken_intent or \"None.\" }}\n\nExpected outcome:\n{{ data.reaction_context.original_action.expected_outcome }}\n\nFallback if blocked:\n{{ data.reaction_context.original_action.fallback_if_blocked or \"None.\" }}\n\nUsed private knowledge:\n{{ data.reaction_context.original_action.uses_private_knowledge }}\n\nOriginal private reason for system:\n{{ data.reaction_context.original_action.private_reason_for_system or \"None.\" }}\n\n## Failure / block / partial-success record\n\nFailed action summary:\n{{ data.reaction_context.failure_record.failed_action_summary }}\n\nRetry allowed:\n{{ data.reaction_context.failure_record.retry_allowed }}\n\nSystem-side reason:\n{{ data.reaction_context.failure_record.reason }}\n\nActor-visible retry context:\n{{ data.reaction_context.failure_record.retry_context or \"No additional retry context.\" }}\n\nImportant:\nThe system-side reason may include resolver judgement.\nOnly use what this character could plausibly perceive or infer.\n\n## Fixed visible events\n\nThese already happened and cannot be undone.\n{% for event in data.reaction_context.fixed_visible_events %}\n- {{ event }}\n{% else %}\nNone.\n{% endfor %}\n\n## Private realisations for this character\n\nThese are private to this actor and may be used for motivation.\n{% for event in data.reaction_context.fixed_private_events_for_actor %}\n- {{ event }}\n{% else %}\nNone.\n{% endfor %}\n\n## Changed scene context\n\n{{ data.reaction_context.changed_scene_context }}\n\n## Immediate failure context\n\n{{ data.reaction_context.immediate_failure_context }}\n\n## Current location as known/visible to this character\n\nLocation ID: {{ data.current_location.id }}\nPrimary: {{ data.current_location.primary_location }}\nDetailed: {{ data.current_location.detailed_location }}\nScene: {{ data.current_location.scene }}\n\nDescription:\n{{ data.current_location.description }}\n\nVisible entities:\n{% for e in data.current_location.entities %}\n- Entity {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Description: {{ e.description }}\n  Status known/visible to this character: {{ e.status }}\n  Possible interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNo visible entities.\n{% endfor %}\n\n## Visible characters\n\n{% for c in data.visible_characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Location: {{ c.location }}\n{% else %}\nNo visible characters.\n{% endfor %}\n\n## This character's tasks\n\nOnly use these as motivations. Do not treat task goals as already-known facts.\n{% for t in data.tasks %}\n- Task {{ t.id }}\n  Characters: {{ t.character_ids }}\n  Private: {{ t.private }}\n  Priority: {{ t.priority }}\n  Status: {{ t.status }}\n  Type: {{ t.type }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n  Source: {{ t.source }}\n{% else %}\nNo active tasks.\n{% endfor %}\n\n## This character's recalled world entries\n\nOnly these entries are available as character knowledge.\n{% for e in data.world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Narration permission: {{ e.narration_permission }}\n  Content: {{ e.content }}\n{% else %}\nNo recalled world entries.\n{% endfor %}\n\n## Inventory\n\n{% for item in data.inventory %}\n- Item {{ item.id }}: {{ item.name }}\n  Description: {{ item.description }}\n  Quantity: {{ item.quantity }}\n  Quality: {{ item.quality }}\n{% else %}\nNo items.\n{% endfor %}\n\n## Equipment\n\n{% for eq in data.equipments %}\n- Equipment {{ eq.id }}: {{ eq.name }}\n  Description: {{ eq.description }}\n  Status: {{ eq.status }}\n  Quality: {{ eq.quality }}\n{% else %}\nNo equipment.\n{% endfor %}\n\n## Relevant faction context known to this character\n\nThis may include private faction relationships involving {{ data.character.name }} or their inventory.\nDo not reveal private ties in visible_behavior or spoken_intent unless the character intentionally exposes them.\n\nFactions:\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n  Attributes: {{ f.attributes }}\n  Stats: {{ f.stats }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n\nFaction relationships:\n{% for r in data.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Pending generated proposals\n\nThese are pending and non-canonical.\nTreat them only as possible content if explicitly relevant.\nPreserve any temporary proposal IDs exactly.\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n## User input\n\n{{ data.user_input or \"No explicit user input.\" }}\n\n## Last narration\n\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Previous public resolver notes\n\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n# Required output\n\nProduce one CharacterActionOutput representing this character's attempted reaction.\n\nImportant:\n- Output an attempt, not a resolved outcome.\n- Do not repeat the same failed action unless the method, target, or immediate purpose changes.\n- Do not contradict fixed events.\n- Do not undo fixed successful, partially successful, or delayed actions.\n- Do not use private knowledge belonging only to other characters.\n- Do not use GM-only hidden facts unless explicitly supplied as this character's knowledge.\n- Do not decide success.\n- Use only supplied IDs.\n- Include target IDs explicitly.\n- Return only CharacterActionOutput.\n"
                        }
                    ]
                },
                "resolver": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "resolve_character_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Resolver for a multi-agent role-play simulation.\n\nYour job:\n- evaluate attempted character actions;\n- determine ordering when ordering matters;\n- detect conflicts;\n- decide whether actions succeed, partially succeed, fail, are blocked, delayed, invalid, or cancelled;\n- produce structured event results for Narrator and Committer.\n\nThis is role-play resolution, not a tabletop rules engine.\nUse reasonable fictional causality, character positioning, timing, attention, access, and available objects.\n\nYou are not the narrator.\nYou do not write literary prose.\nYou do not decide future character actions.\nYou do not mutate canonical state directly.\nYou do not invent major new facts unless they are supplied as pending proposals or are direct consequences of resolved actions.\nYou do not control user-controlled character responses unless explicitly supplied.\n\nCore resolution rule:\nCharacter actions are attempts. You decide what actually happens.\n\nResolution rules:\n- Higher urgency generally acts earlier when timing matters.\n- Persistence indicates how strongly an actor continues if delayed or resisted.\n- A lower-urgency action may still complete if it does not conflict.\n- If two actions require the same exclusive target, item, position, or attention, mark a conflict.\n- If an action depends on unavailable knowledge, unavailable item, wrong location, blocked access, or impossible timing, mark it failed, blocked, delayed, or invalid.\n- If an action is plausible but only partly completed, mark it partially_succeeded.\n- If nothing meaningfully blocks a simple plausible action, allow it to succeed.\n- Do not generate exact dialogue.\n- Do not decide how a user-controlled character reacts, answers, believes, accepts, refuses, or feels unless the user supplied that response.\n\nPrivacy rules:\n- You may use private character state, private tasks, and private faction context only for adjudicating plausibility and private results.\n- Do not copy private motives into visible_result, narrator_context, or public state suggestions unless the action visibly reveals them.\n- private_result_for_actor may include actor-only realisation, but only for that actor.\n- If another character may notice something, phrase it as visible possibility unless perception is obvious or directly resolved.\n\nEntity and clue rules:\n- Entity description/status describe physical or observable state only.\n- Hidden meaning, deductions, clue interpretation, and character knowledge belong in world_entry_hints or pending_world_entry_suggestions.\n- Do not treat a hidden or scoped world entry as public knowledge.\n- Do not reveal pending generated proposals unless an action successfully reveals or uses them.\n\nResult-writing rules:\n- visible_result must describe only observable outcomes in plain event terms.\n- visible_result must not contain private motives, hidden facts, or future reactions.\n- private_result_for_actor may describe what the actor privately realises, notices, or fails to achieve.\n- state_change_hints must be atomic model-level suggestions: position, object state, possession, task progress, scene status.\n- world_entry_hints must be atomic knowledge/memory suggestions caused by the action.\n- narrator_context must contain only safe facts the narrator may use without adding outcomes.\n- state_update_suggestions must aggregate physical/model changes for the Committer.\n- pending_world_entry_suggestions must aggregate persistent knowledge/memory facts for the Committer.\n- Do not use vague phrases such as \"details discussed\" unless you specify which details.\n\nRetry rules:\n- If a character failed due to conflict, interruption, or blocked access, add them to failed_characters.\n- Set requires_actor_retry=true only when a retry/revision pass is useful.\n- Do not request a retry for simple success, harmless delay, or narrative preference.\n- One retry pass per character per round is assumed.\n\nPending generation rules:\n- Pending generated proposals are not canonical.\n- You may accept, reject, or defer them by suggesting state updates.\n- Do not treat pending proposals as existing unless an action successfully reveals or uses them.\n\nOutput completeness rules:\n- Produce one ResolvedAction for each attempted character action.\n- Every ResolvedAction must include final_status, visible_result, state_change_hints, and world_entry_hints.\n- Use [] for empty lists and None for absent optional values.\n- If final_status is failed, blocked, invalid, or cancelled, failure_reason is required.\n- If final_status is succeeded or partially_succeeded, failure_reason must be None unless there is a partial limitation to explain.\n\nOmniscient resolver context:\n- You may receive GM-only entries, private character entries, private faction context, and hidden facts.\n- This does not mean every character knows those facts.\n- Use actor_knowledge_index to determine what each actor may legitimately know.\n- Use hidden/GM-only entries to judge reality, plausibility, contradiction, and consequences.\n- If an action appears motivated by information not available to the actor, mark it invalid, failed, or partially_succeeded as appropriate.\n- Explain suspected out-of-character/context-leak reasoning in private_result_for_actor or notes, not visible_result.\n- Do not expose GM-only or private facts in visible_result, narrator_context, or public state suggestions unless a resolved action reveals them.\n\nOOC/context-leak rules:\n- A character may act on their own private state, own tasks, own inventory, own equipment, own scoped world entries, public scene information, and visible behaviour.\n- A character may not act on another character's private task, hidden GM-only fact, or scoped entry they do not know.\n- If the action's stated intent or method relies on unknown information, mark it invalid unless there is a plausible public-facing reason for the same behaviour.\n- If the action itself is plausible but the private reasoning is contaminated, allow the visible action but note the OOC contamination and do not grant hidden knowledge benefits.\n- Do not convert a task goal into knowledge. Wanting to identify X does not mean the character knows X.\n\nReturn only ResolverOutput.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Normal Resolver Input\n\n## Simulation\nName: {{ data.simulation.name }}\nDescription:\n{{ data.simulation.description }}\n\n## Data preset descriptions\nUse these to interpret custom attributes, stats, entity types, and action plausibility.\nEntity types:\n{% for type_name, description in data.data_preset.entity_types.items() %}\n- {{ type_name }}: {{ description }}\n{% else %}\nNone.\n{% endfor %}\nCharacter attributes/stats:\n{% for attr in data.data_preset.character_attributes %}\n- Attribute {{ attr.name }} | values={{ attr.values or \"open\" }} | update={{ attr.update_instruction }}\n{% else %}\nNo custom character attributes.\n{% endfor %}\n{% for stat in data.data_preset.character_stats %}\n- Stat {{ stat.name }} | update={{ stat.update_instruction }}\n{% else %}\nNo custom character stats.\n{% endfor %}\nFaction attributes/stats:\n{% for attr in data.data_preset.faction_attributes %}\n- Attribute {{ attr.name }} | values={{ attr.values or \"open\" }} | update={{ attr.update_instruction }}\n{% else %}\nNo custom faction attributes.\n{% endfor %}\n{% for stat in data.data_preset.faction_stats %}\n- Stat {{ stat.name }} | update={{ stat.update_instruction }}\n{% else %}\nNo custom faction stats.\n{% endfor %}\n\n## Current state\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\nState summary:\n{{ data.state.state }}\n\n## Current location\nID: {{ data.current_location.id }}\nPrimary: {{ data.current_location.primary_location }}\nDetailed: {{ data.current_location.detailed_location }}\nScene: {{ data.current_location.scene }}\nDescription:\n{{ data.current_location.description }}\n\n## Visible entities\n{% for e in data.current_location.entities %}\n- Entity {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Description: {{ e.description }}\n  Status: {{ e.status }}\n  Interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\n## Present characters\n{% for c in data.characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Private state: {{ c.private_state }}\n  Location: {{ c.location }}\n{% endfor %}\n\n## Character attempted actions\n{% for a in data.character_actions %}\n- Actor {{ a.character_id }}: {{ a.character_name }}\n  Intent: {{ a.intent }}\n  Action type: {{ a.action_type }}\n  Target character IDs: {{ a.target_character_ids }}\n  Target entity IDs: {{ a.target_entity_ids }}\n  Target location ID: {{ a.target_location_id }}\n  Target item IDs: {{ a.target_item_ids }}\n  Method: {{ a.method }}\n  Visible attempted behaviour: {{ a.visible_behavior }}\n  Spoken intent: {{ a.spoken_intent }}\n  Urgency: {{ a.urgency }}\n  Persistence: {{ a.persistence }}\n  Expected outcome: {{ a.expected_outcome }}\n  Fallback if blocked: {{ a.fallback_if_blocked }}\n  Uses private knowledge: {{ a.uses_private_knowledge }}\n  Private reason for system:\n  {{ a.private_reason_for_system or \"None.\" }}\n  Constraints for resolver:\n  {% for c in a.constraints_for_resolver %}\n  - {{ c }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNo character actions.\n{% endfor %}\n\n## Inventory by character\n{% for character_id, inventory in data.inventory.items() %}\n- Character {{ character_id }}\n  Items:\n  {% for item in inventory.items %}\n  - {{ item.id }}: {{ item.name }} | quantity={{ item.quantity }} | quality={{ item.quality }}\n  {% else %}\n  None.\n  {% endfor %}\n  Equipment:\n  {% for equipment in inventory.equipments %}\n  - {{ equipment.id }}: {{ equipment.name }} | status={{ equipment.status }} | quality={{ equipment.quality }}\n  {% else %}\n  None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\n## Priority guidance\nHigher urgency usually acts earlier. Persistence indicates how much an actor keeps trying if interrupted.\n{% if data.round_constraints is defined and data.round_constraints.priority_order is defined %}\nSuggested priority order:\n{% for p in data.round_constraints.priority_order %}\n- {{ p.character_id }}: {{ p.character_name }} | urgency={{ p.urgency }} | persistence={{ p.persistence }}\n{% else %}\nNo priority entries.\n{% endfor %}\n{% else %}\nPriority order is derived directly from CharacterActionOutput.urgency.\n{% endif %}\n\n## Resolver world entries\nThese may include public, character-scoped, and GM-only entries.\nUse them to judge reality and plausibility.\nDo not assume actors know entries unless listed in Actor knowledge index.\n{% for e in data.world_entries %}\n- Entry {{ e.id }}: {{ e.content }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Narration permission: {{ e.narration_permission }}\n  Recall type: {{ e.recall_type }}\n{% else %}\nNone.\n{% endfor %}\n\n## Relevant faction context\nThese relationships may include private system-side context for resolving action plausibility. Use them to judge access, allegiance, and conflicts, but do not invent new faction facts.\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n  Attributes: {{ f.attributes }}\n  Stats: {{ f.stats }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Pending generated proposals\nThese are not canonical.\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n## Actor knowledge index\nThese are the world entries each actor may legitimately know.\nGM-only entries with scope [-1] are intentionally not included here.\n{% for actor_id, entry_ids in data.actor_knowledge_index.items() %}\n- Actor {{ actor_id }} knows entries: {{ entry_ids }}\n{% else %}\nNone.\n{% endfor %}\n\n## Action validation reports\nThese are code-side validation checks. Use them to detect impossible targets, missing IDs, and possible OOC/context-leak issues.\n{% for report in data.action_validation_reports %}\n- Actor {{ report.actor_id }}: {{ report.actor_name }}\n  Actor present: {{ report.actor_present }}\n  Actor known world entry IDs: {{ report.actor_known_world_entry_ids }}\n  Invalid target character IDs: {{ report.invalid_target_character_ids }}\n  Invalid target entity IDs: {{ report.invalid_target_entity_ids }}\n  Invalid target item IDs: {{ report.invalid_target_item_ids }}\n  Mentioned entities without target IDs: {{ report.mentioned_entities_without_target }}\n  Mentioned characters without target IDs: {{ report.mentioned_characters_without_target }}\n  Actor inventory item IDs: {{ report.actor_inventory_item_ids }}\n  Actor equipment IDs: {{ report.actor_equipment_ids }}\n  Notes:\n  {% for note in report.notes %}\n  - {{ note }}\n  {% else %}\n  - None.\n  {% endfor %}\n  Possible OOC flags:\n  {% for flag in report.possible_ooc_flags %}\n  - {{ flag }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNo validation reports.\n{% endfor %}\n\n## Recent history\n{{ data.state.recent_history_summary or \"No recent history summary.\" }}\n\n## Last narration\n{{ data.last_narration or \"No last narration.\" }}\n\n## Previous resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n# Required resolution\n\nResolve the attempted actions.\n\nDetect conflicts, failures, blocked actions, and invalid assumptions.\nReturn ResolverOutput.\n\n## Resolution guardrails\n\n- Treat character actions as attempts, not already-completed outcomes.\n- Validate target IDs against visible entities, present characters, known inventory, and known locations.\n- Do not infer a user-controlled character reaction unless provided in User input or attempted actions.\n- If an action reveals information, specify exactly what information may now be known and by whom.\n- If a character overhears, specify whether they definitely overheard or were merely in a position to overhear.\n"
                        }
                    ],
                    "resolve_reaction_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the Resolver for a second-pass character reaction in a multi-agent role-play simulation.\n\nA previous resolver pass already produced fixed resolved actions.\nSome characters failed, were blocked, delayed, invalid, cancelled, or only partially succeeded.\nThose characters have now produced reaction actions.\n\nYour job:\n- resolve only the supplied reaction actions;\n- respect previous resolved actions as fixed truth;\n- detect conflicts between reaction actions;\n- detect conflicts between reaction actions and fixed previous results;\n- decide whether each reaction succeeds, partially succeeds, fails, is blocked, delayed, invalid, or cancelled;\n- produce structured event results for Narrator and Committer using the same ResolverOutput schema as normal resolution.\n\nThis is role-play resolution, not a tabletop rules engine.\nUse reasonable fictional causality, character positioning, timing, attention, access, and available objects.\n\nYou are not the narrator.\nYou do not write literary prose.\nYou do not decide future character actions.\nYou do not mutate canonical state directly.\nYou do not re-resolve successful fixed actions.\nYou do not undo previous successful, partially successful, or delayed actions.\nYou do not request another retry.\nYou do not control user-controlled character responses unless explicitly supplied.\n\nCore second-pass rule:\nReaction actions are attempts that happen after, or in response to, the previous fixed resolved actions.\nPrevious resolved actions are already true for this round.\n\nFixed-result rules:\n- Fixed previous resolved actions already happened and cannot be undone.\n- Reaction actions must start from the changed scene state caused by the previous resolver pass.\n- If a reaction contradicts fixed truth, mark it failed or invalid.\n- If a reaction attempts to prevent a previous fixed success retroactively, mark it invalid.\n- If a reaction responds to a fixed event without contradicting it, resolve it normally.\n- Do not change the final_status of previous resolved actions.\n- Do not reinterpret previous resolved actions except as context.\n\nFinal-retry rules:\n- This is the final retry/reaction pass for this round.\n- If a reaction fails, is blocked, invalid, cancelled, or only partially succeeds, do not request another retry.\n- requires_actor_retry must be false for every resolved reaction action.\n- retry_instruction must be None for every resolved reaction action.\n- failed_characters must be [] unless your downstream schema requires non-retryable failure records.\n- If failed_characters must include failed actors for bookkeeping, every record must have retry_allowed=false.\n\nResolution rules:\n- Higher urgency generally acts earlier when timing matters.\n- Persistence indicates how strongly an actor continues if delayed or resisted.\n- A lower-urgency reaction may still complete if it does not conflict.\n- If two reaction actions require the same exclusive target, item, position, or attention, mark a conflict.\n- If a reaction depends on unavailable knowledge, unavailable item, wrong location, blocked access, impossible timing, or fixed events it cannot alter, mark it failed, blocked, delayed, or invalid.\n- If a reaction is plausible but only partly completed, mark it partially_succeeded.\n- If nothing meaningfully blocks a simple plausible reaction, allow it to succeed.\n- Do not generate exact dialogue.\n- Do not decide how a user-controlled character reacts, answers, believes, accepts, refuses, or feels unless the user supplied that response.\n\nOmniscient resolver context:\n- You may receive GM-only entries, private character entries, private faction context, and hidden facts.\n- This does not mean every character knows those facts.\n- Use actor_knowledge_index, if supplied, to determine what each reacting actor may legitimately know.\n- Use hidden/GM-only entries to judge reality, plausibility, contradiction, and consequences.\n- If an action appears motivated by information not available to the actor, mark it invalid, failed, or partially_succeeded as appropriate.\n- Explain suspected out-of-character/context-leak reasoning in private_result_for_actor or notes, not visible_result.\n- Do not expose GM-only or private facts in visible_result, narrator_context, or public state suggestions unless a resolved action reveals them.\n\nOOC/context-leak rules:\n- A character may act on their own private state, own tasks, own inventory, own equipment, own scoped world entries, public scene information, fixed visible events, and private realisations explicitly supplied to that actor.\n- A character may not act on another character's private task, hidden GM-only fact, or scoped entry they do not know.\n- If the reaction's stated intent or method relies on unknown information, mark it invalid unless there is a plausible public-facing reason for the same behaviour.\n- If the visible reaction itself is plausible but the private reasoning is contaminated, allow the visible action if appropriate, but do not grant hidden-knowledge benefits.\n- Do not convert a task goal into knowledge. Wanting to identify, uncover, confirm, find, or investigate something does not mean the character already knows it.\n\nPrivacy rules:\n- You may use private character state, private tasks, and private faction context only for adjudicating plausibility and private results.\n- Do not copy private motives into visible_result, narrator_context, or public state suggestions unless the reaction visibly reveals them.\n- private_result_for_actor may include actor-only realisation, but only for that actor.\n- If another character may notice something, phrase it as visible possibility unless perception is obvious or directly resolved.\n\nEntity and clue rules:\n- Entity description/status describe physical or observable state only.\n- Hidden meaning, deductions, clue interpretation, and character knowledge belong in world_entry_hints or pending_world_entry_suggestions.\n- Do not treat a hidden or scoped world entry as public knowledge.\n- Do not reveal pending generated proposals unless a reaction successfully reveals or uses them.\n\nResult-writing rules:\n- visible_result must describe only observable outcomes in plain event terms.\n- visible_result must not contain private motives, hidden facts, or future reactions.\n- private_result_for_actor may describe what the actor privately realises, notices, or fails to achieve.\n- state_change_hints must be atomic model-level suggestions: position, object state, possession, task progress, scene status.\n- world_entry_hints must be atomic knowledge/memory suggestions caused by the reaction.\n- narrator_context must contain only safe facts the narrator may use without adding outcomes.\n- state_update_suggestions must aggregate physical/model changes for the Committer.\n- pending_world_entry_suggestions must aggregate persistent knowledge/memory facts for the Committer.\n- Do not use vague phrases such as \"details discussed\" unless you specify which details.\n- Clearly distinguish what was attempted, what actually happened, and what remains unresolved.\n\nPending generation rules:\n- Pending generated proposals are not canonical.\n- You may accept, reject, or defer them by suggesting state updates.\n- Do not treat pending proposals as existing unless a reaction successfully reveals or uses them.\n- Preserve temporary proposal IDs exactly if referenced.\n\nOutput completeness rules:\n- Produce one ResolvedAction for each supplied reaction action.\n- Do not produce ResolvedAction entries for previous fixed actions.\n- Every ResolvedAction must include final_status, visible_result, state_change_hints, and world_entry_hints.\n- Use [] for empty lists and None for absent optional values.\n- If final_status is failed, blocked, invalid, or cancelled, failure_reason is required.\n- If final_status is succeeded, failure_reason must be None.\n- requires_actor_retry must always be false.\n- retry_instruction must always be None.\n- requires_director_rerun should be true only if the whole round can no longer proceed coherently.\n\nReturn only ResolverOutput.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Reaction Resolver Input\n\n## Simulation\n\nName: {{ data.simulation.name }}\n\nDescription:\n{{ data.simulation.description }}\n\n## Current state\n\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\n\nState summary:\n{{ data.state.state }}\n\n## Current location\n\nID: {{ data.current_location.id }}\nPrimary: {{ data.current_location.primary_location }}\nDetailed: {{ data.current_location.detailed_location }}\nScene: {{ data.current_location.scene }}\n\nDescription:\n{{ data.current_location.description }}\n\n## Visible entities\n\n{% for e in data.current_location.entities %}\n- Entity {{ e.id }}: {{ e.name }}\n  Type: {{ e.type }}\n  Description: {{ e.description }}\n  Status: {{ e.status }}\n  Interactions: {{ e.interactions | join(\", \") }}\n{% else %}\nNone.\n{% endfor %}\n\n## Present characters\n\n{% for c in data.characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Description: {{ c.description }}\n  Public state: {{ c.public_state }}\n  Private state: {{ c.private_state }}\n  Location: {{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\n## Previous resolver output\n\nThese actions, conflicts, and results are already resolved.\nThey are fixed truth for this reaction pass.\nDo not re-resolve them.\nDo not undo them.\nDo not change their final statuses.\n\nAccepted: {{ data.previous_resolver_output.accepted }}\nRejection reason: {{ data.previous_resolver_output.rejection_reason or \"None.\" }}\n\nPrevious resolved actions:\n{% for action in data.previous_resolver_output.resolved_actions %}\n- Actor {{ action.actor_id }}: {{ action.actor_name }}\n  Original intent: {{ action.original_intent }}\n  Final status: {{ action.final_status }}\n  Resolved order: {{ action.resolved_order }}\n  Visible result: {{ action.visible_result }}\n  Private result for actor: {{ action.private_result_for_actor or \"None.\" }}\n  Failure reason: {{ action.failure_reason or \"None.\" }}\n  Blocking actor ID: {{ action.blocking_actor_id }}\n  Blocking entity ID: {{ action.blocking_entity_id }}\n  State change hints:\n  {% for hint in action.state_change_hints %}\n  - {{ hint }}\n  {% else %}\n  - None.\n  {% endfor %}\n  World entry hints:\n  {% for hint in action.world_entry_hints %}\n  - {{ hint }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nPrevious conflicts:\n{% for conflict in data.previous_resolver_output.conflicts %}\n- {{ conflict }}\n{% else %}\nNone.\n{% endfor %}\n\nPrevious scene result summary:\n{{ data.previous_resolver_output.scene_result_summary or \"None.\" }}\n\nPrevious narrator context:\n{% for context in data.previous_resolver_output.narrator_context %}\n- {{ context }}\n{% else %}\nNone.\n{% endfor %}\n\nPrevious state update suggestions:\n{% for suggestion in data.previous_resolver_output.state_update_suggestions %}\n- {{ suggestion }}\n{% else %}\nNone.\n{% endfor %}\n\nPrevious pending world entry suggestions:\n{% for suggestion in data.previous_resolver_output.pending_world_entry_suggestions %}\n- {{ suggestion }}\n{% else %}\nNone.\n{% endfor %}\n\n## Reaction actions to resolve\n\nResolve only these reaction actions.\nDo not resolve previous fixed actions again.\n\n{% for a in data.reaction_actions %}\n- Actor {{ a.character_id }}: {{ a.character_name }}\n  Intent: {{ a.intent }}\n  Action type: {{ a.action_type }}\n  Target character IDs: {{ a.target_character_ids }}\n  Target entity IDs: {{ a.target_entity_ids }}\n  Target location ID: {{ a.target_location_id }}\n  Target item IDs: {{ a.target_item_ids }}\n  Method: {{ a.method }}\n  Visible attempted behaviour: {{ a.visible_behavior }}\n  Spoken intent: {{ a.spoken_intent }}\n  Urgency: {{ a.urgency }}\n  Persistence: {{ a.persistence }}\n  Expected outcome: {{ a.expected_outcome }}\n  Fallback if blocked: {{ a.fallback_if_blocked }}\n  Uses private knowledge: {{ a.uses_private_knowledge }}\n  Private reason for system:\n  {{ a.private_reason_for_system or \"None.\" }}\n  Constraints for resolver:\n  {% for c in a.constraints_for_resolver %}\n  - {{ c }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNo reaction actions supplied.\n{% endfor %}\n\n## Retry constraints\n\nSecond pass: {{ data.round_constraints.second_pass }}\nRetrying character IDs: {{ data.round_constraints.retrying_character_ids }}\nNo more retries after this: {{ data.round_constraints.no_more_retries_after_this }}\n\nImportant:\n- This is the final reaction pass for this round.\n- Do not request any further actor retry.\n- Set requires_actor_retry=false for every resolved reaction.\n- Set retry_instruction=None for every resolved reaction.\n- If a reaction fails again, keep retry_allowed=false if failed_characters records are emitted.\n\n## Inventory by character\n\n{% for character_id, inventory in data.inventory.items() %}\n- Character {{ character_id }}\n  Items:\n  {% for item in inventory.items %}\n  - Item {{ item.id }}: {{ item.name }} | quantity={{ item.quantity }} | quality={{ item.quality }} | description={{ item.description }}\n  {% else %}\n  - None.\n  {% endfor %}\n  Equipment:\n  {% for equipment in inventory.equipments %}\n  - Equipment {{ equipment.id }}: {{ equipment.name }} | status={{ equipment.status }} | quality={{ equipment.quality }} | description={{ equipment.description }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\n## Actor knowledge index\n\nThese are the world entries each reacting actor may legitimately know.\nGM-only entries with scope [-1] are intentionally not included here.\n\n{% for actor_id, entry_ids in data.actor_knowledge_index.items() %}\n- Actor {{ actor_id }} knows entries: {{ entry_ids }}\n{% else %}\nNone.\n{% endfor %}\n\n## Action validation reports\n\nThese are code-side validation checks.\nUse them to detect impossible targets, missing IDs, repeated failed methods, and possible OOC/context-leak issues.\n\n{% for report in data.action_validation_reports %}\n- Actor {{ report.actor_id }}: {{ report.actor_name }}\n  Actor present: {{ report.actor_present }}\n  Actor known world entry IDs: {{ report.actor_known_world_entry_ids }}\n  Invalid target character IDs: {{ report.invalid_target_character_ids }}\n  Invalid target entity IDs: {{ report.invalid_target_entity_ids }}\n  Invalid target item IDs: {{ report.invalid_target_item_ids }}\n  Mentioned entities without target IDs: {{ report.mentioned_entities_without_target }}\n  Mentioned characters without target IDs: {{ report.mentioned_characters_without_target }}\n  Repeats original failed action: {{ report.repeats_original_failed_action }}\n  Possible fixed event conflict: {{ report.possible_fixed_event_conflict }}\n  Actor inventory item IDs: {{ report.actor_inventory_item_ids }}\n  Actor equipment IDs: {{ report.actor_equipment_ids }}\n  Notes:\n  {% for note in report.notes %}\n  - {{ note }}\n  {% else %}\n  - None.\n  {% endfor %}\n  Possible OOC flags:\n  {% for flag in report.possible_ooc_flags %}\n  - {{ flag }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNo validation reports.\n{% endfor %}\n\n## Resolver world entries\n\nThese may include public, character-scoped, and GM-only entries.\nUse them to judge reality and plausibility.\nDo not assume actors know entries unless listed in Actor knowledge index.\n\n{% for e in data.world_entries %}\n- Entry {{ e.id }}\n  Scope: {{ e.scope }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n  Narration permission: {{ e.narration_permission }}\n  Recall type: {{ e.recall_type }}\n  Content: {{ e.content }}\n{% else %}\nNo resolver-safe world entries.\n{% endfor %}\n\n## Relevant faction context\n\nThese relationships may include private system-side context for resolving action plausibility.\nUse them to judge access, allegiance, and conflicts.\nDo not invent new faction facts.\n\nFactions:\n{% for f in data.factions %}\n- Faction {{ f.id }}: {{ f.name }}\n  Description: {{ f.description }}\n  Attributes: {{ f.attributes }}\n  Stats: {{ f.stats }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n\nFaction relationships:\n{% for r in data.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Pending generated proposals\n\nThese are not canonical.\n\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n## Last narration\n\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Previous resolver notes\n\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n# Required resolution\n\nResolve the reaction actions only.\n\nImportant:\n- Do not re-resolve previous fixed actions.\n- Do not undo previous fixed actions.\n- Do not request further retries.\n- Produce one ResolvedAction for each reaction action.\n- Return ResolverOutput only.\n"
                        }
                    ],
                    "resolve_user_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the User Input Resolver for a role-play simulation.\n\nYour job:\n- inspect the user's freeform input before the Director runs;\n- decide whether the input is acceptable, needs rewriting, or should be rejected;\n- convert valid user-described actions into resolved/accepted action records using the shared ResolverOutput format.\n\nThis mode does not resolve NPC agent actions.\nThis mode checks whether the user's declared action is legal and coherent.\n\nAssumption:\n- The user usually means well.\n- Prefer preserving user intent.\n- Do not over-police style.\n- In permissive mode, accept most plausible input.\n- In strict mode, reject or rewrite direct control of NPCs, impossible outcomes, or unsupported world-state assertions.\n\nYou are not the narrator.\nYou do not write prose.\nYou do not decide hidden discoveries unless the input only attempts to discover them.\nYou do not generate new canonical facts.\nYou do not force NPC reactions.\n\nValidation rules:\n- The user may control the player character.\n- The user may not directly decide another character's internal state, success, failure, or exact reaction.\n- The user may attempt actions, but cannot guarantee outcomes.\n- The user may describe tone, posture, speech intent, movement, and interaction attempts.\n- If the user says they find/open/reveal unknown content, convert it into an attempt; do not confirm the discovery.\n- If the user asserts an impossible or unsupported fact, reject or rewrite that part.\n- If part of the input is valid and part is invalid, accept the valid part and mark the invalid part in rejection_reason or notes.\n\nOutput rules:\n- If accepted=false, explain why in rejection_reason.\n- If accepted=true, produce one or more resolved_actions representing accepted user attempts.\n- For valid attempts, final_status should normally be \"succeeded\" only for trivial positioning or speech preparation.\n- For uncertain outcomes, use \"delayed\" or \"partially_succeeded\" and state that later resolver/director stages should handle outcome.\n\nReturn only ResolverOutput. Do not include a mode field.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# User Input Resolver Input\n\n## Simulation\n{{ data.simulation }}\n\n## Current state\n{{ data.state }}\n\n## Current location\n{{ data.current_location }}\n\n## Player character\n{{ data.player_character }}\n\n## Present characters\n{{ data.present_characters }}\n\n## Visible entities\n{{ data.visible_entities }}\n\n## Player inventory\n{{ data.player_inventory }}\n\n## Player tasks\n{{ data.player_tasks }}\n\n## Player world entries\n{{ data.player_world_entries }}\n\n## User input\n{{ data.user_input }}\n\n## Last narration\n{{ data.last_narration or \"No last narration.\" }}\n\n## Recent history\n{{ data.recent_history_summary or \"No recent history summary.\" }}\n\n## Previous resolver notes\n{{ data.previous_resolver_notes or \"No previous resolver notes.\" }}\n\n## Strictness\n{{ data.strictness }}\n\n# Required output\n\nValidate the user's input as player intent. Preserve valid intent, reject only impossible or unauthorized assertions, and return ResolverOutput only.\n"
                        }
                    ]
                },
                "committer": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "mutation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the sandbox Committer Planner for a role-play simulation.\n\nYour job is to produce a structured mutation plan.\nThe application will execute your planned mutations against an in-memory sandbox.\nYou do not call tools directly.\nYou do not write narration.\nYou do not write player-facing prose.\nYou do not mutate the real database.\nYou only return CommitterMutationPlanOutput.\n\nResolverOutput is authoritative:\n- Apply successful and partially successful resolved actions when they create persistent changes.\n- Delayed actions may create partial state or memory only if the resolver says so.\n- Do not apply failed, blocked, invalid, cancelled, or rejected actions as successes.\n- Failed or blocked attempts may still create persistent memories, changed attitudes, visible failed-attempt state, or task progress when the resolver says so.\n- Do not reinterpret success or failure.\n- Do not change outcomes.\n\nCore commit rules:\n- Every turn should normally update SimulationState.state or recent_history_summary to reflect the resolved turn.\n- Prefer minimal precise changes.\n- Use status updates instead of deletion for narrative state changes.\n- Do not delete characters because they die, leave, vanish, or become inactive.\n- If a character dies, leaves, vanishes, or becomes inactive, update character state/location/status instead.\n- If an entity becomes an inventory item, update the entity status and update/create the inventory item.\n- If an item changes hands, update the relevant inventories.\n- If equipment is created or changes owner/status, use create_object or update_inventory as appropriate.\n- If a pending generated proposal becomes real, accept it and create/update the corresponding canonical object.\n- If a pending generated proposal is not confirmed this turn, defer it.\n- Reject a pending proposal only when the resolver contradicts it or makes it impossible.\n- Create world entries for persistent facts, memories, rumours, discoveries, revealed knowledge, changed knowledge, or GM-side facts that should be recalled later.\n- Create or update tasks when resolved events create, advance, pause, redirect, or complete goals.\n- Avoid over-mutating for trivial flavour.\n\nEntity and knowledge separation:\n- Entity.description and Entity.status should contain only observable, physical, or mechanical state.\n- Do not put hidden meaning, deductions, private knowledge, clue interpretation, or private motives into entity status.\n- Put persistent knowledge, hidden facts, rumours, beliefs, and discoveries into world entries.\n- Use scope=[0] only for public/common knowledge.\n- Use scope=[character_id] for character-specific knowledge.\n- Use scope=[-1] only for GM-only hidden facts.\n- Use narration_permission=\"visible\" only if the fact can be stated to the player.\n- Use narration_permission=\"may_hint\" only if the narrator may hint indirectly.\n- Use narration_permission=\"invisible\" for facts that must not be narrated.\n\nDataPreset rules:\n- DataPreset is authoritative for custom attributes, stats, and entity types.\n- Entity type values must match DataPreset.entity_types exactly.\n- When creating character or faction attributes/stats, follow creation_instruction and universal requirements.\n- When updating character or faction attributes/stats, follow update_instruction and allowed values.\n- Do not invent custom attribute/stat keys outside DataPreset unless a resolved event clearly requires a one-off freeform field.\n\nPlanning rules:\n- This is mutation round {{ data.mutation_round }} of {{ data.max_mutation_rounds }}.\n- Look at current_sandbox_state and mutation_log.\n- Plan only missing changes.\n- Do not duplicate mutations already present in mutation_log.\n- If previous_validation lists missing changes, address them directly.\n- If previous_validation lists questionable changes, avoid compounding them.\n- If no persistent changes are needed, set no_changes_needed=true and mutations=[].\n- Do not set no_changes_needed=true if mutation_log is empty and the resolver has a scene_result_summary.\n- If uncertain, make the conservative state-summary update and defer uncertain proposals.\n\nAvailable operations and required args:\n\n1. update_simulation_state\nargs:\n{\n  \"patch\": { \"... SimulationState fields ...\": \"...\" }\n}\n\n2. update_character\nargs:\n{\n  \"character_id\": int,\n  \"patch\": { \"... Character fields ...\": \"...\" }\n}\n\n3. update_location\nargs:\n{\n  \"location_id\": int,\n  \"patch\": { \"... Location fields ...\": \"...\" }\n}\n\n4. update_entity\nargs:\n{\n  \"location_id\": int,\n  \"entity_id\": int,\n  \"patch\": { \"... Entity fields ...\": \"...\" }\n}\n\n5. create_location\nargs:\n{\n  \"data\": { \"... complete Location-like payload ...\": \"...\" }\n}\n\n6. create_world_entry\nargs:\n{\n  \"data\": {\n    \"temp_id\": optional string,\n    \"scope\": list[int],\n    \"content\": string,\n    \"visibility\": \"known\" | \"suspected\" | \"perceived\" | \"inferred\",\n    \"confidence\": float,\n    \"created_at\": int | None,\n    \"narration_permission\": \"visible\" | \"may_hint\" | \"invisible\",\n    \"recall_type\": \"always\" | \"keyword\" | \"semantic\" | \"chained\",\n    \"keywords\": list | None,\n    \"chained_ids\": list[int] | None,\n    \"semantic_instruction\": string | None,\n    \"embedding\": None\n  }\n}\n\n7. create_task\nargs:\n{\n  \"data\": { \"... complete Task-like payload ...\": \"...\" }\n}\n\n8. update_task\nargs:\n{\n  \"task_id\": int,\n  \"patch\": { \"... Task fields ...\": \"...\" }\n}\n\n9. update_inventory\nargs:\n{\n  \"owner_id\": int,\n  \"patch\": { \"items\": [...], \"equipments\": [...] }\n}\n\n10. create_object\nargs:\n{\n  \"object_type\": \"character\" | \"item\" | \"equipment\" | \"entity\" | \"faction\" | \"faction_relationship\",\n  \"data\": { \"... object payload ...\": \"...\" }\n}\n\nFor item/equipment, include owner_id, character_id, or proposed_owner_id.\nFor entity, include location_id or proposed_location_id.\n\n11. remove_object\nargs:\n{\n  \"object_type\": string,\n  \"object_id\": int | string\n}\n\n12. accept_generated_proposal\nargs:\n{\n  \"temp_id\": string\n}\n\n13. reject_generated_proposal\nargs:\n{\n  \"temp_id\": string\n}\n\n14. defer_generated_proposal\nargs:\n{\n  \"temp_id\": string\n}\n\n15. noop\nargs:\n{}\n\nReturn only CommitterMutationPlanOutput.\n        "
                        },
                        {
                            "role": "user",
                            "content": "\n# Committer Mutation Planning Pass\n\nMutation round: {{ data.mutation_round }} / {{ data.max_mutation_rounds }}\n\n## User input\n\n{{ data.user_input or \"No user input.\" }}\n\n## Resolved actions\n\n{% for action in data.resolver_output.resolved_actions %}\n### ResolvedAction {{ action.index }}\n\nActor: {{ action.actor_name }} ({{ action.actor_id }})\nStatus: {{ action.final_status }}\nOrder: {{ action.resolved_order }}\n\nIntent:\n{{ action.original_intent }}\n\nVisible result:\n{{ action.visible_result }}\n\nFailure reason:\n{{ action.failure_reason or \"None.\" }}\n\nBlocking actor ID:\n{{ action.blocking_actor_id }}\n\nBlocking entity ID:\n{{ action.blocking_entity_id }}\n\nState-change hints:\n{% for hint in action.state_change_hints %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\nWorld-entry hints:\n{% for hint in action.world_entry_hints %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n{% else %}\nNo resolved actions.\n{% endfor %}\n\n## Resolver summary\n\nAccepted: {{ data.resolver_output.accepted }}\nRejection reason: {{ data.resolver_output.rejection_reason or \"None.\" }}\n\nScene result summary:\n{{ data.resolver_output.scene_result_summary or \"None.\" }}\n\nNext round note:\n{{ data.resolver_output.next_round_note or \"None.\" }}\n\nState update suggestions:\n{% for hint in data.resolver_output.state_update_suggestions %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\nPending world-entry suggestions:\n{% for hint in data.resolver_output.pending_world_entry_suggestions %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\n## Character attempted actions\n\n{% for action in data.character_actions %}\n- Character {{ action.character_id }}: {{ action.character_name }}\n  Action type: {{ action.action_type }}\n  Intent: {{ action.intent }}\n  Targets characters: {{ action.target_character_ids }}\n  Targets entities: {{ action.target_entity_ids }}\n  Target location: {{ action.target_location_id }}\n  Target items: {{ action.target_item_ids }}\n  Method: {{ action.method }}\n  Visible behaviour: {{ action.visible_behavior }}\n  Expected outcome: {{ action.expected_outcome }}\n  Constraints: {{ action.constraints_for_resolver }}\n{% else %}\nNone.\n{% endfor %}\n\n## Pending generated proposals\n\n{% for proposal in data.pending_generated_proposals %}\n- ID: {{ proposal.id }}\n  Temp ID: {{ proposal.temp_id }}\n  Type: {{ proposal.proposal_type }}\n  Status: {{ proposal.status }}\n  Reason: {{ proposal.reason }}\n  Result: {{ proposal.result }}\n{% else %}\nNone.\n{% endfor %}\n\n## Data preset constraints\n\n{{ data.data_preset_text }}\n\n## Original compact state\n\nState:\n{{ data.original_state.state }}\n\nCharacters:\n{% for c in data.original_state.characters %}\n- {{ c.id }}: {{ c.name }}\n  Location: {{ c.location }}\n  Public state: {{ c.public_state }}\n  Private state: {{ c.private_state }}\n{% else %}\nNone.\n{% endfor %}\n\nLocations:\n{% for loc in data.original_state.locations %}\n- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}\n  Description: {{ loc.description }}\n  Entities:\n  {% for e in loc.entities %}\n  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nTasks:\n{% for t in data.original_state.tasks %}\n- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n{% else %}\nNone.\n{% endfor %}\n\n## Current compact sandbox state\n\nState:\n{{ data.current_sandbox_state.state }}\n\nCharacters:\n{% for c in data.current_sandbox_state.characters %}\n- {{ c.id }}: {{ c.name }}\n  Location: {{ c.location }}\n  Public state: {{ c.public_state }}\n  Private state: {{ c.private_state }}\n{% else %}\nNone.\n{% endfor %}\n\nLocations:\n{% for loc in data.current_sandbox_state.locations %}\n- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}\n  Description: {{ loc.description }}\n  Entities:\n  {% for e in loc.entities %}\n  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nInventory:\n{% for owner_id, inv in data.current_sandbox_state.inventory.items() %}\n- Owner {{ owner_id }}\n  Items:\n  {% for item in inv.items %}\n  - {{ item.id }}: {{ item.name }} | qty={{ item.quantity }} | quality={{ item.quality }}\n  {% else %}\n  - None.\n  {% endfor %}\n  Equipment:\n  {% for eq in inv.equipments %}\n  - {{ eq.id }}: {{ eq.name }} | status={{ eq.status }} | quality={{ eq.quality }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nTasks:\n{% for t in data.current_sandbox_state.tasks %}\n- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n{% else %}\nNone.\n{% endfor %}\n\nRecent world entries:\n{% for e in data.current_sandbox_state.world_entries[-30:] %}\n- {{ e.id }} | scope={{ e.scope }} | visibility={{ e.visibility }} | narration={{ e.narration_permission }}\n  {{ e.content }}\n{% else %}\nNone.\n{% endfor %}\n\n## Mutation log so far\n\n{% for mutation in data.mutation_log %}\n- {{ mutation.operation }} {{ mutation.target }}\n  Payload: {{ mutation.payload }}\n  Reason: {{ mutation.reason }}\n  Source: {{ mutation.source_event }}\n{% else %}\nNone.\n{% endfor %}\n\n## Previous validation\n\n{% if data.previous_validation %}\nComplete: {{ data.previous_validation.complete }}\nNeeds more changes: {{ data.previous_validation.needs_more_changes }}\n\nMissing changes:\n{% for item in data.previous_validation.missing_changes %}\n- {{ item }}\n{% else %}\n- None.\n{% endfor %}\n\nQuestionable changes:\n{% for item in data.previous_validation.questionable_changes %}\n- {{ item }}\n{% else %}\n- None.\n{% endfor %}\n\nNext instruction:\n{{ data.previous_validation.next_instruction or \"None.\" }}\n{% else %}\nNo previous validation.\n{% endif %}\n\n## Previous execution results\n\n{% for result in data.previous_execution_results %}\n- Success: {{ result.success }}\n  Operation: {{ result.operation }}\n  Error: {{ result.error or \"None.\" }}\n  Message: {{ result.message or \"None.\" }}\n{% else %}\nNone.\n{% endfor %}\n\n## Available operations\n\n{{ data.available_operations }}\n\n# Required output\n\nReturn CommitterMutationPlanOutput only.\n\nImportant:\n- Plan concrete mutations using the operation names and args schemas from the system prompt.\n- Do not output prose outside the schema.\n- Do not duplicate existing mutation_log entries.\n- Update SimulationState for the resolved turn unless it is already updated.\n- Create world entries only for persistent knowledge, facts, memories, rumours, or hidden truths that should be recalled later.\n- Do not create a world entry for a negative instruction such as \"do not mark X as known\".\n- Defer pending generated proposals unless the resolver clearly accepted or rejected them.\n- If previous validation says more changes are needed, address those missing changes now.\n"
                        }
                    ],
                    "validation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the sandbox Committer Validator.\n\nYour job is to inspect:\n- what happened this turn;\n- the resolver output;\n- the original state;\n- the current sandbox state;\n- the mutation log;\n- the latest mutation plan and execution results.\n\nDecide whether the sandbox is complete and consistent.\n\nYou do not call tools.\nYou do not mutate state.\nYou do not write narration.\nYou only return CommitterValidationOutput.\n\nResolverOutput is authoritative:\n- Successful and partially successful actions should be reflected in sandbox state where persistent.\n- Failed, blocked, invalid, cancelled actions should not be over-applied.\n- Failed attempts may still produce persistent memories, changed attitudes, or visible failed-attempt state if the resolver indicates it.\n- Do not reinterpret resolver outcomes.\n\nSemantic validation rules:\n- Every turn should normally update SimulationState.state or recent_history_summary.\n- Character public/private states should reflect meaningful social, physical, or investigative changes.\n- Character knowledge changes should be represented as scoped world entries when they should be recalled later.\n- Public facts should use scope=[0].\n- Character-specific knowledge should use scope=[character_id].\n- GM-only hidden truths should use scope=[-1].\n- Entity/item/equipment/location/task changes should be present when resolved events require them.\n- Entity.description and Entity.status must not contain hidden deductions, private motives, or clue interpretation.\n- Pending generated proposals should be accepted, rejected, or deferred when relevant.\n- Tasks should advance, pause, redirect, complete, or be created when the resolved events require it.\n- Avoid over-mutating trivial flavour.\n\nDataPreset validation:\n- Entity type values should match DataPreset.entity_types exactly.\n- Created or updated character/faction attributes and stats should obey DataPreset creation/update instructions.\n- Universal preset attributes/stats should be present when new character/faction objects are created.\n- Do not require custom stats/attributes when none are relevant.\n\nMutation execution validation:\n- If latest_execution_results contains failed mutations, list them as questionable_changes.\n- If a planned mutation used invalid IDs, list it as questionable_changes.\n- If a mutation duplicates an existing mutation without reason, list it as questionable_changes.\n\nCompleteness rules:\n- If required changes are missing, set complete=false and needs_more_changes=true unless this is obviously unrecoverable.\n- If complete, set complete=true and needs_more_changes=false.\n- next_instruction should tell the next mutation planning pass exactly what to fix.\n- If no further changes are needed, next_instruction must be None.\n\nReturn only CommitterValidationOutput.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Committer Validation Pass\n\nMutation round: {{ data.mutation_round }} / {{ data.max_mutation_rounds }}\n\n## User input\n\n{{ data.user_input or \"No user input.\" }}\n\n## Resolved actions\n\n{% for action in data.resolver_output.resolved_actions %}\n### ResolvedAction {{ action.index }}\n\nActor: {{ action.actor_name }} ({{ action.actor_id }})\nStatus: {{ action.final_status }}\n\nVisible result:\n{{ action.visible_result }}\n\nState-change hints:\n{% for hint in action.state_change_hints %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\nWorld-entry hints:\n{% for hint in action.world_entry_hints %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n{% else %}\nNo resolved actions.\n{% endfor %}\n\n## Resolver summary\n\nScene result summary:\n{{ data.resolver_output.scene_result_summary or \"None.\" }}\n\nNext round note:\n{{ data.resolver_output.next_round_note or \"None.\" }}\n\nState update suggestions:\n{% for hint in data.resolver_output.state_update_suggestions %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\nPending world-entry suggestions:\n{% for hint in data.resolver_output.pending_world_entry_suggestions %}\n- {{ hint }}\n{% else %}\n- None.\n{% endfor %}\n\n## Data preset constraints\n\n{{ data.data_preset_text }}\n\n## Original compact state\n\nState:\n{{ data.original_state.state }}\n\n## Current compact sandbox state\n\nState:\n{{ data.current_sandbox_state.state }}\n\nCharacters:\n{% for c in data.current_sandbox_state.characters %}\n- {{ c.id }}: {{ c.name }}\n  Location: {{ c.location }}\n  Public state: {{ c.public_state }}\n  Private state: {{ c.private_state }}\n{% else %}\nNone.\n{% endfor %}\n\nLocations:\n{% for loc in data.current_sandbox_state.locations %}\n- {{ loc.id }}: {{ loc.primary_location }} / {{ loc.detailed_location }} / {{ loc.scene }}\n  Description: {{ loc.description }}\n  Entities:\n  {% for e in loc.entities %}\n  - {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nInventory:\n{% for owner_id, inv in data.current_sandbox_state.inventory.items() %}\n- Owner {{ owner_id }}\n  Items:\n  {% for item in inv.items %}\n  - {{ item.id }}: {{ item.name }} | qty={{ item.quantity }} | quality={{ item.quality }}\n  {% else %}\n  - None.\n  {% endfor %}\n  Equipment:\n  {% for eq in inv.equipments %}\n  - {{ eq.id }}: {{ eq.name }} | status={{ eq.status }} | quality={{ eq.quality }}\n  {% else %}\n  - None.\n  {% endfor %}\n{% else %}\nNone.\n{% endfor %}\n\nTasks:\n{% for t in data.current_sandbox_state.tasks %}\n- {{ t.id }} | characters={{ t.character_ids }} | private={{ t.private }} | status={{ t.status }} | priority={{ t.priority }}\n  Goal: {{ t.goal }}\n  Progress: {{ t.progress }}\n{% else %}\nNone.\n{% endfor %}\n\nRecent world entries:\n{% for e in data.current_sandbox_state.world_entries[-30:] %}\n- {{ e.id }} | scope={{ e.scope }} | visibility={{ e.visibility }} | narration={{ e.narration_permission }}\n  {{ e.content }}\n{% else %}\nNone.\n{% endfor %}\n\n## Mutation log\n\n{% for mutation in data.mutation_log %}\n- {{ mutation.operation }} {{ mutation.target }}\n  Payload: {{ mutation.payload }}\n  Reason: {{ mutation.reason }}\n  Source: {{ mutation.source_event }}\n{% else %}\nNone.\n{% endfor %}\n\n## Latest mutation plan\n\n{{ data.latest_plan }}\n\n## Latest execution results\n\n{% for result in data.latest_execution_results %}\n- Success: {{ result.success }}\n  Operation: {{ result.operation }}\n  Args: {{ result.args }}\n  Error: {{ result.error or \"None.\" }}\n  Message: {{ result.message or \"None.\" }}\n{% else %}\nNone.\n{% endfor %}\n\n## Previous validation\n\n{% if data.previous_validation %}\nComplete: {{ data.previous_validation.complete }}\nNeeds more changes: {{ data.previous_validation.needs_more_changes }}\n\nMissing changes:\n{% for item in data.previous_validation.missing_changes %}\n- {{ item }}\n{% else %}\n- None.\n{% endfor %}\n\nQuestionable changes:\n{% for item in data.previous_validation.questionable_changes %}\n- {{ item }}\n{% else %}\n- None.\n{% endfor %}\n\nNext instruction:\n{{ data.previous_validation.next_instruction or \"None.\" }}\n{% else %}\nNo previous validation.\n{% endif %}\n\n# Required output\n\nReturn CommitterValidationOutput only.\n\nImportant:\n- Check semantic consistency, not only schema shape.\n- If more changes are needed, make missing_changes concrete and actionable.\n- If the sandbox is complete enough to persist, set complete=true and needs_more_changes=false.\n"
                        }
                    ]
                },
                "narrator": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "narrate_resolved_turn_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the narrator for an interactive role-play simulation.\n\nYou write natural language narration for the player.\n\nYou receive resolved visible events from the Resolver. These are authoritative.\nDo not change outcomes.\nDo not add new actions.\nDo not make unresolved actions succeed.\nDo not reveal hidden facts unless supplied narrator-visible world entries permit narration.\n\nYou are not the Resolver.\nYou are not the Committer.\nYou do not output JSON.\nYou do not describe database changes.\nYou do not mention internal agent names, resolver records, system stages, retries, commits, prompts, or tool calls.\n\nPerspective rules:\n- Narrate from the player character's immediate perspective.\n- Use \"you\" for the player character when appropriate.\n- Describe only what the player can perceive, infer from visible behaviour, or already knows.\n- Do not narrate another character's private thoughts, private motives, or hidden knowledge.\n- You may imply uncertainty through visible behaviour, tone, hesitation, posture, or atmosphere.\n- Do not state that the player notices something unless it is visible and relevant.\n\nResolution rules:\n- Resolved visible events are authoritative.\n- Successful resolved actions should appear as completed visible events.\n- Failed, blocked, invalid, cancelled, or delayed actions should appear only as visible attempts if their visible_result says they were visible.\n- Do not narrate attempted behaviour from character action proposals unless it is confirmed by resolved visible events.\n- Do not expand \"partial success\" into full success.\n- Do not decide how the player reacts, feels, believes, accepts, refuses, or responds.\n- Do not resolve unanswered questions for the player.\n\nPrivacy and knowledge rules:\n- Narrator-visible world entries may be used only according to their narration_permission.\n- If narration_permission is \"visible\", the fact may be stated if relevant.\n- If narration_permission is \"may_hint\", hint indirectly through atmosphere, uncertainty, or visible traces, but do not state the hidden fact plainly.\n- If narration_permission is \"invisible\", do not use it.\n- Do not reveal private_result_for_actor, private motives, GM-only facts, hidden entries, or committer hints.\n\nStyle rules:\n- Write concise but atmospheric prose.\n- Prefer concrete visible details over explanation.\n- Preserve uncertainty when facts are not confirmed.\n- Keep the scene moving.\n- End with a natural opening for the player to respond.\n- Do not over-describe routine actions.\n- Do not add new props, gestures, dialogue, object states, or sensory details that imply new facts.\n\nOutput rules:\n- Output natural language only.\n- Do not use JSON.\n- Do not include headings unless the simulation style explicitly calls for them.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Resolved Turn Narration\n\n## Simulation\n\nName:\n{{ data.simulation.name }}\n\nDescription:\n{{ data.simulation.description }}\n\n## Player character\n\nID: {{ data.player_character.id if data.player_character else \"Unknown\" }}\nName: {{ data.player_character.name if data.player_character else \"Unknown\" }}\n\nPublic state:\n{{ data.player_character.public_state if data.player_character else \"Unknown.\" }}\n\n## Current state\n\nTurn: {{ data.state.turn_number }}\nTime: {{ data.state.time_label }}\n\nState summary:\n{{ data.state.state }}\n\n## Location\n\n{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}\n\n{{ data.current_location.description }}\n\n## User input\n\n{{ data.user_input or \"No explicit user input.\" }}\n\n## Last narration\n\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Recent history\n\n{{ data.recent_history_summary or \"No recent history summary.\" }}\n\n## Long-term history\n\n{{ data.long_term_history_summary or \"No long-term history summary.\" }}\n\n## Present characters visible to the player\n\n{% for c in data.characters %}\n- Character {{ c.id }}: {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Public state: {{ c.public_state }}\n  Location: {{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\n## Resolved visible events\n\nThese are authoritative.\nNarrate these outcomes only.\nDo not replace them with attempted action text.\n\n{% for event in data.narrator_resolution_view.resolved_visible_events %}\n- Actor {{ event.actor_id }}: {{ event.actor_name }}\n  Final status: {{ event.final_status }}\n  Resolved order: {{ event.resolved_order }}\n  Visible result: {{ event.visible_result }}\n  Failure reason, if visibly relevant: {{ event.failure_reason or \"None.\" }}\n  Blocking actor ID: {{ event.blocking_actor_id }}\n  Blocking entity ID: {{ event.blocking_entity_id }}\n{% else %}\nNo resolved visible events.\n{% endfor %}\n\n## Safe narrator context\n\nThese are safe visible context notes from the resolver.\nUse only if helpful.\nDo not treat them as extra actions.\n\n{% for context in data.narrator_resolution_view.safe_narrator_context %}\n- {{ context }}\n{% else %}\nNone.\n{% endfor %}\n\n## Scene result summary\n\n{{ data.narrator_resolution_view.scene_result_summary or \"No scene result summary.\" }}\n\n## Narrator-visible world entries\n\nUse these only according to narration permission.\n\n{% for e in data.world_entries_for_narrator %}\n- Entry {{ e.id }}\n  Content: {{ e.content }}\n  Permission: {{ e.narration_permission }}\n  Visibility: {{ e.visibility }}\n  Confidence: {{ e.confidence }}\n{% else %}\nNone.\n{% endfor %}\n\n## Pending generated proposals\n\nThese are not canonical unless the resolved visible events explicitly accepted or revealed them.\nDo not narrate them as real otherwise.\n\n{% for p in data.pending_generated_proposals %}\n- {{ p }}\n{% else %}\nNone.\n{% endfor %}\n\n# Required narration\n\nWrite the narration for this resolved turn.\n\nImportant:\n- Output natural language only.\n- Narrate from the player character's perspective.\n- Use resolved visible events as the source of truth.\n- Do not narrate private motives, private resolver results, database changes, or internal notes.\n- Do not add new actions, new dialogue, new object states, or new discoveries.\n- Use MAY_HINT entries only as indirect atmospheric or behavioural hints; do not state their hidden fact directly.\n- End with a natural opening for the player to respond.\n"
                        }
                    ],
                    "narrate_user_input_failure_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the narrator for an interactive role-play simulation.\n\nThis narration is for an early user-input validation failure.\n\nThe user's attempted action was not accepted as stated.\nYour job is to narrate the failed or blocked attempt in-world, while preserving player agency.\n\nDo not punish the player harshly unless the resolver output says so.\nDo not invent major consequences.\nDo not make the action succeed.\nDo not reveal hidden facts.\nDo not output JSON.\nDo not mention validation, resolver, legality checks, or system rules.\n\nNarration rules:\n- Show the player character attempting or reconsidering the action.\n- Explain the immediate in-world obstacle.\n- Keep the tone immersive.\n- End with the player still able to choose another action.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# User Input Failure Narration\n\n## Simulation\n{{ data.simulation.name }}\n{{ data.simulation.description }}\n\n## Current state\nTime: {{ data.state.time_label }}\nState summary:\n{{ data.state.state }}\n\n## Location\n{{ data.current_location.primary_location }} / {{ data.current_location.detailed_location }} / {{ data.current_location.scene }}\n\n{{ data.current_location.description }}\n\n## Player character\n{{ data.player_character.name }}\nPublic state: {{ data.player_character.public_state }}\n\n## User attempted input\n{{ data.user_input }}\n\n## Resolver validation output\n{{ data.resolver_output }}\n\n## Last narration\n{{ data.last_narration or \"No previous narration.\" }}\n\n## Recent history\n{{ data.recent_history_summary or \"No recent history summary.\" }}\n\n## Long-term history\n{{ data.long_term_history_summary or \"No long-term history summary.\" }}\n\n## Narrator-visible world entries\n{% for e in data.world_entries_for_narrator %}\n- {{ e.content }}\n  Permission: {{ e.narration_permission }}\n  Visibility: {{ e.visibility }}\n{% else %}\nNone.\n{% endfor %}\n\n# Required narration\n\nNarrate the failed or blocked attempt naturally.\n\nOutput natural language only.\n"
                        }
                    ],
                    "narrate_wait_for_user_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are the narrator for an interactive role-play simulation.\n\nThis mode is used when the scene should pause for player input.\n\nYour job:\n- briefly restate the immediate user-facing situation;\n- make clear that the next meaningful choice belongs to the player character;\n- gently nudge the user to provide an action, answer, question, or decision;\n- do not progress NPC actions;\n- do not resolve new events;\n- do not reveal hidden facts;\n- do not invent new facts.\n\nThis is a pause narration, not a normal scene continuation.\n\nHard rules:\n- Do not make any NPC take a new action.\n- Do not make any NPC answer a question unless that answer was already in last narration.\n- Do not add new discoveries, clues, arrivals, interruptions, threats, or environmental changes.\n- Do not decide what the player character thinks, feels, says, or does.\n- Do not mention Director, scheduler, agents, branches, system stages, or waiting flags.\n- Do not output JSON.\n\nStyle:\n- Keep it short: usually 1 short paragraph.\n- Use natural prose.\n- Focus on the immediate social or physical pressure.\n- The final sentence should naturally invite player input.\n- Prefer an in-world nudge over a UI-like instruction.\n\nGood final-sentence patterns:\n- \"Arthur has a moment to decide how directly he wants to press her.\"\n- \"The choice of what to ask next is his.\"\n- \"For now, the room seems to wait on Arthur's next move.\"\n\nBad final-sentence patterns:\n- \"Please provide more input.\"\n- \"The system is waiting for the user.\"\n- \"What would you like to do?\" unless the narration style is intentionally direct.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Wait-for-user narration input\n\n## Simulation\n\n{{ data.context.simulation_name }}\n\n{{ data.context.simulation_description or \"\" }}\n\n## Current scene\n\nTime:\n{{ data.context.time_label or \"Unknown.\" }}\n\nLocation:\n{{ data.context.location_label }}\n\nLocation description:\n{{ data.context.location_description or \"No location description.\" }}\n\nCurrent scene state:\n{{ data.context.scene_state or \"No current state summary.\" }}\n\n## Memory\n\nShort-term memory:\n{{ data.context.short_term_memory or data.context.recent_history_summary or \"No short-term memory.\" }}\n\nLong-term memory:\n{{ data.context.long_term_memory or data.context.long_term_history_summary or \"No long-term memory.\" }}\n\n## Last narration\n\n{{ data.context.last_narration or \"No previous narration.\" }}\n\n## Latest user input\n\n{{ data.context.user_input or \"No explicit user input.\" }}\n\n## Why the scene is pausing\n\nScene focus:\n{{ data.context.scene_focus or \"No scene focus.\" }}\n\nReason to wait:\n{{ data.context.reason_to_wait or \"The player character needs to choose the next action.\" }}\n\n## Present characters\n\n{% for c in data.context.present_characters %}\n- {{ c.name }}\n  User controlled: {{ c.user_controlled }}\n  Public state: {{ c.public_state }}\n{% else %}\nNone.\n{% endfor %}\n\n## Narrator-visible recalled facts\n\n{% for e in data.context.visible_world_entries %}\n- {{ e.content }}\n  Visibility: {{ e.visibility }}\n  Narration permission: {{ e.narration_permission }}\n{% else %}\nNone.\n{% endfor %}\n\n# Required narration\n\nWrite a short pause narration.\n\nIt should:\n- restate the immediate situation;\n- avoid progressing time or NPC actions;\n- naturally invite the player character's next move.\n\nOutput natural language only.\n"
                        }
                    ]
                },
                "world_generator": {
                    "backend_configuration": {
                        "connection": 1,
                        "model": "huihui_ai/qwen3.5-abliterated:122b",
                        "temperature": 0.4,
                        "context_window": 65536,
                        "seed": None,
                        "reasoning": None,
                        "stop_tokens": None,
                        "mirostat": None,
                        "mirostat_eta": None,
                        "mirostat_tau": None,
                        "num_predict": None,
                        "repeat_penalty_window": None,
                        "repeat_penalty": None
                    },
                    "remove_empty_messages": True,
                    "merge_adjacent_user": True,
                    "merge_adjacent_assistant": False,
                    "merge_assistant_with_tool_calls": False,
                    "system_message_policy": "merge_to_top",
                    "message_merge_separator": "\n\n",
                    "max_tool_rounds": 3,
                    "location_generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are a location generation tool for a role-play simulation.\n\nGenerate exactly one ProposedLocation.\n\nOutput schema:\n- temp_id: temporary string ID for this proposal, for example \"loc_temp_iron_stag_cellar\". Do not use a database ID.\n- primary_location: broad area or parent place.\n- detailed_location: specific named place inside the parent area.\n- scene: concise scene label used for the current playable area.\n- description: objective, playable description of what characters can perceive and interact with.\n- attributes: mapping of attribute names to lists of string values. Use {} unless constraints require attributes.\n- stats: mapping of stat names to numeric values. Use {} unless constraints require stats.\n- entities: 0-3 ProposedEntity objects already present in this location.\n- reason: why this proposal is useful and how it satisfies the trigger.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nHard rules:\n- The location is a pending proposal, not canonical.\n- Do not reuse an existing location.\n- Do not contradict existing locations or state summary.\n- Do not solve major mysteries.\n- Do not reveal final answers unless explicitly required.\n- Use temporary IDs only for the location and generated entities.\n- If adding entities inside the location, their type must match an existing setting entity type when possible.\n- Keep the location useful for interaction, not just description.\n- The location must fit the setting, era, tone, and current scene.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n\nLocation quality rules:\n- Provide a concrete playable scene.\n- Include sensory details only when they imply interaction or atmosphere.\n- Include 0-3 proposed entities maximum.\n- Entities should be clues, obstacles, containers, mechanisms, traces, or interactable fixtures.\n- Entity description and status must only contain objective observable/mechanical/physical state.\n  Do not include inferred facts, hidden contents, clue interpretation, private knowledge, or deductions.\n  They needed to be added to world entry, which is not in scope of this generation\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate Location\n\n## Goal\n\nYour goal is:\n{{ data.goal }}\n\nThis is only a guidance. You do not have to generate exactly the same content as it describes, as long as the\ngoal aligns. However, your proposed location must match the world style and is sensible.\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number  }}\nTime: {{ data.generation_context.time_label }}\nState summary:\n{{ data.generation_context.state_summary }}\n\nData preset constraints:\n- Entity types:\n{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}\n  - {{ type_name }}: {{ description }}\n{% else %}\n  - No custom entity types configured.\n{% endfor %}\n- Character attributes:\n{% for attr in data.generation_context.data_preset.character_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Character stats:\n{% for stat in data.generation_context.data_preset.character_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction attributes:\n{% for attr in data.generation_context.data_preset.faction_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction stats:\n{% for stat in data.generation_context.data_preset.faction_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting locations:\n{% for l in data.generation_context.existing_locations %}\n- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting entities in current location:\n{% for e in data.generation_context.existing_entities %}\n- {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\nRelevant factions and relationships:\n{% for f in data.generation_context.factions %}\n- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.generation_context.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% endfor %}\n\nGenerate exactly one ProposedLocation.\n    "
                        }
                    ],
                    "item_generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are an item generation tool for a role-play simulation.\n\nGenerate exactly one ProposedItem.\n\nOutput schema:\n- temp_id: temporary string ID for this proposal, for example \"item_temp_torn_receipt\". Do not use a database ID.\n- name: short item name.\n- description: what the item is and what can be noticed about it. Do not narrate discovery.\n- quality: optional condition label such as \"worn\", \"torn\", \"polished\", or None.\n- quantity: integer count. Use 1 for unique or clue items.\n- unique: true for named clues/evidence, false only for ordinary stackable objects.\n- proposed_owner_id: existing character ID if the item clearly belongs in a character inventory; otherwise None.\n- proposed_location_id: existing location ID if the item clearly belongs in a known location; otherwise None.\n- reason: why this item is useful and how it satisfies the trigger.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nHard rules:\n- The item is a pending proposal, not canonical.\n- Do not duplicate existing items.\n- Do not solve major mysteries.\n- Do not create a final-answer clue unless explicitly required.\n- The item must fit the setting, era, tone, and trigger.\n- Use temp_id only.\n- proposed_owner_id must be None unless the item is clearly generated for one of the present character IDs.\n- proposed_location_id must be None or one of the existing location IDs.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n\nItem quality rules:\n- Prefer partial, ambiguous, actionable clues.\n- A clue item should point to a lead, contradiction, location, person, or question.\n- Avoid overly symbolic or genre-breaking objects unless the simulation tone supports them.\n- description should say what the item is, not narrate its discovery.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate Item\n\n## Goal\n\nYour goal is:\n{{ data.goal }}\n\nThis is only a guidance. You do not have to generate exactly the same content as it describes, as long as the\ngoal aligns. However, your proposed item must match the world style and is sensible.\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number  }}\nTime: {{ data.generation_context.time_label }}\nState summary:\n{{ data.generation_context.state_summary }}\n\nData preset constraints:\n- Entity types:\n{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}\n  - {{ type_name }}: {{ description }}\n{% else %}\n  - No custom entity types configured.\n{% endfor %}\n- Character attributes:\n{% for attr in data.generation_context.data_preset.character_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Character stats:\n{% for stat in data.generation_context.data_preset.character_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction attributes:\n{% for attr in data.generation_context.data_preset.faction_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction stats:\n{% for stat in data.generation_context.data_preset.faction_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting locations:\n{% for l in data.generation_context.existing_locations %}\n- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | quality={{ i.quality }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | quality={{ e.quality }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\nRelevant factions and relationships:\n{% for f in data.generation_context.factions %}\n- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.generation_context.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% endfor %}\n\nGenerate exactly one ProposedItem.\n"
                        }
                    ],
                    "equipment_generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are an equipment generation tool for a role-play simulation.\n\nGenerate exactly one ProposedEquipment.\n\nOutput schema:\n- temp_id: temporary string ID for this proposal, for example \"equip_temp_storm_lantern\". Do not use a database ID.\n- name: short equipment name.\n- description: what the equipment is and what can be observed about it.\n- status: current usable/equipped/damaged/stored condition.\n- quality: optional condition label such as \"worn\", \"damaged\", \"polished\", or None.\n- proposed_owner_id: existing character ID if the equipment clearly belongs to a present character; otherwise None.\n- proposed_location_id: existing location ID if the equipment clearly belongs in a known location; otherwise None.\n- reason: why this equipment is useful and how it satisfies the trigger.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nHard rules:\n- The equipment is a pending proposal, not canonical.\n- Do not duplicate existing equipment.\n- Do not generate portable clue documents as equipment; use generate_item instead.\n- Do not generate fixed environmental fixtures as equipment; use generate_entity instead.\n- Do not solve major mysteries.\n- Do not create final-answer evidence unless explicitly required.\n- Use temp_id only.\n- proposed_owner_id must be None unless clearly generated for one of the present character IDs.\n- proposed_location_id must be None or one of the existing location IDs.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n\nEquipment quality rules:\n- Equipment should be repeatedly usable or have meaningful state/status.\n- Description and status must not include hidden deductions, inferred facts, or private knowledge.\n- If hidden meaning is needed, create a linked world entry using generate_generation_package instead.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate Equipment\n\n## Goal\n{{ data.goal }}\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number  }}\nTime: {{ data.generation_context.time_label }}\n\nState summary:\n{{ data.generation_context.state_summary }}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting locations:\n{% for l in data.generation_context.existing_locations %}\n- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | quality={{ e.quality }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% else %}\nNone.\n{% endfor %}\n\nGenerate exactly one ProposedEquipment.\n"
                        }
                    ],
                    "entity_generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are an entity generation tool for a role-play simulation.\n\nGenerate exactly one ProposedEntity.\n\nOutput schema:\n- temp_id: temporary string ID for this proposal, for example \"entity_temp_locked_cabinet\". Do not use a database ID.\n- name: short entity name.\n- type: exactly one supported entity type from the simulation data preset.\n- description: objective details visible or discoverable by interaction.\n- status: current state, access, damage, concealment, or other condition.\n- interactions: concrete verbs or short phrases characters can attempt.\n- reason: why this entity is useful and how it satisfies the trigger.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nHard rules:\n- The entity is a pending proposal, not canonical.\n- The entity must belong to or be discoverable within the current location unless constraints specify another location.\n- Do not duplicate existing entities.\n- type must be exactly one supported entity type from the simulation data preset.\n- Do not invent unsupported entity types.\n- Do not solve major mysteries.\n- Do not create portable inventory items as entities unless they remain scene-anchored containers or fixtures.\n- Use temp_id only.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n- Entity description and status must only contain objective observable/mechanical/physical state.\n  Do not include inferred facts, hidden contents, clue interpretation, private knowledge, or deductions.\n  They are encoded in world entries, which is out of scope of this generation.\n\nEntity quality rules:\n- The entity must support meaningful interactions.\n- interactions must be concrete verbs or short phrases.\n- status must describe its current discoverable condition.\n- description should be objective and playable, not narrated prose.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate Entity\n\n## Goal\n\nYour goal is:\n{{ data.goal }}\n\nThis is only a guidance. You do not have to generate exactly the same content as it describes, as long as the\ngoal aligns. However, your proposed location must match the world style and is sensible.\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number  }}\nTime: {{ data.generation_context.time_label }}\nState summary:\n{{ data.generation_context.state_summary }}\n\nData preset constraints:\n- Entity types:\n{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}\n  - {{ type_name }}: {{ description }}\n{% else %}\n  - No custom entity types configured.\n{% endfor %}\n- Character attributes:\n{% for attr in data.generation_context.data_preset.character_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Character stats:\n{% for stat in data.generation_context.data_preset.character_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction attributes:\n{% for attr in data.generation_context.data_preset.faction_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction stats:\n{% for stat in data.generation_context.data_preset.faction_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting entities in current location:\n{% for e in data.generation_context.existing_entities %}\n- {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\nRelevant factions and relationships:\n{% for f in data.generation_context.factions %}\n- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.generation_context.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% endfor %}\n\nGenerate exactly one ProposedEntity.\n"
                        }
                    ],
                    "world_entry_generation_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are a world-entry generation tool for a role-play simulation.\n\nGenerate exactly one ProposedWorldEntry.\n\nOutput schema:\n- temp_id: temporary string ID for this proposal, for example \"entry_temp_clara_suspicion\". Do not use a database ID.\n- scope: list of IDs that can know this entry. Use [0] for public/common knowledge, [-1] for hidden GM-only, or character IDs from present characters.\n- content: one complete factual sentence. It may describe a belief or rumour, but make uncertainty explicit.\n- visibility: one of \"known\", \"suspected\", \"perceived\", or \"inferred\".\n- confidence: 0.0-1.0. Use less than 1.0 for rumours, suspicions, guesses, and unreliable testimony.\n- narration_permission: one of \"visible\", \"may_hint\", or \"invisible\".\n- recall_type: one of \"always\", \"keyword\", \"semantic\", or \"chained\".\n- keywords: for keyword recall, provide useful keyword dicts; otherwise None.\n- chained_ids: for chained recall, provide existing world entry IDs; otherwise None.\n- semantic_instruction: for semantic recall, describe when this entry should be recalled; otherwise None.\n- reason: why this persistent knowledge is needed.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nHard rules:\n- The world entry is a pending proposal, not canonical.\n- content must be a complete factual sentence, not a title.\n- Do not duplicate existing world entries.\n- Do not contradict canonical state.\n- Do not solve major mysteries unless explicitly required.\n- scope may contain only present character IDs, 0 for everyone, or -1 for hidden GM-only.\n- If recall_type is KEYWORD, include useful keywords.\n- If recall_type is CHAINED, include chained_ids only if known from supplied context; otherwise use SEMANTIC.\n- If recall_type is SEMANTIC, include semantic_instruction.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n\nWorld-entry quality rules:\n- Use confidence below 1.0 for rumours, suspicions, guesses, or unreliable testimony.\n- Use scoped character knowledge when only some characters know it.\n- Use scope [0] only for public/common knowledge.\n- Use scope [-1] only for hidden GM-side truth.\n- Do not create a world entry for “someone noticed a person standing there” unless it must persist as memory.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate World Entry\n\n## Goal\n\nYour goal is:\n{{ data.goal }}\n\nThis is only a guidance. You do not have to generate exactly the same content as it describes, as long as the\ngoal aligns. However, your proposed location must match the world style and is sensible.\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number }}\nTime: {{ data.generation_context.time_label }}\nState summary:\n{{ data.generation_context.state_summary }}\n\nData preset constraints:\n- Entity types:\n{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}\n  - {{ type_name }}: {{ description }}\n{% else %}\n  - No custom entity types configured.\n{% endfor %}\n- Character attributes:\n{% for attr in data.generation_context.data_preset.character_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Character stats:\n{% for stat in data.generation_context.data_preset.character_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction attributes:\n{% for attr in data.generation_context.data_preset.faction_attributes %}\n  - {{ attr.name }} | universal={{ attr.universal }} | values={{ attr.values or \"open\" }} | creation={{ attr.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n- Faction stats:\n{% for stat in data.generation_context.data_preset.faction_stats %}\n  - {{ stat.name }} | universal={{ stat.universal }} | creation={{ stat.creation_instruction }}\n{% else %}\n  - None.\n{% endfor %}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\nRelevant factions and relationships:\n{% for f in data.generation_context.factions %}\n- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.generation_context.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% endfor %}\n\nGenerate exactly one ProposedWorldEntry.\n"
                        }
                    ],
                    "generation_package_prompt": [
                        {
                            "role": "system",
                            "content": "\nYou are a linked world-generation package tool for a role-play simulation.\n\nGenerate exactly one ProposedGenerationPackage.\n\nUse this tool when generated content is interdependent and must share temporary IDs:\n- a location with entities inside it;\n- an entity with hidden or scoped world-entry facts;\n- a container with possible item contents;\n- an item or equipment with associated knowledge;\n- a clue that requires both a physical object and scoped memory/world entries.\n\nOutput schema:\n- temp_id: temporary package ID, for example \"pkg_temp_room_7_cache\".\n- title: short package title.\n- package_type: one of \"linked_discovery\", \"location_with_contents\", \"entity_with_clues\", \"item_with_knowledge\", \"equipment_with_knowledge\", or \"mixed\".\n- summary: concise summary of the package.\n- locations: list of ProposedLocation objects.\n- entities: list of ProposedEntity objects.\n- items: list of ProposedItem objects.\n- equipments: list of ProposedEquipment objects.\n- world_entries: list of ProposedWorldEntry objects.\n- links: list of ProposedLink objects.\n- reason: why this package is useful and how it satisfies the trigger.\n- commit_policy: \"resolver_decides\" unless a constraint explicitly says otherwise.\n\nTemporary ID rules:\n- Every generated object must have a temp_id.\n- Use readable temporary IDs such as \"entity_temp_locked_trunk\" or \"entry_temp_trunk_latent_clue\".\n- If one generated object refers to another generated object, use that object's temp_id exactly.\n- Do not use database IDs for generated objects.\n- Existing canonical objects may be referred to by their existing integer IDs only where the schema expects canonical IDs.\n- The application will namespace temporary IDs after generation; your internal references must still be consistent.\n\nEntity rules:\n- Entity description and status must contain only objective, observable, mechanical, or physical state.\n- Do not put inferred facts, hidden contents, clue interpretation, ownership deductions, or private knowledge into entity description/status.\n- Put hidden facts, inferred facts, private knowledge, rumours, beliefs, or latent clue meaning into world_entries instead.\n\nItem and equipment rules:\n- Item description must describe the object, not narrate discovery or guarantee interpretation.\n- Equipment is for worn, carried, installed, or repeatedly usable gear.\n- Items are for portable objects, documents, clues, tokens, receipts, fragments, and consumables.\n\nWorld-entry rules:\n- World entries hold persistent knowledge, hidden facts, deductions, rumours, beliefs, memories, and clue meanings.\n- scope must use [0] for public/common knowledge, [-1] for GM-only hidden facts, or present character IDs.\n- Use confidence below 1.0 for rumours, suspicions, guesses, or unreliable testimony.\n- If recall_type is \"keyword\", include useful keywords.\n- If recall_type is \"semantic\", include semantic_instruction.\n- If recall_type is \"chained\", chained_ids may refer only to existing canonical entry IDs supplied in context, not generated temp IDs.\n- Use links to connect generated entries to generated objects.\n\nPackage quality rules:\n- Keep the package minimal. Generate only what is needed now.\n- Do not solve major mysteries unless explicitly required.\n- Prefer partial, ambiguous, actionable clues.\n- Do not duplicate existing locations, entities, items, equipment, or world entries.\n- Do not decide whether the triggering action succeeds.\n- Include commit_policy=\"resolver_decides\" unless constraints specify otherwise.\n"
                        },
                        {
                            "role": "user",
                            "content": "\n# Generate Linked Package\n\n## Goal\n{{ data.goal }}\n\n## Canonical generation context\nSimulation: {{ data.generation_context.simulation_name }}\nDescription:\n{{ data.generation_context.simulation_description }}\n\nRound: {{ data.generation_context.turn_number }}\nTime: {{ data.generation_context.time_label }}\n\nState summary:\n{{ data.generation_context.state_summary }}\n\nData preset constraints:\n- Entity types:\n{% for type_name, description in data.generation_context.data_preset.entity_types.items() %}\n  - {{ type_name }}: {{ description }}\n{% else %}\n  - No custom entity types configured.\n{% endfor %}\n\nCurrent location:\n{{ data.generation_context.current_location }}\n\nPresent characters:\n{% for c in data.generation_context.present_characters %}\n- {{ c.id }}: {{ c.name }} | public_state={{ c.public_state }} | location={{ c.location }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting locations:\n{% for l in data.generation_context.existing_locations %}\n- {{ l.id }}: {{ l.primary_location }} / {{ l.detailed_location }} / {{ l.scene }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting entities in current location:\n{% for e in data.generation_context.existing_entities %}\n- {{ e.id }}: {{ e.name }} | type={{ e.type }} | status={{ e.status }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting items:\n{% for i in data.generation_context.existing_items %}\n- {{ i.id }}: {{ i.name }} | description={{ i.description }}\n{% else %}\nNone.\n{% endfor %}\n\nExisting equipment:\n{% for e in data.generation_context.existing_equipments %}\n- {{ e.id }}: {{ e.name }} | status={{ e.status }} | description={{ e.description }}\n{% else %}\nNone.\n{% endfor %}\n\nRelevant factions and relationships:\n{% for f in data.generation_context.factions %}\n- Faction {{ f.id }}: {{ f.name }} | {{ f.description }}\n{% else %}\nNo relevant factions.\n{% endfor %}\n{% for r in data.generation_context.faction_relationships %}\n- Relationship: {{ r.from_type }} {{ r.from_id }} -> {{ r.to_type }} {{ r.to_id }}\n  Type: {{ r.relationship }}\n  Private: {{ r.private }}\n{% else %}\nNo relevant faction relationships.\n{% endfor %}\n\n## Trigger\n{{ data.trigger }}\n\n## Constraints\n{% for c in data.constraints %}\n- {{ c }}\n{% else %}\nNone.\n{% endfor %}\n\nGenerate exactly one ProposedGenerationPackage.\n\nUse the package only for linked content. If only one independent object is required, this tool should not have been called; still produce the smallest valid package.\n"
                        }
                    ]
                }
            },
            "data_preset": {
                "character_attributes": [
                    {
                        "name": "relationship",
                        "values": None,
                        "creation_instruction": "",
                        "update_instruction": "",
                        "universal": True
                    }
                ],
                "character_stats": [],
                "faction_attributes": [],
                "faction_stats": [],
                "entity_types": {
                    "important-item": "An important item that is relevant to the story, and can be interacted with. It should remain relevant after multiple rounds, and may be acquired or used by characters."
                }
            },
            "embedding_profile": {
                "connection": 1,
                "model": "qwen3-embedding:4b",
                "dimensions": 1024,
                "context_window": 8192
            },
            "language": "en",
            "act_for_user": False,
            "enable_tts": False,
            "enable_image_generation": False
        },
        "state": {
            "id": 1,
            "scene": 3,
            "turn_number": 0,
            "state": "Arthur Moore has arrived at the Iron Stag Inn during the Founder's Festival. Clara Whitlock is behind the bar, managing guests while quietly observing Arthur. The inn is busy with locals and festival visitors, making it a useful place to gather rumours without drawing immediate attention. Arthur has not yet revealed the full contents of the anonymous letter. Eleanor Graves is aware that an outside investigator has arrived in town, but has not yet confronted him directly. Marcus Reed remains at or near the observatory, anxious about Harlan's missing notebook and the unauthorized signal experiments.",
            "time_label": "Founder's Festival evening, three weeks after Director Harlan's disappearance",
            "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter.",
            "long_term_history_summary": "Director Harlan disappeared three weeks ago. Officially he left without notice, but many residents doubt this. The observatory, the old mine, altered property records, the unknown visitor, and Harlan's missing notebook are all unresolved investigation threads."
        },
        "connection_profiles": {
            "director": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "memory": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "character": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "resolver": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "committer": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "narrator": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "world_generator": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            },
            "embedding": {
                "provider": "ollama",
                "name": "Mock Connection",
                "base_url": "http://100.86.189.45:11434",
                "api_key": None,
                "id": 1
            }
        },
        "director_output": {
            "scene_focus": "Arthur questions Clara regarding Room 7 occupancy at the Iron Stag Inn bar.",
            "activations": [
                {
                    "character_id": 3,
                    "character_name": "Clara Whitlock",
                    "activate": True,
                    "priority": 85,
                    "reason": "Directly addressed by player input; holds the relevant ledger records; private task aligns with the specific question asked about Room 7.",
                    "private_motive_used": True,
                    "activation_sources": {
                        "public_state": True,
                        "private_state": False,
                        "public_task": False,
                        "private_task": True,
                        "scene_opportunity": True,
                        "user_input": True
                    }
                },
                {
                    "character_id": 1,
                    "character_name": "Eleanor Graves",
                    "activate": False,
                    "priority": 0,
                    "reason": "Present at the scene but not directly addressed; observing passively without immediate need to intervene or speak this turn.",
                    "private_motive_used": False,
                    "activation_sources": {
                        "public_state": True,
                        "private_state": False,
                        "public_task": False,
                        "private_task": False,
                        "scene_opportunity": False,
                        "user_input": False
                    }
                }
            ],
            "wait_for_user": False,
            "reason_to_wait": None,
            "director_notes": "Clara is prioritized to respond to the direct query about Room 7. Her private task (Task 12) regarding the unknown visitor in Room 7 drives her interest in providing an accurate answer. Eleanor remains passive for this turn to allow the information exchange between Arthur and Clara to resolve without premature interruption, though she will likely react in a subsequent turn based on Clara's response."
        },
        "generated_proposals": [],
        "briefing_output": {
            "briefings": [
                {
                    "character_id": 3,
                    "character_name": "Clara Whitlock",
                    "scene_context": "Iron Stag Inn bar during Founder's Festival evening. The room is warm, noisy, and crowded with locals and visitors.",
                    "recent_context": "Arthur Moore arrived at the inn earlier; Eleanor Graves greeted him publicly. Arthur has not yet revealed an anonymous letter. Clara observed his controlled manner upon arrival.",
                    "known_relevant_facts": "Blackwater Ridge is isolated around Blackwater Observatory (Entry 1). It is 1912, Founder's Festival time (Entry 2). Director Harlan vanished three weeks ago; officially he left without notice (Entry 3). The inn ledger records room usage and payments.",
                    "immediate_situation": "Arthur Moore stands at the bar asking whether Room 7 was occupied before Director Harlan vanished. The busy environment allows for discreet listening.",
                    "instruction": "Respond to Arthur's inquiry regarding Room 7 occupancy while maintaining the role of innkeeper amidst festival activity.",
                    "available_interactions": [
                        "Consult Visitor's Room Ledger (Entity 5) to check Room 7 history",
                        "Observe Arthur Moore's reaction and demeanor",
                        "Listen to nearby guest conversations for rumours",
                        "Inspect Notice Board (Entity 6) for festival or missing notices"
                    ],
                    "relevant_task_ids": [],
                    "relevant_world_entry_ids": [
                        1,
                        2,
                        3
                    ],
                    "constraints": [
                        "Maintain public innkeeper persona",
                        "Avoid drawing undue attention while gathering information",
                        "Keep interactions subtle within the noisy bar environment"
                    ]
                }
            ],
            "notes": ""
        },
        "character_action_outputs": [
            {
                "character_id": 3,
                "character_name": "Clara Whitlock",
                "intent": "Verify Room 7 occupancy records from the official ledger before answering Arthur's inquiry.",
                "action_type": "manipulate_entity",
                "target_character_ids": [],
                "target_entity_ids": [],
                "target_location_id": None,
                "target_item_ids": [],
                "method": "Reaches behind the bar to retrieve and open the Visitor's Room Ledger, scanning the entries near the date of Harlan's disappearance while maintaining eye contact with Arthur.",
                "visible_behavior": "Clara offers a polite, professional smile, turns slightly toward the shelf behind her, retrieves a large bound book, and flips through pages with practiced efficiency. She pauses on a specific page before looking back up at Arthur.",
                "spoken_intent": None,
                "urgency": 40,
                "persistence": 60,
                "expected_outcome": "Locate the specific entry for Room 7 around the relevant dates to confirm what is publicly recorded versus her private notes.",
                "fallback_if_blocked": "If the ledger is temporarily unavailable or Arthur interrupts, she will rely on memory and offer a general confirmation that records are kept securely.",
                "uses_private_knowledge": True,
                "private_reason_for_system": "Task 12 (Identify unknown visitor) motivates checking the public record specifically for Room 7 to compare against her private receipt (Item 10) before revealing information to Arthur.",
                "constraints_for_resolver": [
                    "The ledger is located on a shelf behind the bar within Clara's reach",
                    "Arthur is standing at the counter waiting for an answer",
                    "The room is noisy enough that nearby guests might not hear specific details if she speaks quietly"
                ],
                "notes": ""
            }
        ],
        "character_reaction_outputs": [],
        "resolver_output": {
            "accepted": True,
            "rejection_reason": None,
            "resolved_actions": [
                {
                    "actor_id": 3,
                    "actor_name": "Clara Whitlock",
                    "original_intent": "Verify Room 7 occupancy records from the official ledger before answering Arthur's inquiry.",
                    "final_status": "succeeded",
                    "resolved_order": None,
                    "visible_result": "Clara offers a polite smile and turns slightly toward the shelf behind the bar. She retrieves a large bound Visitor's Room Ledger, flips through pages with practiced efficiency while maintaining eye contact with Arthur, pauses on a specific entry near the date of Director Harlan's disappearance, then closes the ledger and looks back up at him.",
                    "private_result_for_actor": None,
                    "failure_reason": None,
                    "blocking_actor_id": None,
                    "blocking_entity_id": None,
                    "state_change_hints": [
                        "Clara has accessed and reviewed Room 7 occupancy records in the Visitor's Room Ledger for dates around three weeks ago (Harlan's disappearance timeframe)",
                        "The Visitor's Room Ledger remains behind the bar, now open to a specific page before being closed"
                    ],
                    "world_entry_hints": [
                        "Clara can now compare the official ledger entry for Room 7 against her private receipt (Item 10: Room 7 Cash Receipt) regarding occupancy during Harlan's disappearance timeframe",
                        "The public record in the ledger may differ from or match Clara's private records"
                    ],
                    "requires_actor_retry": False,
                    "retry_instruction": None
                }
            ],
            "conflicts": [],
            "failed_characters": [],
            "scene_result_summary": "Clara successfully verified Room 7 occupancy records from the official ledger before responding to Arthur. The action completed without interference in the noisy bar environment.",
            "next_round_note": "Arthur's response or next action pending; Clara now has information to answer his inquiry about Room 7.",
            "narrator_context": [],
            "state_update_suggestions": [],
            "pending_world_entry_suggestions": [],
            "requires_director_rerun": False,
            "director_rerun_reason": None,
            "notes": ""
        },
        "committer_output": {
            "simulation_id": 1,
            "ready_to_commit": True,
            "round_summary": "Clara successfully verified Room 7 occupancy records from the official ledger before responding to Arthur. The action completed without interference in the noisy bar environment.",
            "mutation_log": [
                {
                    "mutation_id": "4c241b91-9f92-44d0-995a-00dc7ab1bc0f",
                    "operation": "update",
                    "target": {
                        "object_type": "state",
                        "object_id": 1
                    },
                    "payload": {
                        "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; she verified records from the Visitor's Room Ledger."
                    },
                    "reason": "Reflect resolved turn in narrative history",
                    "source_event": None
                },
                {
                    "mutation_id": "f30af8f1-850f-4aa1-8890-9e5211df865b",
                    "operation": "update",
                    "target": {
                        "object_type": "task",
                        "object_id": 12
                    },
                    "payload": {
                        "progress": 40
                    },
                    "reason": "Clara gained useful information by checking the ledger, advancing her investigation into the unknown visitor",
                    "source_event": None
                }
            ],
            "warnings": [],
            "final_state": {
                "simulation": {
                    "id": 1,
                    "name": "The Blackwater Observatory",
                    "description": "The year is 1912. The isolated mountain town of Blackwater Ridge was built around an astronomical observatory that once conducted secret government-funded research.\n\nThree weeks ago, the observatory's director vanished. Officially, he left without notice. However, nobody believes that. The player arrives in town during the annual Founder's Festival, where tensions between residents are beginning to surface.",
                    "language": "en"
                },
                "state": {
                    "id": 1,
                    "scene": 3,
                    "turn_number": 0,
                    "state": "Arthur Moore has arrived at the Iron Stag Inn during the Founder's Festival. Clara Whitlock is behind the bar, managing guests while quietly observing Arthur. The inn is busy with locals and festival visitors, making it a useful place to gather rumours without drawing immediate attention. Arthur has not yet revealed the full contents of the anonymous letter. Eleanor Graves is aware that an outside investigator has arrived in town, but has not yet confronted him directly. Marcus Reed remains at or near the observatory, anxious about Harlan's missing notebook and the unauthorized signal experiments.",
                    "time_label": "Founder's Festival evening, three weeks after Director Harlan's disappearance",
                    "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; she verified records from the Visitor's Room Ledger.",
                    "long_term_history_summary": "Director Harlan disappeared three weeks ago. Officially he left without notice, but many residents doubt this. The observatory, the old mine, altered property records, the unknown visitor, and Harlan's missing notebook are all unresolved investigation threads."
                },
                "characters": [
                    {
                        "id": 1,
                        "name": "Eleanor Graves",
                        "user_controlled": False,
                        "location": 3,
                        "public_state": "Welcoming Arthur Moore to Blackwater Ridge while presenting the town as orderly, festive, and untroubled by Director Harlan's disappearance.",
                        "private_state": "Trying to determine what Arthur Moore is actually here for, whether he was truly hired as an independent investigator, and whether his presence threatens the altered property records, the town's finances, or her own position.",
                        "attributes": {
                            "relationship": [
                                "Marcus Reed:distrust",
                                "Clara Whitlock:wary respect",
                                "Arthur Moore:cautious scrutiny",
                                "Director Harlan:concern mixed with political fear"
                            ]
                        },
                        "stats": {}
                    },
                    {
                        "id": 2,
                        "name": "Marcus Reed",
                        "user_controlled": False,
                        "location": 1,
                        "public_state": "Continuing limited observatory work while insisting that Director Harlan's disappearance must have a rational explanation.",
                        "private_state": "Desperate to recover Harlan's missing notebook before Eleanor, Arthur, or anyone else uses it to expose his unauthorized experiments. He suspects the underground signals are connected to Harlan's disappearance but fears admitting how much he knows.",
                        "attributes": {
                            "relationship": [
                                "Eleanor Graves:suspicion",
                                "Clara Whitlock:trust and reliance",
                                "Arthur Moore:intellectual curiosity mixed with caution",
                                "Director Harlan:guilt, loyalty, and unresolved dependence"
                            ]
                        },
                        "stats": {}
                    },
                    {
                        "id": 3,
                        "name": "Clara Whitlock",
                        "user_controlled": False,
                        "location": 3,
                        "public_state": "Running the Iron Stag Inn during the Founder's Festival, serving guests, listening to rumours, and presenting herself as merely curious about Arthur Moore's arrival.",
                        "private_state": "Trying to uncover the truth behind Director Harlan's disappearance, partly out of concern and partly because she believes the story could be valuable to a newspaper. She is also quietly watching Marcus, whom she believes is frightened rather than malicious.",
                        "attributes": {
                            "relationship": [
                                "Eleanor Graves:wary",
                                "Marcus Reed:protective fondness",
                                "Arthur Moore:friendly curiosity",
                                "Director Harlan:concerned respect"
                            ]
                        },
                        "stats": {}
                    },
                    {
                        "id": 4,
                        "name": "Arthur Moore",
                        "user_controlled": True,
                        "location": 3,
                        "public_state": "Arriving in Blackwater Ridge during the Founder's Festival as an independent investigator, presenting himself as professionally interested in Director Harlan's disappearance.",
                        "private_state": "Investigating who anonymously hired him, why payment depends on obtaining evidence, and whether Harlan's disappearance is connected to the observatory, the old mine, or the town's leadership.",
                        "attributes": {
                            "relationship": [
                                "Eleanor Graves:professionally cautious",
                                "Marcus Reed:unresolved suspicion",
                                "Clara Whitlock:tentative trust",
                                "Director Harlan:case subject"
                            ]
                        },
                        "stats": {}
                    }
                ],
                "locations": [
                    {
                        "id": 1,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Blackwater Observatory",
                        "scene": "Director's Office",
                        "description": "The private office of the missing Director Harlan. Tall windows face the mountains, while shelves of astronomical records, correspondence and field notes line the walls. The room is orderly, quiet, and formal.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 1,
                                "name": "Director's Desk",
                                "type": "important-item",
                                "description": "A heavy oak desk used by Director Harlan. Its drawers hold correspondence, old stationery, and observatory paperwork.",
                                "status": "Closed. The surface is neat.",
                                "interactions": [
                                    "inspect",
                                    "open drawers",
                                    "search for hidden compartment"
                                ]
                            },
                            {
                                "id": 2,
                                "name": "Locked Filing Cabinet",
                                "type": "important-item",
                                "description": "A reinforced metal cabinet used for observatory administrative records and archived research paperwork.",
                                "status": "Locked. The lock plate is visibly scratched.",
                                "interactions": [
                                    "inspect",
                                    "attempt to unlock",
                                    "force open"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 2,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Blackwater Observatory",
                        "scene": "Telescope Chamber",
                        "description": "The main chamber of the observatory, dominated by a large brass-and-steel telescope mounted beneath the rotating dome. The room smells of machine oil, cold stone and dust. Instruments, calibration charts and star tables are arranged around the chamber.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 3,
                                "name": "Main Telescope",
                                "type": "important-item",
                                "description": "The observatory's primary telescope, a large and finely maintained astronomical instrument aimed through the dome aperture.",
                                "status": "Functional. Its alignment controls are not currently set to their marked resting positions.",
                                "interactions": [
                                    "inspect",
                                    "adjust alignment",
                                    "look through"
                                ]
                            },
                            {
                                "id": 4,
                                "name": "Signal Recording Apparatus",
                                "type": "important-item",
                                "description": "A collection of coils, receivers, paper rolls and improvised attachments used to record signal patterns alongside astronomical observations.",
                                "status": "Powered down. Several paper recording strips remain attached to the machine.",
                                "interactions": [
                                    "inspect",
                                    "read recording strips",
                                    "attempt to operate"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 3,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Iron Stag Inn",
                        "scene": "Bar",
                        "description": "The busy ground-floor bar of the Iron Stag Inn. Locals gather here for drink, gossip and festival talk. The room is warm, noisy and crowded enough that a careful listener can overhear many things without appearing suspicious.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 5,
                                "name": "Visitor's Room Ledger",
                                "type": "important-item",
                                "description": "The inn's room ledger, recording room usage, dates, names, payments and occasional notes made by Clara Whitlock.",
                                "status": "Kept behind the bar. Closed unless accessed.",
                                "interactions": [
                                    "read",
                                    "inspect Room 7 entry",
                                    "add entry"
                                ]
                            },
                            {
                                "id": 6,
                                "name": "Notice Board",
                                "type": "important-item",
                                "description": "A public notice board covered with festival announcements, missing notices, trade offers and local messages.",
                                "status": "Crowded with new festival notices. Older papers are pinned underneath.",
                                "interactions": [
                                    "inspect",
                                    "read notices",
                                    "remove notice"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 4,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Iron Stag Inn",
                        "scene": "Room 7",
                        "description": "A modest guest room on the upper floor of the Iron Stag Inn. It is tidy, sparse, and quiet, with a small writing desk and a window overlooking the side alley.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 7,
                                "name": "Room 7 Writing Desk",
                                "type": "important-item",
                                "description": "A small guest writing desk with a worn surface, an ink bottle and a narrow drawer.",
                                "status": "Mostly clean. Faint pressure marks are visible on the writing surface.",
                                "interactions": [
                                    "inspect",
                                    "search drawer",
                                    "take rubbing of writing marks"
                                ]
                            },
                            {
                                "id": 8,
                                "name": "Guest Room Window",
                                "type": "important-item",
                                "description": "A window overlooking the side alley beside the inn.",
                                "status": "Closed but not latched. The sill has faint scrape marks.",
                                "interactions": [
                                    "inspect",
                                    "open",
                                    "look outside"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 5,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Town Hall",
                        "scene": "Mayor's Office",
                        "description": "Eleanor Graves's office inside Town Hall. The room is formal, controlled and carefully arranged. A locked cabinet, a polished desk and framed town charters communicate authority and civic stability.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 9,
                                "name": "Mayor's Desk",
                                "type": "important-item",
                                "description": "A polished desk containing official correspondence, festival planning papers and sealed municipal documents.",
                                "status": "Orderly.",
                                "interactions": [
                                    "inspect",
                                    "search",
                                    "read visible papers"
                                ]
                            },
                            {
                                "id": 10,
                                "name": "Municipal Lockbox",
                                "type": "important-item",
                                "description": "A compact iron lockbox used for sensitive town documents and private administrative records.",
                                "status": "Locked and kept inside the mayor's office.",
                                "interactions": [
                                    "inspect",
                                    "attempt to unlock",
                                    "move"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 6,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Town Hall",
                        "scene": "Records Room",
                        "description": "A cramped archival room filled with shelves of deeds, survey papers, council minutes and tax records. Dust hangs in the air, and the shelves are densely packed with folders and document boxes.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 11,
                                "name": "Property Record Shelves",
                                "type": "important-item",
                                "description": "Shelves containing land ownership records for Blackwater Ridge and its surrounding territory, including the old mine area.",
                                "status": "Dusty. Some folders are unevenly aligned on the shelves.",
                                "interactions": [
                                    "inspect",
                                    "search records",
                                    "compare documents"
                                ]
                            },
                            {
                                "id": 12,
                                "name": "Survey Archive Cabinet",
                                "type": "important-item",
                                "description": "A cabinet containing older surveyor records and historical mine documentation.",
                                "status": "Closed but not locked.",
                                "interactions": [
                                    "open",
                                    "search",
                                    "retrieve map"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 7,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Town Square",
                        "scene": "Festival Monument",
                        "description": "The centre of Blackwater Ridge, currently decorated for the Founder's Festival. A stone monument commemorates the town's founding and stands among bunting, stalls and temporary wooden stages.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 13,
                                "name": "Festival Monument",
                                "type": "important-item",
                                "description": "A commemorative stone monument with a plaque marking the town's founding.",
                                "status": "Decorated for the festival.",
                                "interactions": [
                                    "inspect",
                                    "remove plaque",
                                    "hide item",
                                    "retrieve hidden item"
                                ]
                            },
                            {
                                "id": 14,
                                "name": "Festival Stalls",
                                "type": "important-item",
                                "description": "Temporary market stalls set up for the Founder's Festival, selling food, trinkets and local crafts.",
                                "status": "Active during the day and partly covered at night.",
                                "interactions": [
                                    "inspect",
                                    "ask vendors",
                                    "search after closing"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 8,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Old Mine",
                        "scene": "Mine Entrance",
                        "description": "The boarded entrance to the abandoned silver mine north of town. The official closure signs are old and weathered, and the ground nearby is rough and uneven.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 15,
                                "name": "Boarded Mine Entrance",
                                "type": "important-item",
                                "description": "The sealed entrance to the old silver mine where eleven workers died twenty years ago.",
                                "status": "Officially closed. Boards cover the entrance.",
                                "interactions": [
                                    "inspect",
                                    "remove boards",
                                    "enter mine"
                                ]
                            },
                            {
                                "id": 16,
                                "name": "Old Warning Sign",
                                "type": "important-item",
                                "description": "A weathered municipal warning sign declaring the mine unsafe and closed by town order.",
                                "status": "Faded and partially broken.",
                                "interactions": [
                                    "inspect",
                                    "read",
                                    "move aside"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 9,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "Old Mine",
                        "scene": "Main Tunnel",
                        "description": "A dark, unstable tunnel inside the abandoned mine. The air is cold and mineral-heavy. Old rails run into darkness, and sounds echo strangely through unseen side passages.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 17,
                                "name": "Collapsed Side Passage",
                                "type": "important-item",
                                "description": "A partially collapsed passage branching from the main tunnel. Loose stones and cracked support beams make it dangerous to disturb.",
                                "status": "Blocked, but not completely sealed.",
                                "interactions": [
                                    "inspect",
                                    "listen",
                                    "clear debris"
                                ]
                            },
                            {
                                "id": 18,
                                "name": "Rusting Mine Cart",
                                "type": "important-item",
                                "description": "An old ore cart sitting on warped rails, half-filled with stone fragments and rotting wood.",
                                "status": "Stationary. Its wheels are rusted.",
                                "interactions": [
                                    "inspect",
                                    "search",
                                    "push"
                                ]
                            }
                        ]
                    },
                    {
                        "id": 10,
                        "primary_location": "Blackwater Ridge",
                        "detailed_location": "North Forest",
                        "scene": "Abandoned Cabin",
                        "description": "A small hunter's cabin hidden among the trees north of town. It has been abandoned for years. Dust lies across the room, and the air smells of damp timber and old ash.",
                        "attributes": {},
                        "stats": {},
                        "entities": [
                            {
                                "id": 19,
                                "name": "Cabin Hearth",
                                "type": "important-item",
                                "description": "A stone hearth filled with ash.",
                                "status": "Cold.",
                                "interactions": [
                                    "inspect",
                                    "search ash",
                                    "light fire"
                                ]
                            },
                            {
                                "id": 20,
                                "name": "Loose Floorboard",
                                "type": "important-item",
                                "description": "A warped floorboard near the cabin wall.",
                                "status": "Slightly raised from the surrounding floor.",
                                "interactions": [
                                    "inspect",
                                    "lift",
                                    "hide item",
                                    "retrieve hidden item"
                                ]
                            }
                        ]
                    }
                ],
                "inventory": {
                    "0": {
                        "items": [
                            {
                                "id": 1,
                                "name": "Harlan's Notebook",
                                "description": "Director Harlan's missing notebook, containing research notes, rough mine sketches, observatory calculations, and several encoded entries.",
                                "quantity": 1,
                                "quality": None
                            },
                            {
                                "id": 2,
                                "name": "Brass Laboratory Key",
                                "description": "A small brass key that opens the locked laboratory in Blackwater Observatory. It is currently hidden inside the hollow festival monument in town square.",
                                "quantity": 1,
                                "quality": None
                            },
                            {
                                "id": 3,
                                "name": "Silver Pocket Watch",
                                "description": "Director Harlan's silver pocket watch. It stopped at 11:17 PM and may indicate when something significant happened.",
                                "quantity": 1,
                                "quality": "damaged"
                            },
                            {
                                "id": 4,
                                "name": "Unknown Visitor's Note Fragment",
                                "description": "A torn fragment of paper connected to the unknown visitor who rented Room 7. It contains only partial handwriting and is not enough to identify the writer by itself.",
                                "quantity": 1,
                                "quality": "torn"
                            }
                        ],
                        "equipments": []
                    },
                    "1": {
                        "items": [
                            {
                                "id": 5,
                                "name": "Surveyor's Map",
                                "description": "An old surveyor's map of the mine and surrounding land. It shows a tunnel not present on official town records.",
                                "quantity": 1,
                                "quality": "aged"
                            },
                            {
                                "id": 6,
                                "name": "Mayor's Administrative Seal",
                                "description": "Eleanor Graves's official municipal seal, used to authenticate town documents and records.",
                                "quantity": 1,
                                "quality": None
                            }
                        ],
                        "equipments": []
                    },
                    "2": {
                        "items": [
                            {
                                "id": 7,
                                "name": "Signal Recording Strip",
                                "description": "A narrow paper strip from the observatory's recording apparatus, marked with irregular signal patterns detected beneath Blackwater Ridge.",
                                "quantity": 1,
                                "quality": None
                            },
                            {
                                "id": 8,
                                "name": "Marcus's Calibration Notes",
                                "description": "Marcus Reed's personal technical notes on telescope alignment, receiver behaviour, and his unauthorized signal experiments.",
                                "quantity": 1,
                                "quality": None
                            }
                        ],
                        "equipments": []
                    },
                    "3": {
                        "items": [
                            {
                                "id": 9,
                                "name": "Clara's Gossip Notebook",
                                "description": "Clara Whitlock's private notebook of rumours, guest observations, suspicious behaviour, and overheard conversations at the Iron Stag Inn.",
                                "quantity": 1,
                                "quality": None
                            },
                            {
                                "id": 10,
                                "name": "Room 7 Cash Receipt",
                                "description": "A receipt for the unknown visitor's payment for Room 7 at the Iron Stag Inn. The name written on it is believed to be false.",
                                "quantity": 1,
                                "quality": None
                            }
                        ],
                        "equipments": []
                    },
                    "4": {
                        "items": [
                            {
                                "id": 11,
                                "name": "Anonymous Letter",
                                "description": "The letter that brought Arthur Moore to Blackwater Ridge. It requests an investigation into Director Harlan's disappearance and states that payment depends on obtaining evidence.",
                                "quantity": 1,
                                "quality": None
                            },
                            {
                                "id": 12,
                                "name": "Investigator's Notebook",
                                "description": "Arthur Moore's own notebook for case notes, witness statements, deductions, timelines, and contradictions.",
                                "quantity": 1,
                                "quality": None
                            }
                        ],
                        "equipments": [
                            {
                                "id": 1,
                                "name": "Pocket Revolver",
                                "description": "Arthur Moore's compact personal revolver, carried for protection rather than open intimidation.",
                                "status": "equipped",
                                "quality": None
                            },
                            {
                                "id": 2,
                                "name": "Investigator's Coat",
                                "description": "A practical dark travelling coat with deep pockets suitable for carrying papers, small tools, and evidence.",
                                "status": "equipped",
                                "quality": None
                            }
                        ]
                    }
                },
                "factions": [
                    {
                        "id": 1,
                        "name": "Blackwater Observatory",
                        "description": "The astronomical observatory overlooking Blackwater Ridge. Publicly, it studies stars and celestial phenomena; privately, it has received secret government funding for unusual signal research. Its reputation is scholarly, but its isolation and secrecy make it a source of local suspicion.",
                        "attributes": {},
                        "stats": {}
                    },
                    {
                        "id": 2,
                        "name": "Blackwater Town Council",
                        "description": "The municipal authority of Blackwater Ridge, responsible for town administration, public records, festival arrangements and official decisions. It is closely associated with Mayor Eleanor Graves and the public image of the town.",
                        "attributes": {},
                        "stats": {}
                    },
                    {
                        "id": 3,
                        "name": "Iron Stag Inn",
                        "description": "The central inn and tavern of Blackwater Ridge. It is not a political institution, but it acts as the town's informal information hub because locals, visitors and festival guests regularly gather there.",
                        "attributes": {},
                        "stats": {}
                    },
                    {
                        "id": 4,
                        "name": "Unknown Government Contractor",
                        "description": "A vague outside interest connected to the observatory's original secret funding. Its exact identity, authority and current involvement are not publicly known, but it is relevant to Director Harlan's past work and the unknown visitor who came before his disappearance.",
                        "attributes": {},
                        "stats": {}
                    },
                    {
                        "id": 5,
                        "name": "Mine Land Shell Companies",
                        "description": "A set of obscure legal entities associated with property purchases around the abandoned old mine. They may not operate openly in town, but they are repeatedly connected to altered records and suspicious land transfers.",
                        "attributes": {},
                        "stats": {}
                    }
                ],
                "faction_relationships": [
                    {
                        "id": None,
                        "from_type": "character",
                        "from_id": 1,
                        "to_type": "faction",
                        "to_id": 2,
                        "relationship": "mayor",
                        "private": False
                    },
                    {
                        "id": None,
                        "from_type": "character",
                        "from_id": 2,
                        "to_type": "faction",
                        "to_id": 1,
                        "relationship": "employee",
                        "private": False
                    },
                    {
                        "id": None,
                        "from_type": "character",
                        "from_id": 3,
                        "to_type": "faction",
                        "to_id": 3,
                        "relationship": "proprietor",
                        "private": False
                    },
                    {
                        "id": None,
                        "from_type": "character",
                        "from_id": 1,
                        "to_type": "faction",
                        "to_id": 5,
                        "relationship": "concealed administrative connection",
                        "private": True
                    },
                    {
                        "id": None,
                        "from_type": "faction",
                        "from_id": 4,
                        "to_type": "faction",
                        "to_id": 1,
                        "relationship": "secret research sponsor",
                        "private": True
                    },
                    {
                        "id": None,
                        "from_type": "faction",
                        "from_id": 5,
                        "to_type": "faction",
                        "to_id": 2,
                        "relationship": "records irregularity subject",
                        "private": True
                    }
                ],
                "tasks": [
                    {
                        "id": 1,
                        "character_ids": [
                            4
                        ],
                        "private": False,
                        "priority": "urgent",
                        "status": "in_progress",
                        "type": "main_quest",
                        "goal": "Determine what happened to Director Harlan.",
                        "progress": 0,
                        "source": "Anonymous Letter"
                    },
                    {
                        "id": 2,
                        "character_ids": [
                            4
                        ],
                        "private": True,
                        "priority": "important",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Identify who anonymously hired Arthur Moore.",
                        "progress": 0,
                        "source": "Arthur Moore's professional suspicion"
                    },
                    {
                        "id": 3,
                        "character_ids": [
                            4
                        ],
                        "private": False,
                        "priority": "normal",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Locate Harlan's missing notebook.",
                        "progress": 0,
                        "source": "Investigation into Harlan's final movements"
                    },
                    {
                        "id": 4,
                        "character_ids": [
                            4
                        ],
                        "private": False,
                        "priority": "normal",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Discover the identity of the unknown visitor who stayed in Room 7.",
                        "progress": 0,
                        "source": "The suspicious Room 7 ledger entry"
                    },
                    {
                        "id": 5,
                        "character_ids": [
                            1
                        ],
                        "private": True,
                        "priority": "urgent",
                        "status": "in_progress",
                        "type": "main_quest",
                        "goal": "Prevent public panic regarding Director Harlan's disappearance.",
                        "progress": 70,
                        "source": "Mayoral duty and concern for the town's reputation"
                    },
                    {
                        "id": 6,
                        "character_ids": [
                            1
                        ],
                        "private": True,
                        "priority": "important",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Determine why Arthur Moore has come to Blackwater Ridge and whether he is a threat.",
                        "progress": 10,
                        "source": "Eleanor's suspicion of outside investigators"
                    },
                    {
                        "id": 7,
                        "character_ids": [
                            1
                        ],
                        "private": True,
                        "priority": "important",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Prevent investigation of irregular land transactions near the old mine.",
                        "progress": 60,
                        "source": "Eleanor's connection to the altered property records"
                    },
                    {
                        "id": 8,
                        "character_ids": [
                            2
                        ],
                        "private": True,
                        "priority": "urgent",
                        "status": "in_progress",
                        "type": "main_quest",
                        "goal": "Recover Harlan's notebook before anyone else obtains it.",
                        "progress": 15,
                        "source": "Marcus's fear that the notebook exposes his unauthorized experiments"
                    },
                    {
                        "id": 9,
                        "character_ids": [
                            2
                        ],
                        "private": True,
                        "priority": "important",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Conceal evidence of unauthorized signal experiments.",
                        "progress": 80,
                        "source": "Marcus's self-preservation"
                    },
                    {
                        "id": 10,
                        "character_ids": [
                            2
                        ],
                        "private": True,
                        "priority": "normal",
                        "status": "paused",
                        "type": "side_quest",
                        "goal": "Determine the source of the underground radio signals.",
                        "progress": None,
                        "source": "Marcus's scientific obsession"
                    },
                    {
                        "id": 11,
                        "character_ids": [
                            3
                        ],
                        "private": True,
                        "priority": "important",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Learn the truth about Director Harlan's disappearance.",
                        "progress": 20,
                        "source": "Clara's curiosity and concern"
                    },
                    {
                        "id": 12,
                        "character_ids": [
                            3
                        ],
                        "private": True,
                        "priority": "normal",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Identify the unknown visitor who rented Room 7.",
                        "progress": 40,
                        "source": "Clara's inn records and memory of the visitor"
                    },
                    {
                        "id": 13,
                        "character_ids": [
                            3
                        ],
                        "private": True,
                        "priority": "background",
                        "status": "in_progress",
                        "type": "daily",
                        "goal": "Collect and organize rumours heard at the Iron Stag Inn.",
                        "progress": None,
                        "source": "Clara's occupation and habits"
                    },
                    {
                        "id": 14,
                        "character_ids": [
                            1,
                            2
                        ],
                        "private": True,
                        "priority": "background",
                        "status": "in_progress",
                        "type": "side_quest",
                        "goal": "Keep the observatory operational despite Director Harlan's absence.",
                        "progress": 65,
                        "source": "Observatory responsibility and town reputation"
                    }
                ],
                "world_entries": [
                    {
                        "id": 1,
                        "scope": [
                            0
                        ],
                        "content": "Blackwater Ridge is an isolated mountain town built around Blackwater Observatory.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "always",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 2,
                        "scope": [
                            0
                        ],
                        "content": "The current year is 1912, and Blackwater Ridge is holding its annual Founder's Festival.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "always",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 3,
                        "scope": [
                            0
                        ],
                        "content": "Director Harlan, head of Blackwater Observatory, disappeared three weeks ago. Officially, he left without notice.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "always",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 4,
                        "scope": [
                            0
                        ],
                        "content": "Many residents of Blackwater Ridge do not believe the official explanation for Director Harlan's disappearance.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "visible",
                        "recall_type": "semantic",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": "Recall when the scene involves public mood, rumours, townspeople, the festival, or discussion of Harlan's disappearance."
                    },
                    {
                        "id": 5,
                        "scope": [
                            0
                        ],
                        "content": "Twenty years ago, a collapse in the old silver mine killed eleven workers. The mine was officially closed after the incident.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "old mine",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine collapse",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "eleven workers",
                                "similarity": 0.75,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 6,
                        "scope": [
                            1,
                            2
                        ],
                        "content": "Eight years ago, Blackwater Observatory began receiving secret government funding.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "government funding",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "observatory funding",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "secret funding",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 7,
                        "scope": [
                            -1
                        ],
                        "content": "The secret government funding for Blackwater Observatory was connected to unusual signal research rather than ordinary astronomy.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            6
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 8,
                        "scope": [
                            1
                        ],
                        "content": "Three years ago, property around the old mine was sold to shell companies through irregular transactions.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "property records",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "shell companies",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine land",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 9,
                        "scope": [
                            1
                        ],
                        "content": "Some town property records concerning land near the old mine were altered.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            8
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 10,
                        "scope": [
                            -1
                        ],
                        "content": "The altered property records are connected to the hidden mine tunnel and the underground chamber beneath the mine.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            8,
                            9
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 11,
                        "scope": [
                            2
                        ],
                        "content": "Six months ago, Marcus Reed began unauthorized experiments involving underground radio signals.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Marcus experiments",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "underground signals",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "radio signals",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 12,
                        "scope": [
                            2
                        ],
                        "content": "Marcus Reed has detected strange signal patterns that appear to originate from beneath Blackwater Ridge.",
                        "visibility": "known",
                        "confidence": 0.9,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            11
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 13,
                        "scope": [
                            1,
                            2
                        ],
                        "content": "Five weeks ago, Director Harlan discovered irregularities in property records connected to land near the old mine.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan property records",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Harlan discovered",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "land records",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 14,
                        "scope": [
                            0
                        ],
                        "content": "Four weeks ago, Director Harlan began carrying a notebook everywhere.",
                        "visibility": "perceived",
                        "confidence": 0.9,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan's Notebook",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Harlan carrying notebook",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "missing notebook",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 15,
                        "scope": [
                            0
                        ],
                        "content": "Harlan's Notebook is currently missing. It contains research notes, maps, and encoded entries.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan's Notebook",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "missing notebook",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "encoded entries",
                                "similarity": 0.75,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 16,
                        "scope": [
                            2
                        ],
                        "content": "Marcus knows that the brass laboratory key is hidden inside the hollow festival monument in town square.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "brass laboratory key",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "hollow festival monument",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "laboratory key",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 17,
                        "scope": [
                            -1
                        ],
                        "content": "The brass laboratory key opens the locked laboratory inside Blackwater Observatory.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            16
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 18,
                        "scope": [
                            3
                        ],
                        "content": "An unknown visitor arrived in Blackwater Ridge five days before Director Harlan disappeared.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "unknown visitor",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "Room 7",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "visitor before Harlan disappeared",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 19,
                        "scope": [
                            3
                        ],
                        "content": "The unknown visitor rented Room 7 at the Iron Stag Inn under a false name and paid in cash.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            18
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 20,
                        "scope": [
                            3
                        ],
                        "content": "Clara Whitlock knows the unknown visitor met secretly with Director Harlan before Harlan disappeared.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            18,
                            19
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 21,
                        "scope": [
                            3
                        ],
                        "content": "Clara does not know the unknown visitor's true identity.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            18,
                            19,
                            20
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 22,
                        "scope": [
                            2
                        ],
                        "content": "Marcus believes Director Harlan became increasingly paranoid before his disappearance.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan paranoid",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Marcus Harlan",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 23,
                        "scope": [
                            1
                        ],
                        "content": "Eleanor publicly presents Director Harlan as overworked rather than frightened or endangered.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan overworked",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Eleanor Harlan",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 24,
                        "scope": [
                            3
                        ],
                        "content": "Clara believes Director Harlan seemed frightened of someone shortly before he vanished.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Harlan frightened",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Clara Harlan",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 25,
                        "scope": [
                            4
                        ],
                        "content": "Arthur Moore was anonymously hired to investigate Director Harlan's disappearance.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "visible",
                        "recall_type": "always",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 26,
                        "scope": [
                            4
                        ],
                        "content": "Arthur's payment will only be delivered if he obtains evidence concerning Harlan's disappearance.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            25
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 27,
                        "scope": [
                            4
                        ],
                        "content": "Arthur does not know the identity of the person who hired him.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            25
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 28,
                        "scope": [
                            3
                        ],
                        "content": "Clara Whitlock's Visitor's Room Ledger records the Room 7 rental under a false name.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Visitor's Room Ledger",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "Room 7 ledger",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "false name",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            18,
                            19
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 29,
                        "scope": [
                            0
                        ],
                        "content": "The Surveyor's Map shows an old mine tunnel that is not present on official records.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Surveyor's Map",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "hidden tunnel",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine map",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 30,
                        "scope": [
                            0
                        ],
                        "content": "Director Harlan's silver pocket watch stopped at 11:17 PM.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "silver pocket watch",
                                "similarity": 0.7,
                                "embedding": None
                            },
                            {
                                "keyword": "11:17 PM",
                                "similarity": 0.8,
                                "embedding": None
                            },
                            {
                                "keyword": "Harlan's watch",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 31,
                        "scope": [
                            -1
                        ],
                        "content": "Director Harlan's silver pocket watch will be found in the abandoned cabin in the North Forest unless events change its location.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            30
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 32,
                        "scope": [
                            0
                        ],
                        "content": "Locals sometimes report seeing lights inside the old mine despite its official closure.",
                        "visibility": "suspected",
                        "confidence": 0.7,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "lights in the mine",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "old mine rumours",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine entrance",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 33,
                        "scope": [
                            0
                        ],
                        "content": "Locals have recently mentioned fresh footprints near the abandoned cabin in the North Forest.",
                        "visibility": "perceived",
                        "confidence": 0.75,
                        "narration_permission": "visible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "North Forest cabin",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "fresh footprints",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "abandoned cabin",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 34,
                        "scope": [
                            -1
                        ],
                        "content": "Director Harlan discovered illegal land sales, a hidden mine tunnel, and an underground chamber beneath the old mine.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "semantic",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": "Recall only for GM-side reasoning when resolving the true cause of Harlan's disappearance, the mine mystery, the shell companies, or the hidden underground chamber."
                    },
                    {
                        "id": 35,
                        "scope": [
                            -1
                        ],
                        "content": "The unknown visitor was a government contractor connected to Blackwater Observatory's original secret funding.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "semantic",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": "Recall only for GM-side reasoning involving the unknown visitor, secret funding, government contractors, or Harlan's final meeting."
                    },
                    {
                        "id": 36,
                        "scope": [
                            -1
                        ],
                        "content": "Director Harlan entered the hidden mine tunnel during his investigation and was trapped by a tunnel collapse.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "semantic",
                        "keywords": None,
                        "chained_ids": None,
                        "semantic_instruction": "Recall only for GM-side reasoning when determining Harlan's true fate, mine exploration outcomes, or clues pointing to a collapse."
                    },
                    {
                        "id": 37,
                        "scope": [
                            -1
                        ],
                        "content": "Director Harlan is still alive but stranded underground.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "invisible",
                        "recall_type": "chained",
                        "keywords": None,
                        "chained_ids": [
                            36
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 38,
                        "scope": [
                            -1
                        ],
                        "content": "Close inspection of Director Harlan's desk can reveal signs that some papers were removed and the room was later restored to order.",
                        "visibility": "known",
                        "confidence": 0.9,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Director's Desk",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "missing papers",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "searched office",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 39,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the locked filing cabinet can suggest that someone may have tried to open it without the key.",
                        "visibility": "perceived",
                        "confidence": 0.75,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Locked Filing Cabinet",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "scratched lock",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "attempt to unlock",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 40,
                        "scope": [
                            2
                        ],
                        "content": "Marcus Reed knows the main telescope is misaligned from its standard calibration position.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Main Telescope",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "misaligned telescope",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "calibration position",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 41,
                        "scope": [
                            2
                        ],
                        "content": "Marcus Reed knows several recent recording strips on the signal recording apparatus contain irregular signal patterns.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Signal Recording Apparatus",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recording strips",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "irregular signal patterns",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            11,
                            12
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 42,
                        "scope": [
                            -1
                        ],
                        "content": "A careful search of Room 7 can reveal signs that someone stayed briefly while avoiding obvious traces.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Room 7",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "guest room",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "stayed briefly",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            18,
                            19
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 43,
                        "scope": [
                            -1
                        ],
                        "content": "The pressure marks on the Room 7 writing desk may preserve traces of something written there.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Room 7 Writing Desk",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "pressure marks",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "writing marks",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            42
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 44,
                        "scope": [
                            -1
                        ],
                        "content": "The scrape marks on the Room 7 window sill may indicate that the window was used carefully or repeatedly.",
                        "visibility": "perceived",
                        "confidence": 0.7,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Guest Room Window",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "scrape marks",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Room 7 window",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            42
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 45,
                        "scope": [
                            1
                        ],
                        "content": "Eleanor Graves habitually watches her desk and municipal papers carefully when others are in her office.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Mayor's Desk",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "municipal papers",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Eleanor office",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 46,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the property record shelves can reveal that folders concerning mine-adjacent land were recently removed and replaced.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Property Record Shelves",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine-adjacent land",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent removal",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            8,
                            9
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 47,
                        "scope": [
                            -1
                        ],
                        "content": "Searching the survey archive cabinet can reveal older maps and mine documentation not normally consulted in public town business.",
                        "visibility": "known",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Survey Archive Cabinet",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "older maps",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine documentation",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            29
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 48,
                        "scope": [
                            -1
                        ],
                        "content": "Close inspection of the festival monument can reveal that one plaque is loose and that there is a hollow space behind it.",
                        "visibility": "known",
                        "confidence": 0.9,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Festival Monument",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "loose plaque",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "hollow monument",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            16
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 49,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the boarded mine entrance can reveal that several boards have been loosened and replaced more than once.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Boarded Mine Entrance",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "loosened boards",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "enter mine",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            32
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 50,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the old warning sign can reveal that dirt around its base was cleared recently.",
                        "visibility": "perceived",
                        "confidence": 0.75,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Old Warning Sign",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "cleared dirt",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine entrance",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            32
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 51,
                        "scope": [
                            -1
                        ],
                        "content": "Air can be felt moving faintly through gaps in the collapsed side passage.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Collapsed Side Passage",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "air moving",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "clear debris",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            36
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 52,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the abandoned cabin can reveal disturbed dust consistent with recent use.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Abandoned Cabin",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "disturbed dust",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent use",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            33
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 53,
                        "scope": [
                            -1
                        ],
                        "content": "Searching the cabin hearth can reveal traces of a recent small fire beneath the older ash.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Cabin Hearth",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent fire",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "search ash",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            52
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 54,
                        "scope": [
                            -1
                        ],
                        "content": "Lifting the loose floorboard in the abandoned cabin can reveal whether a small object has been hidden beneath it.",
                        "visibility": "known",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Loose Floorboard",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "retrieve hidden item",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "hidden beneath",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            31
                        ],
                        "semantic_instruction": None
                    }
                ]
            },
            "database_patch_preview": [
                {
                    "mutation_id": "4c241b91-9f92-44d0-995a-00dc7ab1bc0f",
                    "operation": "update",
                    "target": {
                        "object_type": "state",
                        "object_id": 1
                    },
                    "payload": {
                        "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; she verified records from the Visitor's Room Ledger."
                    },
                    "reason": "Reflect resolved turn in narrative history",
                    "source_event": None
                },
                {
                    "mutation_id": "f30af8f1-850f-4aa1-8890-9e5211df865b",
                    "operation": "update",
                    "target": {
                        "object_type": "task",
                        "object_id": 12
                    },
                    "payload": {
                        "progress": 40
                    },
                    "reason": "Clara gained useful information by checking the ledger, advancing her investigation into the unknown visitor",
                    "source_event": None
                }
            ]
        },
        "narration": "The bar hums with festival noise—laughter and clinking glass—but Clara’s attention remains fixed on you. She offers a polite smile and turns slightly toward the shelf behind the counter. Her hands move with practiced efficiency as she retrieves a large, bound Visitor’s Room Ledger.\n\nFlipping through the pages, she maintains eye contact the entire time. The leather cover creaks softly under her fingers. She pauses on an entry near the date of Director Harlan’s disappearance before closing the ledger with a firm thud. She sets it down and looks back up at you, waiting in the quiet space between the noise of the room.",
        "summary_output": {
            "scene_summary": "Clara retrieves a large Visitor’s Room Ledger from behind the bar counter during the festival noise. She flips through to an entry near Director Harlan's disappearance date, closes the book with a firm thud, and sets it down while waiting for the player's next move.",
            "short_term_memory": "Arthur arrived at the Iron Stag Inn during the Founder's Festival, where Eleanor greeted him and probed his purpose while presenting the town as orderly. Clara observed Arthur’s controlled manner and suspected he was not merely a curious traveller. Now, Clara has retrieved the Visitor’s Room Ledger, paused on an entry near Director Harlan's disappearance date, and set it down awaiting the player's response.",
            "long_term_memory": "Director Harlan disappeared three weeks ago; officially he left without notice, though many residents doubt this. Current investigation threads include the observatory, old mine, altered property records, unknown visitor, and Harlan's missing notebook. Arthur is investigating at the Iron Stag Inn during the Founder's Festival, where Clara has begun checking the Visitor’s Room Ledger for entries near Harlan's disappearance date.",
            "active_scene": "Iron Stag Inn bar during the Founder's Festival",
            "open_threads": [
                "What specific entry did Clara locate in the ledger near Harlan's disappearance date?",
                "Will Arthur reveal his anonymous letter to Clara or Eleanor now that she is investigating records?",
                "How will Clara react once the player responds to her waiting gesture?"
            ],
            "continuity_notes": [
                "The Visitor’s Room Ledger is open on the counter; Clara is waiting for a response.",
                "Arthur has not yet revealed the anonymous letter to Eleanor or Clara.",
                "Festival noise (laughter, clinking glass) remains the ambient background unless shifted."
            ]
        }
    }


@pytest.fixture
def mock_world_create(mock_simulation,
                      mock_simulation_state_1,
                      mock_characters,
                      mock_locations,
                      mock_items_0,
                      mock_items_1,
                      mock_items_2,
                      mock_items_3,
                      mock_items_4,
                      mock_equipments_0,
                      mock_equipments_1,
                      mock_equipments_2,
                      mock_equipments_3,
                      mock_equipments_4,
                      mock_factions,
                      mock_faction_relationships,
                      mock_tasks,
                      mock_world_entries,
                      ) -> WorldCreate:
    return WorldCreate(
        name=mock_simulation.name,
        description=mock_simulation.description,
        act_for_user=False,
        enable_tts=True,
        enable_image_generation=True,
        agent_preset=mock_simulation.agent_preset,
        data_preset=mock_simulation.data_preset,
        embedding_profile=mock_simulation.embedding_profile,
        language=mock_simulation.language,
        state=mock_simulation_state_1,
        characters=mock_characters,
        locations=mock_locations,
        factions=mock_factions,
        faction_relationships=mock_faction_relationships,
        inventory={
            0: CharacterInventory(
                items=mock_items_0,
                equipments=mock_equipments_0,
            ),
            1: CharacterInventory(
                items=mock_items_1,
                equipments=mock_equipments_1,
            ),
            2: CharacterInventory(
                items=mock_items_2,
                equipments=mock_equipments_2,
            ),
            3: CharacterInventory(
                items=mock_items_3,
                equipments=mock_equipments_3,
            ),
            4: CharacterInventory(
                items=mock_items_4,
                equipments=mock_equipments_4,
            ),
        },
        tasks=mock_tasks,
        world_entries=mock_world_entries,
        turn_records=[],
    )
