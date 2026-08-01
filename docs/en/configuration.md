# Configuration

World Simulation Engine has two configuration layers:

1. **Startup configuration** is read from environment variables. These settings let the backend start, find Neo4j, write media files, and set service-wide limits.
2. **Runtime service configuration** is managed in the web interface. These settings decide which model providers, prompts, image services, and voice services a world or simulation uses.

The first layer belongs in `.env`, Docker Compose, or your shell. The second layer is stored in Neo4j and can be changed without editing environment variables.

## Startup configuration

The backend reads `WSE_`-prefixed variables through `src/world_simulation_engine/misc/config.py`. By default it loads them from `.env`; set `WSE_ENV_FILE` if you want to use a different file.

```shell
WSE_ENV_FILE=/path/to/local.env uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

For Docker Compose, the provided `docker-compose.yml` passes `.env` into the application container:

```yaml
services:
  app:
    env_file:
      - .env
```

### Required variables

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_NEO4J_PASSWORD` | Required | Password used to connect to Neo4j. The Docker Compose dependency example uses `neo4j/password`; change it before any non-local use. |

### Common variables

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_APP_HOST` | `127.0.0.1` | Host used by the local start script. When running behind Docker/nginx, the container entrypoint and proxy decide the externally exposed host. |
| `WSE_APP_PORT` | `9797` | Port used by the local start script. The full Docker Compose stack exposes the web app on host port `9798`. |
| `WSE_LOGGING_LEVEL` | `INFO` | Python logging level. Supported values are `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, and `NOTSET`. |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Bolt URI for Neo4j. Use the host and port visible from the backend process or container. |
| `WSE_NEO4J_USERNAME` | `neo4j` | Username used to connect to Neo4j. |
| `WSE_DATA_FOLDER` | `data/storage` | Content-addressed storage folder for uploaded media, generated images, prompt overrides, and workflow files. In Docker, this is normally mounted under `/app/data/storage`. |

### TTS service limits

These variables do not choose a TTS provider. They only control backend behavior once TTS is configured in the interface.

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_TTS_MAX_CONCURRENCY` | `3` | Maximum number of concurrent outbound TTS generation requests. Lower this if the TTS backend becomes unstable under load. |
| `WSE_TTS_MEDIA_RETENTION_TURNS` | `50` | Number of most-recent turns whose generated voice media are retained per simulation before older generated files are pruned. |

### Example `.env`

```dotenv
WSE_LOGGING_LEVEL=INFO
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
WSE_TTS_MAX_CONCURRENCY=3
WSE_TTS_MEDIA_RETENTION_TURNS=50
```

!!! warning "Local-only security model"
    The application is designed for local use. It does not include authentication or multi-user isolation, and prompts or world content may be sent to configured external model providers.

### What is not configured by environment variables

Do not put LLM, embedding, image, TTS, STT, prompt, or per-component model assignments in `.env`. Those are runtime service settings managed through the web interface and stored in Neo4j.

## Runtime service configuration

Open the web interface, then go to **Configurations** or **Connections** from the main navigation. This area defines reusable provider connections and model profiles. Worlds and simulations then assign those profiles to the components that need them.

<!-- Screenshot placeholder: Configurations page showing tabs for Connections, Embeddings, LLMs, TTS, Images, and STT. -->

### Configuration hierarchy

Runtime settings are intentionally reusable:

- **Connection**: the network endpoint and optional API key for a provider, such as Ollama, OpenAI-compatible chat, ComfyUI, AllTalk, or whisper.cpp.
- **Model config**: a reusable model profile for one service type, such as an LLM model with sampling settings or a ComfyUI image config with image dimensions.
- **World assignment**: default model, image, embedding, TTS, and prompt assignments for a world.
- **Simulation assignment**: overrides for a specific simulation. Use this when one run needs different models, image behavior, or prompts from the world default.

In practice, create provider connections first, create model configs second, then assign those configs to worlds or simulations.

## Connections

Connections contain the shared provider access details:

| Field | Description |
| --- | --- |
| `type` | Provider type: `ollama`, `openai`, `comfyui`, `alltalk`, or `whispercpp`. |
| `name` | Display name shown in dropdowns. Use names that describe the endpoint, not just the provider. |
| `base_url` | Provider base URL. Local providers usually need this; official or SDK-default providers may leave it empty. |
| `api_key` | Optional API key. Leave it empty for local/self-hosted providers that do not require one. |

<!-- Screenshot placeholder: New/Edit Connection modal with provider type, name, base URL, and API key fields. -->

Recommended examples:

| Provider | Typical local base URL |
| --- | --- |
| Ollama | `http://localhost:11434` |
| ComfyUI | `http://localhost:8188` |
| AllTalk | AllTalk V2 server URL visible from the backend |
| whisper.cpp | whisper.cpp `examples/server` URL visible from the backend |

