# LLM 模型配置

使用 **LLMs** 标签页创建聊天模型配置。每个配置指向一个特定提供商的聊天连接，并保存模型标识符和生成参数。

支持的聊天模型提供商包括 Ollama、OpenAI、Anthropic、OpenRouter、Google GenAI、Mistral AI、Cohere、Perplexity、Groq、DeepSeek、xAI 和 Cloudflare。选择提供商后，UI 会显示对应的提供商特定字段，并且只允许选择相同提供商类型的连接。

<!-- Screenshot placeholder: LLM config editor with provider connection, model, temperature, context window, reasoning, and stop token fields. -->

## 通用字段

| 字段 | 说明 |
| --- | --- |
| `name` | 此 LLM 配置的显示名称。 |
| `model` | 提供商模型标识符，例如 Ollama 模型名或 OpenAI-compatible 模型 id。 |
| `temperature` | 采样温度。值越高输出越多样，值越低输出越确定。 |
| `context_window` | 组合提示词时使用的上下文大小。 |
| `seed` | 可选随机种子，适用于支持确定性采样的提供商。 |
| `reasoning` | 可选 reasoning 控制。根据提供商支持情况，可以是 `true`、`false`，也可以是 `low`、`medium`、`high` 等等级。 |
| `stop_tokens` | 可选的逗号分隔 stop tokens。 |

复杂提供商参数，例如 `model_kwargs`、自定义 headers、响应 schema、penalty 配置和 safety settings，都在前端以 JSON 输入。可选字段留空时会使用提供商默认值。

## 提供商特定字段

| 提供商 | 额外配置 |
| --- | --- |
| Ollama | Mirostat 控制、预测长度、重复惩罚控制、初始化时模型校验、GPU/线程选项、logprobs、`top_k`、`top_p`、输出 `format`、`keep_alive`，以及同步/异步 client kwargs。 |
| OpenAI | `model_kwargs`、organization、proxy、request timeout、retries、penalties、logprobs、streaming、`top_p`、completion token limit、reasoning effort、verbosity、tiktoken model name、default headers/query、socket options、stream timeout、extra body、response headers、disabled params、Responses API context/include/service-tier/store/truncation 选项，以及 Responses API conversation flags。 |
| Anthropic | `model_kwargs`、max tokens、timeout、retries、`top_p`、`top_k`、thinking config、output config、usage streaming、streaming、default headers、beta flags、service tier、MCP servers、container 和 inference geography。 |
| OpenRouter | OpenAI-compatible 控制项，以及通过 `model_kwargs` 或 `extra_body` 传入的 OpenRouter 特定请求体值。 |
| Google GenAI | `model_kwargs`、max output tokens、`top_p`、`top_k`、candidate count、retries、timeout、safety settings、response MIME type、response schema、cached content、thinking budget、thought inclusion、transport 和 client options。 |
| Mistral AI | `model_kwargs`、max tokens、`top_p`、random seed、safe mode、streaming、endpoint override、timeout、retries 和 concurrent request limit。 |
| Cohere | `model_kwargs`、preamble、streaming、user agent 和 request timeout。 |
| Perplexity | OpenAI-compatible 控制项。某些不支持的参数可能会被提供商忽略或拒绝，具体取决于模型/API。 |
| Groq | OpenAI-compatible 控制项，加上 max tokens、reasoning format、response format 和 parallel tool-call control。 |
| DeepSeek | OpenAI-compatible 控制项，提供商特定值可通过 `model_kwargs` 或 `extra_body` 传入。 |
| xAI | OpenAI-compatible 控制项，加上 live search parameters。 |
| Cloudflare | `model_kwargs`、account ID、endpoint format、AI Gateway slug、max tokens、`top_p`、`top_k` 和 streaming。 |

## 分配

创建 LLM 配置后，可以从世界编辑器或模拟详情页把它们分配给世界或模拟。

可使用 LLM 的模拟组件包括 `input_interpreter`、`action_validator`、`character_simulator`、`scene_coordinator`、`state_committer`、`memory_summarizer`、`perspective_resolver` 和 `narrator`。

图像相关聊天组件包括 `character_image_generator`、`character_portrait_image_generator`、`location_image_generator`、`item_image_generator`、`scene_image_generator` 和 `turn_image_trigger`。
