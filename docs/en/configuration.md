# Configuration

World Simulation Engine has two configuration layers:

1. **Startup configuration** is read from environment variables. These settings let the backend start, find Neo4j, write media files, and set service-wide limits.
2. **Runtime service configuration** is managed in the web interface. These settings decide which model providers, prompts, image services, and voice services a world or simulation uses.

The first layer belongs in `.env`, Docker Compose, or your shell. The second layer is stored in Neo4j and can be changed without editing environment variables.

## Configuration sections

- [Environment variables](configuration/environment.md): backend startup settings and service-wide limits.
- [Connections](configuration/connections.md): reusable provider endpoints and API keys.
- [LLM model configs](configuration/llm.md): chat model profiles and per-provider generation settings.
- [Embedding configs](configuration/embedding.md): retrieval and memory embedding profiles, including the expanded embedding provider support.
- [Image generation configs](configuration/image.md): ComfyUI image profiles and image generation behavior.
- [TTS configs](configuration/tts.md): AllTalk backend configs and per-simulation voice generation.
- [STT configs](configuration/stt.md): whisper.cpp speech recognition settings.

In practice, start with environment variables, create provider connections, create model/media configs, then assign those configs to worlds or simulations.

## Runtime hierarchy

Runtime settings are intentionally reusable:

- **Connection**: the network endpoint and optional API key for a provider.
- **Model config**: a reusable model profile for one service type, such as an LLM model with sampling settings or a ComfyUI image config with image dimensions.
- **World assignment**: default model, image, embedding, TTS, and prompt assignments for a world.
- **Simulation assignment**: overrides for a specific simulation. Use this when one run needs different models, image behavior, or prompts from the world default.

Open the web interface, then go to **Configurations** or **Connections** from the main navigation.

<!-- Screenshot placeholder: Configurations page showing tabs for Connections, Embeddings, LLMs, TTS, Images, and STT. -->
