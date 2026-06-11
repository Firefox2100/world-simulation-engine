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
    ResolverAgentProfile
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

Hard rules:
- The location is a pending proposal, not canonical.
- Do not reuse an existing location.
- Do not contradict existing locations or state summary.
- Do not solve major mysteries.
- Do not reveal final answers unless explicitly required.
- Use temporary IDs only for generated entities.
- If adding entities inside the location, their type must be one of allowed_entity_types.
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
{{ data.generation_context }}

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

Hard rules:
- The item is a pending proposal, not canonical.
- Do not duplicate existing items.
- Do not solve major mysteries.
- Do not create a final-answer clue unless explicitly required.
- The item must fit the setting, era, tone, and trigger.
- Use temp_id only.
- proposed_owner_id must be null unless the item is clearly generated for a valid character ID.
- proposed_location_id must be null or one of valid_location_ids.
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
{{ data.generation_context }}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Valid character IDs:
{{ data.valid_character_ids }}

Valid location IDs:
{{ data.valid_location_ids }}

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

Hard rules:
- The entity is a pending proposal, not canonical.
- The entity must belong to or be discoverable within the current location unless constraints specify another location.
- Do not duplicate existing entities.
- type must be exactly one value from allowed_entity_types.
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
{{ data.generation_context }}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Allowed entity types:
{{ data.allowed_entity_types }}

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

Hard rules:
- The world entry is a pending proposal, not canonical.
- content must be a complete factual sentence, not a title.
- Do not duplicate existing world entries.
- Do not contradict canonical state.
- Do not solve major mysteries unless explicitly required.
- scope may contain only valid_character_ids, 0 for everyone, or -1 for hidden GM-only.
- visibility must be exactly one value from allowed_visibility_values.
- narration_permission must be exactly one value from allowed_narration_permissions.
- recall_type must be exactly one value from allowed_recall_types.
- If recall_type is KEYWORD, include useful keywords.
- If recall_type is CHAINED, include chained_ids only from existing_world_entries.
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
{{ data.generation_context_json }}

## Trigger
{{ data.trigger }}

## Constraints
{% for c in data.constraints %}
- {{ c }}
{% endfor %}

Valid character IDs:
{{ data.valid_character_ids }}

Allowed visibility values:
{{ data.allowed_visibility_values }}

Allowed narration permissions:
{{ data.allowed_narration_permissions }}

Allowed recall types:
{{ data.allowed_recall_types }}

Existing world entry IDs:
{% for e in data.existing_world_entries %}
- {{ e.id }}: {{ e.content }}
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

## Current state
Round: {{ data.state.round_number }}
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
- Do not leak private reasoning into narrator_constraints.
- reason_for_system is internal only.

Scheduling rules:
- Do not activate every character by default.
- Do not activate user-controlled characters unless explicitly delegated by user input.
- If wait_for_user=true, active_character_ids must be empty.
- Priority uses 0-100, where 100 is most urgent.
- If an NPC has already acted and previous resolver notes say the scene is waiting for user response,
  prefer wait_for_user=true.
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
Round: {{ data.state.round_number }}
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
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Briefing Builder Input

## Requested character IDs
{{ data.character_ids }}

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Current state
Round: {{ data.state.round_number }}
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
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
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
"""
            )
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

## Visible entities
{% for e in data.visible_entities %}
- Entity {{ e.id }}: {{ e.name }}
  Type: {{ e.type }}
  Status: {{ e.status }}
  Interactions: {{ e.interactions | join(", ") }}
{% else %}
None.
{% endfor %}

## Present characters
{% for c in data.present_characters %}
- Character {{ c.id }}: {{ c.name }}
  User controlled: {{ c.user_controlled }}
  Public state: {{ c.public_state }}
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

## Priority order
Higher priority generally acts earlier:
{{ data.round_constraints.priority_order }}

## Recalled resolver-safe world entries
{% for e in data.recalled_world_entries %}
- Entry {{ e.id }}: {{ e.content }}
  Scope: {{ e.scope }}
  Visibility: {{ e.visibility }}
  Confidence: {{ e.confidence }}
{% else %}
None.
{% endfor %}

## Pending generated proposals
These are not canonical.
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

## Recent history
{{ data.recent_history_summary or "No recent history summary." }}

## Last narration
{{ data.last_narration or "No last narration." }}

## Previous resolver notes
{{ data.previous_resolver_notes or "No previous resolver notes." }}

# Required resolution

Resolve the attempted actions.

Detect conflicts, failures, blocked actions, and invalid assumptions.
Return ResolverOutput with mode="normal_action_resolution".
"""
            )
        ],
    )


@pytest.fixture
def mock_simulation(mock_director_profile,
                    mock_memory_agent_profile,
                    mock_character_agent_profile,
                    mock_resolver_agent_profile,
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
            world_generator=mock_world_generator_profile,
            resolver=mock_resolver_agent_profile,
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