When running the backend in Docker, `localhost` means "inside the application container". Use a Docker service name, `host.docker.internal`, or another reachable host address as appropriate for your setup.

## LLM model configs

Use the **LLMs** tab to create chat model configs. Each config points to an Ollama or OpenAI-compatible connection and stores the model identifier plus generation parameters.

<!-- Screenshot placeholder: LLM config editor with provider connection, model, temperature, context window, reasoning, and stop token fields. -->

Common fields:

| Field | Description |
| --- | --- |
| `name` | Display name for this LLM profile. |
| `model` | Provider model identifier, for example an Ollama model name or OpenAI-compatible model id. |
| `temperature` | Sampling temperature. Higher values are more varied; lower values are more deterministic. |
| `context_window` | Context size used when composing prompts. |
| `seed` | Optional seed for providers that support deterministic sampling. |
| `reasoning` | Optional reasoning control. It may be `true`, `false`, or a level such as `low`, `medium`, or `high`, depending on provider support. |
| `stop_tokens` | Optional newline-separated stop tokens. |

Ollama configs also expose provider-specific controls such as `mirostat`, `mirostat_eta`, `mirostat_tau`, `num_predict`, `repeat_penalty_window`, and `repeat_penalty`.

## Embedding configs

Use the **Embeddings** tab to create embedding profiles. Embeddings are used for retrieval and memory lookup.

<!-- Screenshot placeholder: Embedding config editor with provider connection, model, dimension, and context window. -->

| Field | Description |
| --- | --- |
| `name` | Optional display name. If omitted, the UI falls back to the model identifier. |
| `model` | Embedding model identifier. |
| `dimension` | Optional output vector dimension for providers/models that support selecting it. |
| `context_window` | Ollama-only optional context window. |

Use one embedding model consistently for a world once data has been embedded. Switching dimensions or embedding families after a world already has memories may require rebuilding stored embeddings.

## Assigning LLM and embedding configs

After creating model configs, assign them to a world or simulation from the world editor or simulation detail page.

<!-- Screenshot placeholder: World configuration assignment matrix for LLM and embedding components. -->

<!-- Screenshot placeholder: Simulation configuration tab showing LLM and embedding override rows. -->

LLM-capable simulation components:

| Component | Purpose |
| --- | --- |
| `input_interpreter` | Converts user input into structured candidate actions. |
| `action_validator` | Checks whether proposed actions are valid in the current world state. |
| `character_simulator` | Proposes character actions and reactions. |
| `scene_coordinator` | Resolves simultaneous or conflicting actions into a committed timeline. |
| `state_committer` | Converts resolved events into graph state mutations. |
| `memory_summarizer` | Builds memory summaries from events and turns. |
| `perspective_resolver` | Determines what each character can perceive. |
| `narrator` | Renders committed state into user-facing narration. |

Image-related chat components:

| Component | Purpose |
| --- | --- |
| `character_image_generator` | Builds prompts for character state images. |
| `character_portrait_image_generator` | Builds prompts for character portraits. |
| `location_image_generator` | Builds prompts for location images. |
| `item_image_generator` | Builds prompts for item images. |
| `scene_image_generator` | Builds prompts for scene illustrations. |
| `turn_image_trigger` | Decides whether a turn is significant enough to auto-generate an image. |

Embedding-capable components use embedding profiles where retrieval is needed, especially character simulation and memory workflows.

## Prompt configuration

Prompts are managed separately from model configs. Open the **Prompts** area to create or upload reusable prompt media, then assign them on a world or simulation under the **Prompts** section.

<!-- Screenshot placeholder: Prompts page showing uploaded or created prompt media. -->

<!-- Screenshot placeholder: Prompt assignment matrix for a world or simulation. -->

Each prompt is a list of messages. Every message has:

| Field | Description |
| --- | --- |
| `role` | Message role: `system`, `user`, `assistant`, or `tool`. |
| `content` | Prompt text. Jinja2 templating is supported. |

Prompt assignments can be scoped by language, prompt name, and component. This lets a simulation override only the prompts it needs while inheriting defaults for everything else.

Common prompt groups in the UI include:

