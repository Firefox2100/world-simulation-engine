# LLM Model Configs

Use the **LLMs** tab to create chat model configs. Each config points to a provider-specific chat connection and stores the model identifier plus generation parameters.

Supported chat providers are Ollama, OpenAI, Anthropic, OpenRouter, Google GenAI, Mistral AI, Cohere, Perplexity, Groq, DeepSeek, xAI, and Cloudflare. The UI shows provider-specific fields after you choose the provider, and only connections with the matching provider type are available for that config.

<!-- Screenshot placeholder: LLM config editor with provider connection, model, temperature, context window, reasoning, and stop token fields. -->

## Common fields

| Field | Description |
| --- | --- |
| `name` | Display name for this LLM profile. |
| `model` | Provider model identifier, for example an Ollama model name or OpenAI-compatible model id. |
| `temperature` | Sampling temperature. Higher values are more varied; lower values are more deterministic. |
| `context_window` | Context size used when composing prompts. |
| `seed` | Optional seed for providers that support deterministic sampling. |
| `reasoning` | Optional reasoning control. It may be `true`, `false`, or a level such as `low`, `medium`, or `high`, depending on provider support. |
| `stop_tokens` | Optional comma-separated stop tokens. |

Complex provider parameters, such as `model_kwargs`, custom headers, response schemas, penalty configs, and safety settings, are entered as JSON in the frontend. Leave optional fields empty to use the provider default.

## Provider-specific fields

| Provider | Additional configuration |
| --- | --- |
| Ollama | Mirostat controls, prediction length, repeat penalty controls, model validation on init, GPU/thread options, logprobs, `top_k`, `top_p`, output `format`, `keep_alive`, and sync/async client kwargs. |
| OpenAI | `model_kwargs`, organization, proxy, request timeout, retries, penalties, logprobs, streaming, `top_p`, completion token limit, reasoning effort, verbosity, tiktoken model name, default headers/query, socket options, stream timeout, extra body, response headers, disabled params, Responses API context/include/service-tier/store/truncation options, and Responses API conversation flags. |
| Anthropic | `model_kwargs`, max tokens, timeout, retries, `top_p`, `top_k`, thinking config, output config, usage streaming, streaming, default headers, beta flags, service tier, MCP servers, container, and inference geography. |
| OpenRouter | OpenAI-compatible controls, plus any OpenRouter-specific request body values through `model_kwargs` or `extra_body`. |
| Google GenAI | `model_kwargs`, max output tokens, `top_p`, `top_k`, candidate count, retries, timeout, safety settings, response MIME type, response schema, cached content, thinking budget, thought inclusion, transport, and client options. |
| Mistral AI | `model_kwargs`, max tokens, `top_p`, random seed, safe mode, streaming, endpoint override, timeout, retries, and concurrent request limit. |
| Cohere | `model_kwargs`, preamble, streaming, user agent, and request timeout. |
| Perplexity | OpenAI-compatible controls, with unsupported parameters ignored or rejected by the provider depending on the model/API. |
| Groq | OpenAI-compatible controls plus max tokens, reasoning format, response format, and parallel tool-call control. |
| DeepSeek | OpenAI-compatible controls, with provider-specific values available through `model_kwargs` or `extra_body`. |
| xAI | OpenAI-compatible controls plus live search parameters. |
| Cloudflare | `model_kwargs`, account ID, endpoint format, AI Gateway slug, max tokens, `top_p`, `top_k`, and streaming. |

## Assignments

After creating LLM configs, assign them to a world or simulation from the world editor or simulation detail page.

LLM-capable simulation components include `input_interpreter`, `action_validator`, `character_simulator`, `scene_coordinator`, `state_committer`, `memory_summarizer`, `perspective_resolver`, and `narrator`.

Image-related chat components include `character_image_generator`, `character_portrait_image_generator`, `location_image_generator`, `item_image_generator`, `scene_image_generator`, and `turn_image_trigger`.
