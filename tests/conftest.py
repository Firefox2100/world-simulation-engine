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
