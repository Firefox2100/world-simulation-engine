# Frontend

The frontend is a React + Vite application under `frontend/`. It is an admin and interaction UI rather than a thin
chat box. The user can create worlds, manage simulations, configure providers, edit prompts, inspect media, and chat
with a running simulation from the same application.

## Routes

The React router defines these main routes:

| Route | Page | Purpose |
| --- | --- | --- |
| `/` | `SimulationPage` | Simulation list and entry point. |
| `/simulations/:simulationId` | `SimulationChatPage` | Main simulation interaction view, details, configuration tabs, media generation, prompt overrides, and chat. |
| `/worlds` | `WorldPage` | World list and world creation/editing workflows. |
| `/authors` | `AuthorsPage` | Author records. |
| `/media` | `MediaPage` | Uploaded/generated media management. |
| `/prompts` | `PromptsPage` | Prompt media creation and editing. |
| `/connections` and `/configurations` | `ConfigurationsPage` | Provider connections and reusable model configs. |

## API shape

Frontend API modules mirror backend resources. They call the FastAPI backend through JSON requests and media
endpoints. Configuration pages use the same API surface as the simulation editors, so reusable configs and
per-world/per-simulation assignments stay consistent.

## Simulation view

`SimulationChatPage` combines several responsibilities:

- shows turn presentation blocks instead of raw model output,
- sends user input to the generation API,
- follows generation status and run output,
- exposes simulation tabs for config assignments, image generation, TTS generation, prompt overrides, observability,
  and entity details,
- triggers manual media generation when configured,
- shows generated scene, character, location, item, and voice media where available.

The important frontend boundary is that it displays committed turns and presentation records. It does not decide
whether a proposed action is true, valid, or committed. Those decisions stay in the backend generation graph.

## Configuration editors

The frontend has two levels of configuration UI:

- global reusable configs under **Configurations**,
- world or simulation assignment matrices inside creation/edit/detail workflows.

This matches the backend model: provider connections and model configs are reusable nodes; world and simulation
records link to those configs by component.
