# Media and Configuration

## Purpose

Media nodes connect graph entities to uploaded, generated, prompt, workflow, image, and voice assets. Configuration nodes connect worlds and simulations to model providers and runtime generation behavior.

## Important properties

| Entity | Important properties |
| --- | --- |
| `Media` | `id`, `type`, `title`, `hash`, `filename`, `created_at` |
| `PromptMediaFile` | media fields plus `prompt_name`, `language`, `component` |
| `WorkflowMediaFile` | media fields plus `workflow_name` |
| `GeneratedImageMediaFile` | generation type, component, workflow name, canonical and transient tags/descriptions, negative prompt |
| `GeneratedVoiceMediaFile` | presentation block id, turn id, character id, text, voice reference |
| `ConnectionConfig` | `id`, `type`, `name`, `base_url`, `api_key` |
| Model config nodes | provider-specific chat, embedding, image, TTS, and STT settings |
| Generation config nodes | `ImageGenerationConfig.mode`, `fallback_turns`; `TtsGenerationConfig.mode`, browser autoplay, narrator voice fields |

## Relationships

- `(:Entity)-[:HAS_MEDIA]->(:Media)`
- `(:Entity)-[:HAS_COVER]->(:Media)`
- `(:Entity)-[:HAS_IMAGE]->(:GeneratedImageMediaFile)`
- `(:Turn)-[:GENERATES_IMAGE]->(:GeneratedImageMediaFile)`
- `(:TurnPresentationBlock)-[:GENERATES_IMAGE]->(:GeneratedImageMediaFile)`
- `(:TurnPresentationBlock)-[:HAS_VOICE]->(:GeneratedVoiceMediaFile)`
- `(:World|Simulation)-[:USE_PROMPT]->(:PromptMediaFile)`
- `(:World|Simulation)-[:USE_WORKFLOW]->(:WorkflowMediaFile)`
- `(:World|Simulation)-[:USES {component}]->(:ChatModelConfig|EmbedModelConfig|ImageModelConfig|TtsModelConfig|SttModelConfig)`
- `(:ModelConfig)-[:USES]->(:ConnectionConfig)`
- `(:Simulation)-[:HAS_IMAGE_GENERATION_CONFIG]->(:ImageGenerationConfig)`
- `(:Simulation)-[:HAS_TTS_GENERATION_CONFIG]->(:TtsGenerationConfig)`
- `(:Character)-[:HAS_CONFIG]->(:CharacterTtsConfig)`
- `(:CharacterTtsConfig)-[:USE_CONFIG]->(:TtsModelConfig)`

## Ownership and lifecycle

Media can be attached to worlds, simulations, characters, background characters, locations, landmarks, items, stacks, equipment, and containers. Cover media is a single selected media relationship per entity. Prompt and workflow media can be inherited from a world by a simulation unless the simulation has an override.

Connection configs are reusable provider connection records. Model configs point to connection configs. Worlds and simulations then select model configs per component with the `component` relationship property.

## Creation and deletion behaviour

Uploading media creates a `Media` node, stores the file metadata, and optionally attaches it to a source entity. Assigning cover media replaces the previous `HAS_COVER` relationship. Removing media from an entity deletes the relationship and can delete the media node when it is no longer used by that source flow.

Creating prompt and workflow media stores the uploaded definition as specialized media. Assigning prompts or workflows replaces the matching component assignment for the world or simulation.

Deleting a connection or model config removes the config node and its `USES` links. Deleting a simulation removes its generation configs, jobs, snapshots, and media assignments owned by that simulation.

## Invariants

- Media identity is content-addressed with `hash` and named with `filename`.
- Cover assignment is singular for an entity.
- A model config should point to a compatible `ConnectionConfig`.
- World-level prompt, workflow, and model assignments are defaults; simulation-level assignments override them.
- Character TTS config can override the selected TTS backend for one character.
- Generated voice media should point back to the presentation block and turn that requested it.

## Example Cypher representation

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (mira:Character {id: "char-1"})
CREATE (connection:ConnectionConfig {
  id: "conn-1",
  type: "openai",
  name: "OpenAI",
  base_url: null
})
CREATE (llm:OpenAiChatModelConfig {
  id: "llm-1",
  name: "Narration model",
  model: "gpt-4.1"
})
CREATE (portrait:Media {
  id: "media-1",
  type: "image",
  title: "Mira portrait",
  hash: "sha256:...",
  filename: "mira.png",
  created_at: datetime()
})
CREATE (llm)-[:USES]->(connection)
CREATE (simulation)-[:USES {component: "narrator"}]->(llm)
CREATE (mira)-[:HAS_MEDIA]->(portrait)
CREATE (mira)-[:HAS_COVER]->(portrait);
```

## Related API endpoints

- `/media`, `/media/{media_id}`
- `/{entity}/{entity_id}/media`, `/{entity}/{entity_id}/media-connections`, `/{entity}/{entity_id}/cover-image` for worlds, simulations, characters, background characters, locations, landmarks, items, stacks, equipment, and containers
- `/prompts`, `/prompts/{media_id}`, `/prompts/builtin/{language}/{prompt_name}`, `/prompts/{media_id}/messages`
- `/worlds/{world_id}/prompt-connections`, `/simulations/{simulation_id}/prompt-connections`, `/simulations/{simulation_id}/prompts/{language}/{prompt_name}`
- `/workflows`, `/workflows/{media_id}`, `/workflows/builtin/{workflow_name}`, `/workflows/{media_id}/data`
- `/worlds/{world_id}/workflow-connections`, `/simulations/{simulation_id}/workflow-connections`, `/simulations/{simulation_id}/workflows/{workflow_name}`
- `/config/connections`, `/config/llm`, `/config/embeddings`, `/config/images`, `/config/tts`, `/config/stt`
- `/worlds/{world_id}/{llm|embedding|tts|image}-connection`
- `/simulations/{simulation_id}/{llm|embedding|tts|image}-connection`
- `/characters/{character_id}/tts-config`
- `/characters/{character_id}/generate-image/state`, `/locations/{location_id}/generate-image/state`, `/items/{item_id}/generate-image/state`

