# Create the First World and Start a Simulation

This quick start assumes the backend and frontend are already running. If not, start with [Fast local deploy on Windows from source](windows-source.md).

## 1. Create provider configs

Open **Configurations** and create the minimum runtime configs:

1. **Connection**: create a connection for your LLM provider. For local Ollama, use `http://localhost:11434` as the base URL.
2. **LLM config**: choose that connection, enter a model id, and keep the first run simple with default generation settings.
3. **Embedding config**: choose an embedding-capable provider. Current embedding providers are Ollama, OpenAI, AI21, Google GenAI, Mistral AI, Cohere, Perplexity, and Cloudflare Workers AI.

You can add image, TTS, or STT configs later. They are optional for the first simulation.

## 2. Create an author

Open **Authors** and create one author profile. Worlds are attributed to authors, so create this before the world.

## 3. Create a world

Open **Worlds** and create a world with:

- A short name.
- A compact description of the setting.
- The author you just created.

After saving, open the world detail page.

## 4. Add enough world state

For the first run, keep the world tiny:

1. Add one location.
2. Add one player-facing character in that location.
3. Optionally add one background character, item, landmark, or piece of equipment.

Small worlds are easier to debug because every generated action can be traced back to a small amount of structured state.

## 5. Assign model configs

In the world configuration area, assign:

- Your LLM config to the core LLM components.
- Your embedding config to embedding-capable components.

At minimum, make sure the narrator, input interpreter, action validator, character simulator, scene coordinator, state committer, memory summarizer, and perspective resolver have usable LLM configs.

## 6. Start a simulation

From the world page, create a simulation. Open the simulation chat page, then send a simple first action, such as:

```text
I look around and greet the nearest person.
```

The simulation will interpret the input, validate the action, simulate character responses, commit state changes, and render the turn.

## 7. If the first turn fails

Check the likely causes in this order:

1. The backend terminal has provider authentication or connection errors.
2. The selected LLM model id is not available on the provider.
3. The embedding model dimension changed after memories were created.
4. A required component has no assigned LLM or embedding config.
5. The model returned malformed structured output too many times.

After the first world runs, add media generation, voice, prompt overrides, and richer background state one piece at a time.
