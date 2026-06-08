import os

from probes.agents.example_simulation import example_simulation
from world_simulation_engine.misc.enums import LlmProvider, MessageRole
from world_simulation_engine.model import LlmConnectionProfile, OllamaAgentProfile, PromptMessage, \
    EmbeddingProfile
from world_simulation_engine.service import EmbeddingService, WorldGeneratorAgent, DirectorAgent, \
    BriefingAgent


OLLAMA_URL = os.getenv("EXP_OLLAMA_URL")
OLLAMA_MODEL = os.getenv("EXP_OLLAMA_MODEL")
OLLAMA_MODEL_EMBED = os.getenv("EXP_OLLAMA_MODEL_EMBED")


embedding_service = EmbeddingService(
    profile=EmbeddingProfile(
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url=OLLAMA_URL,
        ),
        model=OLLAMA_MODEL_EMBED,
        dimensions=1024,
    ),
)

world_generator_agent = WorldGeneratorAgent(
    profile=OllamaAgentProfile(
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url=OLLAMA_URL,
        ),
        model=OLLAMA_MODEL,
        temperature=0.4,
        context_window=65536,
        prompts=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are a world generation tool for a role-play simulation.

You create proposed world content only. You do not commit canonical state.

You may generate:
- locations
- entities
- items
- world entries
- minor characters
- environmental discoveries

Rules:
- Generated content must fit the existing world tone, time period, location, and mystery structure.
- Do not solve major mysteries unless explicitly requested.
- Do not contradict supplied canonical facts.
- If generating clues, prefer partial, ambiguous, or actionable clues.
- Use temporary IDs only.
- Mark generated content as pending/proposed.
- Include a commit_policy for resolver handling.
- Do not narrate.
- Do not decide whether the player or NPC succeeded.
- Do not expose hidden GM-only truth unless the request explicitly allows GM-side generation.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
Context:
{{ data["context"] }}

Trigger:
{{ data["trigger"] }}

Constraints:
{{ data["constraints"] }}
"""
            )
        ],
    ),
    entity_types=example_simulation.data_preset.entity_types.keys(),
)

director_agent = DirectorAgent(
    profile=OllamaAgentProfile(
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url=OLLAMA_URL,
        ),
        model=OLLAMA_MODEL,
        temperature=0.4,
        context_window=65536,
        prompts=[
            PromptMessage(
                role=MessageRole.SYSTEM,
                content="""
You are the Director/Scheduler for a multi-agent role-play simulation.

Your job:
- decide which present non-user characters should act now;
- optionally call world generation tools when concrete unknown content is needed;
- provide resolver and narrator constraints.

You are not the narrator.
You are not the resolver.
You do not write character briefings.
You do not decide whether actions succeed.
You do not commit world state.
You do not write exact dialogue.

Privacy rules:
- You may use private states, private tasks, and private motives to decide activation.
- If private data influenced activation, mark private_motive_used=true.
- Do not generate text intended for character agents.
- Do not reveal private reasoning in narrator_constraints.
- reason_for_system is for internal orchestration only.

World generation rules:
- Use generation tools only when concrete unknown content is needed now.
- Generated content is pending only.
- Include tool results in pending_generated_proposals.
- The resolver decides whether generated proposals become canonical.

Scheduling rules:
- Do not activate every character by default.
- Do not activate user-controlled characters unless explicitly delegated.
- If wait_for_user=true, active_character_ids must be empty.
- Priority uses 0-100, where 100 is most urgent.

Return only DirectorOutput.
"""
            ),
            PromptMessage(
                role=MessageRole.USER,
                content="""
# Director Input

## Simulation
Name: {{ data.simulation.name }}
Description:
{{ data.simulation.description }}

## Current state
Round: {{ data.state.round_number }}
Time: {{ data.state.time_label }}
Current scene/location ID: {{ data.state.scene }}

State summary:
{{ data.state.state }}

## User input
{{ data.user_input or "No explicit user input. Passive continuation requested." }}

## Last narration
{{ data.last_narration or "No previous narration." }}

## Recent history summary
{{ data.recent_history_summary or "No recent history summary." }}

## Long-term history summary
{{ data.long_term_history_summary or "No long-term history summary." }}

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

## Present characters
{% for c in data.present_characters %}
- Character {{ c.id }}: {{ c.name }}
User controlled: {{ c.user_controlled }}
Description: {{ c.description }}
Public state: {{ c.public_state }}
Private state, Director-only: {{ c.private_state }}
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
No recalled world entries.
{% endfor %}

## Relevant tasks
These may include private tasks. Use them only for activation decisions.
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
No relevant tasks.
{% endfor %}

## Pending generated proposals
{% for p in data.pending_generated_proposals %}
- {{ p }}
{% else %}
None.
{% endfor %}

# Required decision

Select which NPCs should act now.

Do not leak private information.
Do not activate user-controlled characters unless explicitly delegated.
"""
            ),
        ],
    ),
)

briefing_agent = BriefingAgent(
    profile=OllamaAgentProfile(
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url=OLLAMA_URL,
        ),
        model=OLLAMA_MODEL,
        temperature=0.4,
        context_window=65536,
        prompts=[
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
- Do not include Director private activation reasons unless they are present in the safe input.

Briefing rules:
- Build one briefing per requested character ID.
- If a requested character is missing from supplied characters, omit it and note the omission.
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

Build safe briefings for the requested character IDs only.
"""
            )
        ],
    ),
)
