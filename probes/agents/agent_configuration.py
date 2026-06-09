import os

from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model import LlmConnectionProfile, OllamaAgentBackendConfiguration, PromptMessage, \
    EmbeddingProfile, DirectorAgentProfile, WorldGeneratorAgentProfile, MemoryAgentProfile
from world_simulation_engine.service import EmbeddingService, WorldGeneratorAgent, DirectorAgent, \
    MemoryAgent


OLLAMA_URL = str(os.getenv("EXP_OLLAMA_URL"))
OLLAMA_MODEL = str(os.getenv("EXP_OLLAMA_MODEL"))
OLLAMA_MODEL_EMBED = str(os.getenv("EXP_OLLAMA_MODEL_EMBED"))


embedding_service = EmbeddingService(
    profile=EmbeddingProfile(
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url=OLLAMA_URL,
        ),
        model=OLLAMA_MODEL_EMBED,
        dimensions=1024,
        context_window=8192,
    ),
)

world_generator_agent = WorldGeneratorAgent(
    profile=WorldGeneratorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
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
    ),
)

director_agent = DirectorAgent(
    profile=DirectorAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
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
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.long_term_history_summary or "No long-term history summary." }}

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
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history
{{ data.long_term_history_summary or "No long-term history summary." }}

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
    ),
)

memory_agent = MemoryAgent(
    profile=MemoryAgentProfile(
        backend_configuration=OllamaAgentBackendConfiguration(
            connection=LlmConnectionProfile(
                id=1,
                provider=LlmProvider.OLLAMA,
                base_url=OLLAMA_URL,
            ),
            model=OLLAMA_MODEL,
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
{{ data.recent_history_summary or "No recent public history summary." }}

## Long-term public history summary
{{ data.long_term_history_summary or "No long-term public history summary." }}

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
    ),
)
