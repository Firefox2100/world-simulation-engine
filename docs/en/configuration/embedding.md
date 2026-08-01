# Embedding Configs

Use the **Embeddings** tab to create embedding profiles. Embeddings are used for retrieval and memory lookup.

The embedding driver now supports Ollama, OpenAI, Google GenAI, Mistral AI, Cohere, Perplexity, and Cloudflare Workers AI. Providers whose LangChain integration does not expose an embedding class, such as Anthropic, OpenRouter, Groq, DeepSeek, and xAI, are intentionally not shown in the embedding picker.

<!-- Screenshot placeholder: Embedding config editor with provider connection, model, dimension, and provider-specific fields. -->

## Common fields

| Field | Description |
| --- | --- |
| `name` | Optional display name. If omitted, the UI falls back to the model identifier. |
| `model` | Embedding model identifier. |
| `dimension` | Optional output vector dimension for providers/models that support selecting it. |

Use one embedding model consistently for a world once data has been embedded. Switching dimensions or embedding families after a world already has memories may require rebuilding stored embeddings.

## Provider-specific fields

| Provider | Additional configuration |
| --- | --- |
| Ollama | Context window, model validation on init, client kwargs, Mirostat controls, GPU/thread options, `keep_alive`, repeat controls, temperature, stop tokens, `tfs_z`, `top_k`, and `top_p`. |
| OpenAI | Deployment/API version fields, proxy, embedding context length, organization, special-token handling, chunk size, retries, request timeout, headers, tiktoken options, progress display, `model_kwargs`, empty-text handling, default headers/query, retry wait bounds, and context-length checks. |
| Google GenAI | Task type, Vertex AI mode, project, location, additional headers, client args, API version, request options, and output dimensionality through `dimension`. |
| Mistral AI | Endpoint override, retries, timeout, rate-limit wait time, and maximum concurrent requests. |
| Cohere | Truncation mode, embedding types, retries, request timeout, and user agent. |
| Perplexity | Request timeout and retries. |
| Cloudflare | Account ID, batch size, newline stripping, API base URL, and request headers. |

## Assignments

Embedding-capable components use embedding profiles where retrieval is needed, especially character simulation and memory workflows. Assign embedding configs on the world or simulation configuration screen.

<!-- Screenshot placeholder: World or simulation embedding assignment rows. -->
