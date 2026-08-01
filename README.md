# World Simulation Engine

Language: English | [中文](README.zh.md)

[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=bugs)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine) [![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine) [![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine)

World Simulation Engine is an experimental, LLM-driven world simulator: a persistent world of characters, locations,
items, and events that advances turn by turn, with every character (whether on-screen or not) acted out by an LLM
agent grounded in structured, queryable world state rather than a single free-flowing chat transcript. It exposes a
FastAPI backend backed entirely by Neo4j, and ships a React admin/interaction frontend for building worlds, wiring up
LLM connections, and chatting with a simulation.

This is a research/hobby project, not a production product — it exists to explore the design questions below, and
the codebase, prompts, and data model are all still evolving.

## What it explores

- **Time-constrained simulation.** Every character activity carries an expected duration and an interruptibility
  flag, and the simulation advances against an explicit `current_time` rather than one reply per message. Turns
  aren't just "the next chat message" — they're scheduled events that characters can be mid-way through, waiting on,
  or interrupted from.
- **Simulating on-scene *and* off-scene characters.** Characters the user isn't currently interacting with keep
  living: a background worker in `WorldSimulator` continues off-scene characters' activities between user turns
  (deciding, validating, and committing their actions independently), and the foreground pipeline only waits on that
  background work when a user action actually depends on it (e.g. moving into a location an off-scene character is
  mid-action in). The goal is a world that keeps moving, not a cast that freezes the instant the camera looks away.
- **Structured data as the source of truth, not prose.** World state — characters, locations, items, equipment,
  containers, events, intents, relationships, memories — is modeled as typed nodes/relationships in a graph database,
  not as an ever-growing block of narration the model has to re-read and re-infer facts from. Narration is generated
  *from* that committed structured state as a presentation layer, and is decoupled from the state itself, so how a
  turn is rendered to a given viewer can change independently of what actually happened.
- **Memory, truth, and agent separation for something closer to real feeling.** Each character's beliefs are scoped
  and private: `SubjectiveEntityClaim`s record one character's fallible beliefs about another entity (with an
  explicit stance — remembered, inferred, believed, doubted, denied, or known-mistaken), `EntityRelationship`s carry
  both an objective/public description and a private-per-observer one, and each character has a private `Emotion`
  vector (valence/arousal/dominance, with slow-moving baseline and fast-moving immediate components that decay over
  time) that is used only as a soft tone/risk constraint and is never disclosed across characters. Memory retrieval
  is bounded by a token budget rather than dumping full history into every prompt. Each pipeline stage (input
  interpretation, action validation, per-character action proposal, scene coordination, emotion/relationship/belief
  updates, narration, state commit, memory summarization) runs as its own scoped LLM agent, so one character's
  private context can't leak into another's decisions or into the narration.
- **Optimized for small, local models — not just frontier cloud models.** The pipeline is built assuming the model
  will sometimes get structured output wrong: `LlmService.invoke_structured_with_repair` re-prompts to repair
  malformed structured output, action proposals go through a bounded validation/rework loop instead of trusting the
  first draft, and schemas are written to tolerate common small-model quirks (e.g. emitting `null` instead of an
  all-zero delta). Every pipeline stage has its own LLM/embedding connection configuration, so cheap local models can
  be assigned per stage instead of requiring one large model for everything. Development has been tested primarily
  against Qwen3 35B running locally, specifically to validate that the design holds up on modest local hardware and
  not only on massive cloud-hosted models.

## Architecture at a glance

- **Backend** (`src/world_simulation_engine`): FastAPI app, Neo4j-backed `DatabaseService` (one store class per
  entity type, no ORM), a LangGraph-orchestrated simulation pipeline (`WorldSimulator` and its component stages), and
  provider-agnostic LLM/embedding services selected per connection config. Chat models support Ollama, OpenAI,
  Anthropic, OpenRouter, Google GenAI, Mistral AI, Cohere, Perplexity, Groq, DeepSeek, xAI, and Cloudflare;
  embeddings currently support Ollama and OpenAI.
- **Frontend** (`frontend/`): React + Vite admin/chat UI for managing worlds, connections, prompts, and simulations.

## Deployment

### Full stack via Docker Compose

```bash
docker compose up --build
```

This builds the frontend, builds the backend, and serves both behind nginx in a single image (`Dockerfile`), plus a
`neo4j` container with the `apoc` and `graph-data-science` plugins enabled. The app is published on `9798` (proxied
to nginx on `80` inside the container); Neo4j's browser/bolt ports (`7474`/`7687`) are also published.

**Change the default Neo4j credentials** (`neo4j`/`password` in `docker-compose.yml`) before deploying anywhere
non-local.

### Backend + Neo4j only (for local frontend/backend development)

```bash
docker compose -f docker-compose.dependencies.yml up -d
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797 --reload
```

### Configuration

The backend is configured entirely through `WSE_`-prefixed environment variables (see
`src/world_simulation_engine/misc/config.py`), loadable from a `.env` file or a path given via `WSE_ENV_FILE`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `WSE_APP_HOST` / `WSE_APP_PORT` | `127.0.0.1` / `9797` | Bind address for the local dev server. |
| `WSE_LOGGING_LEVEL` | `INFO` | Log verbosity. |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI. |
| `WSE_NEO4J_USERNAME` / `WSE_NEO4J_PASSWORD` | `neo4j` / *(required)* | Neo4j credentials. |
| `WSE_DATA_FOLDER` | `data/storage` | Content-addressed storage location for media (images, custom prompts/workflows). |

LLM/embedding provider credentials and per-component model assignments are configured per-simulation at runtime
through the API/frontend (`ConnectionConfig`, chat/embed configs), not through environment variables. Install only
the provider extras you need, or use the `all-llm` optional dependency group in `pyproject.toml` for every supported
chat integration.

## Roadmap

### Done

- Graph-centric data model covering the full simulation domain: worlds, locations, landmarks, characters, background
  characters, items, equipment, containers, events, intents, memories, relationships, subjective beliefs, emotions,
  turns, media, and simulation/connection configuration.
- Input interpreter and action validator turning free-text user input into structured, validated actions.
- Per-character action proposal and a scene coordinator that resolves simultaneous/conflicting actions into an
  accepted timeline (including reaction handling for interrupted or contested actions).
- Time-based character scheduling and an asynchronous off-scene activity worker so non-present characters keep
  acting between user turns.
- Perspective resolver determining what each character can currently perceive.
- Memory retrieval and summarization with a bounded token budget, plus recall-aware intent management.
- Entity relationship management, including separate public/objective and private/per-observer descriptions.
- Private per-character emotion modeling (baseline + immediate vectors with decay) feeding tone/risk constraints
  without leaking across characters.
- Subjective entity claims: per-character, stance-qualified private beliefs about other entities.
- LLM output repair pipeline (structured-output repair, validation rework loop) aimed at tolerating small local
  models.
- Turn presentation decoupled from the underlying generated/committed state, rendered per viewer.
- Configurable LLM/embedding connections per simulation and per pipeline component, with chat backends for Ollama,
  OpenAI, Anthropic, OpenRouter, Google GenAI, Mistral AI, Cohere, Perplexity, Groq, DeepSeek, xAI, and
  Cloudflare.
- Media management with content-addressed storage, including cover images and per-simulation prompt/workflow
  overrides.
- GraphStateSnapshot-backed regeneration/continuation of a simulation run.
- Structured audit log and Langfuse tracing integration for debugging generation runs, plus author attribution for
  authored content.
- React frontend covering world/simulation management, LLM connection setup, prompt/workflow overrides, media, and a
  simulation chat interface.

### Planned

- ComfyUI based image generation pipeline for character/location/item portraits and scene illustrations.
- Event hooks and bound encounters/events.
- Scripting, guided generation and plots.
- LLM fine-tuning and/or LoRA support for character-specific behavior.
- OOC commands.
