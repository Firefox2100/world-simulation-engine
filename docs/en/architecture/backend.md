# Backend

The backend is a FastAPI application in `src/world_simulation_engine`. It exposes resource routers, owns application
lifetime setup, and holds the long-lived services used by generation runs.

## Startup

`create_app()` registers routers. The lifespan function performs the important runtime wiring:

1. Configure event logging.
2. Open an async Neo4j driver from `WSE_NEO4J_*` environment variables.
3. Create `DatabaseService`.
4. Create `StorageService` from `WSE_DATA_FOLDER`.
5. Mark interrupted generation jobs as failed after restart.
6. Create prompt and workflow loaders.
7. Create `WorldSimulator`.
8. Store these services on `app.state`.
9. Shutdown background simulator work and close Neo4j on application stop.

## Router groups

Routers are deliberately resource-shaped:

| Router area | Responsibilities |
| --- | --- |
| Worlds and simulations | Create worlds, create simulations, import/export worlds, start generation, stream runs, inspect snapshots. |
| Domain entities | Characters, background characters, locations, landmarks, items, equipment, containers, intents, events, memories, variables. |
| Authors | Author profiles, and attributing a world (or other authored content) to one. |
| Story scripting | Trigger CRUD and status control (`trigger_router`) for scripted cues that drive story progression. |
| SillyTavern import | Parse an uploaded card, stream the extraction pipeline over SSE, then commit the reviewed result as a new `World` (`sillytavern_import_router`). |
| Configuration | Provider connections, LLM/embedding/image/TTS/STT configs, world and simulation component assignments. |
| Media, prompts, workflows | Upload and link media, prompt JSON, workflow JSON, cover images, prompt/workflow overrides. |
| Turns and presentation | Turn records, rendered presentation blocks, generated image/audio segment endpoints, archived turn versions and reverting to one. |
| Speech recognition | STT transcription endpoint for configured speech recognition backends. |

The simulation router starts generation with `WorldSimulator.start_generation()`. It can then stream graph updates
from `WorldSimulator.stream_generation()` so the frontend can update while the background job runs.

## Generation run ownership

`WorldSimulator` prevents concurrent writes to the same simulation with an active generation job and per-simulation
run lock. This matters because a generation can apply graph mutations, advance time, create memories, schedule
off-scene work, and start media side effects.

The backend stores generation jobs for idempotency and recovery. If the application restarts mid-generation, startup
marks incomplete jobs as failed rather than silently pretending they completed.

## Provider boundary

Backend components do not keep provider credentials in environment variables. They load provider connections and
model configs from Neo4j at runtime. The service layer then adapts those configs to the relevant external service:

- chat and structured output through `LlmService`,
- embeddings through `EmbedService`,
- images through ComfyUI image services,
- voice through AllTalk TTS services,
- speech recognition through whisper.cpp STT services.

This keeps deployment configuration separate from simulation behavior configuration.