| Role group | Prompt keys |
| --- | --- |
| Director | `generation_prompt`, `planning_prompt` |
| Memory | `briefing_prompt`, `summary_prompt` |
| Character | `action_prompt`, `reaction_prompt` |
| Resolver | `resolve_character_prompt`, `resolve_reaction_prompt`, `resolve_user_prompt` |
| Committer | `mutation_prompt`, `validation_prompt` |
| Narrator | `narrate_resolved_turn_prompt`, `narrate_user_input_failure_prompt`, `narrate_wait_for_user_prompt` |
| World generator | `location_generation_prompt`, `item_generation_prompt`, `equipment_generation_prompt`, `entity_generation_prompt`, `world_entry_generation_prompt`, `generation_package_prompt` |

Prompt changes can strongly alter simulation behavior. Keep a working baseline prompt set and make focused overrides for experiments.

## Image generation configuration

Image generation uses both an image service config and an LLM chat config:

- The image config sends the final prompt to the image backend, currently ComfyUI.
- The chat config builds image prompts from world state, character state, or narration.

Use the **Images** tab in **Configurations** to create reusable ComfyUI image model configs.

<!-- Screenshot placeholder: Image model config editor with ComfyUI connection, model, VAE, CLIP, dimensions, seed, steps, and CFG. -->

ComfyUI image fields:

| Field | Description |
| --- | --- |
| `model` | Optional checkpoint/model name. |
| `vae` | Optional VAE model name. |
| `clip` | Optional CLIP model name. |
| `image_width` / `image_height` | Optional requested image dimensions. |
| `seed` | Optional deterministic seed. |
| `steps` | Optional generation step count. |
| `cfg` | Optional classifier-free guidance value. |

Assign image configs to world or simulation image components:

| Component | Purpose |
| --- | --- |
| `character_image_generator` | Character state/cover images. |
| `character_portrait_image_generator` | Character portrait images. |
| `location_image_generator` | Location images. |
| `item_image_generator` | Item images. |
| `scene_image_generator` | Turn or scene illustrations. |

<!-- Screenshot placeholder: Simulation Image Generation tab showing image model assignments and generation behavior settings. -->

Per-simulation image generation behavior is controlled by `ImageGenerationConfig`:

| Field | Description |
| --- | --- |
| `mode` | `manual`, `auto`, or `always`. Manual only generates on request. Auto uses a significance check and fallback interval. Always generates every turn. |
| `fallback_turns` | In `auto` mode, force an image after this many turns without one. |

For automatic turn images, make sure both `scene_image_generator` and `turn_image_trigger` have suitable chat model assignments, and that `scene_image_generator` also has an image model assignment.

## TTS and STT configuration

Voice services are optional, but they follow the same connection/profile/assignment pattern.

### TTS

Use the **TTS** tab to create AllTalk backend configs. The shared backend config controls engine-level settings; narrator and character voices are selected separately.

<!-- Screenshot placeholder: TTS config editor with AllTalk connection, engine status, text filtering, language, speed, temperature, and playback fields. -->

Per-simulation TTS generation settings:

| Field | Description |
| --- | --- |
| `mode` | `manual` or `auto`. Manual generates audio on demand. Auto voices turn narration/speech after the turn is committed. |
| `autoplay_in_browser` | When enabled with auto mode, the frontend plays generated segments in sequence in the browser. |
| `narrator_voice` | Voice used for narration and unattributed speech. |
| `rvc_narrator_voice` | Optional RVC model for narrator voice conversion. |
| `rvc_narrator_pitch` | Optional narrator RVC pitch adjustment from `-24` to `24`. |

Character-specific voice selection lives on each character's TTS config and can point back to a shared TTS backend.

### STT

Use the **STT** tab to configure whisper.cpp HTTP server connections for speech recognition.

<!-- Screenshot placeholder: STT config editor with whisper.cpp connection, language, translate, temperature, and initial prompt fields. -->

Fields include language, translate-to-English behavior, decoding temperature, fallback temperature increment, and an optional initial prompt for domain vocabulary.

## Recommended setup order

1. Start Neo4j and the backend with a valid `.env`.
2. Open the web interface.
3. Create provider connections for your local or remote services.
4. Create LLM and embedding model configs.
5. Create image, TTS, or STT configs if you plan to use those features.
6. Assign LLM and embedding configs to the world.
7. Assign image and voice configs only where you want media generation.
8. Add prompt overrides last, after the baseline simulation runs successfully.

This order keeps startup problems separate from model or prompt problems: first prove the app can run, then prove each service connection works, then tune the simulation behavior.
