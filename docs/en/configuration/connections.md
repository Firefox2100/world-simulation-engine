# Connections

Connections contain the shared provider access details used by LLM, embedding, image, TTS, and STT configs.

| Field | Description |
| --- | --- |
| `type` | Provider type: `ollama`, `openai`, `anthropic`, `openrouter`, `ai21`, `google_genai`, `mistralai`, `cohere`, `perplexity`, `groq`, `deepseek`, `xai`, `cloudflare`, `comfyui`, `alltalk`, or `whispercpp`. |
| `name` | Display name shown in dropdowns. Use names that describe the endpoint, not just the provider. |
| `base_url` | Provider base URL. Local providers usually need this; official or SDK-default providers may leave it empty. |
| `api_key` | Optional API key. Leave it empty for local/self-hosted providers that do not require one. |

<!-- Screenshot placeholder: New/Edit Connection modal with provider type, name, base URL, and API key fields. -->

## Recommended examples

| Provider | Typical base URL or note |
| --- | --- |
| Ollama | `http://localhost:11434` |
| OpenAI | Leave empty for the official OpenAI endpoint, or set an OpenAI-compatible base URL. |
| Anthropic | Leave empty for the official Anthropic endpoint. |
| OpenRouter | Leave empty for the integration default, or set a custom OpenRouter-compatible endpoint. |
| AI21 | Leave empty for the official AI21 endpoint. |
| Google GenAI | Leave empty for the official Google GenAI endpoint. |
| Mistral AI | Leave empty for the official Mistral endpoint, or use the config-level endpoint override. |
| Cohere | Leave empty for the official Cohere endpoint. |
| Perplexity | Leave empty for the official Perplexity endpoint. |
| Groq | Leave empty for the official Groq endpoint. |
| DeepSeek | Leave empty for the official DeepSeek endpoint. |
| xAI | Leave empty for the official xAI endpoint. |
| Cloudflare | Usually leave empty; set account and gateway details on the model config. |
| ComfyUI | `http://localhost:8188` |
| AllTalk | AllTalk V2 server URL visible from the backend. |
| whisper.cpp | whisper.cpp `examples/server` URL visible from the backend. |

When running the backend in Docker, `localhost` means "inside the application container". Use a Docker service name, `host.docker.internal`, or another reachable host address as appropriate for your setup.
