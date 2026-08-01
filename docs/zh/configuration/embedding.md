# Embedding 配置

使用 **Embeddings** 标签页创建 embedding 配置。Embeddings 用于检索和记忆查找。

Embedding 驱动现在支持 Ollama、OpenAI、Google GenAI、Mistral AI、Cohere、Perplexity 和 Cloudflare Workers AI。对于当前 LangChain 集成没有暴露 embedding 类的提供商，例如 Anthropic、OpenRouter、Groq、DeepSeek 和 xAI，界面不会把它们显示在 embedding 选择器中。

<!-- Screenshot placeholder: Embedding config editor with provider connection, model, dimension, and provider-specific fields. -->

## 通用字段

| 字段 | 说明 |
| --- | --- |
| `name` | 可选显示名称。如果省略，UI 会回退显示模型标识符。 |
| `model` | Embedding 模型标识符。 |
| `dimension` | 可选输出向量维度，适用于支持选择维度的提供商/模型。 |

世界中已有数据完成 embedding 后，请尽量持续使用同一个 embedding 模型。切换维度或 embedding 系列后，可能需要重建已存储的 embeddings。

## 提供商特定字段

| 提供商 | 额外配置 |
| --- | --- |
| Ollama | 上下文窗口、初始化时模型校验、client kwargs、Mirostat 控制、GPU/线程选项、`keep_alive`、重复控制、temperature、stop tokens、`tfs_z`、`top_k` 和 `top_p`。 |
| OpenAI | Deployment/API version 字段、proxy、embedding context length、organization、特殊 token 处理、chunk size、retries、request timeout、headers、tiktoken 选项、进度显示、`model_kwargs`、空文本处理、default headers/query、retry 等待范围，以及 context-length 检查。 |
| Google GenAI | Task type、Vertex AI 模式、project、location、additional headers、client args、API version、request options，并通过 `dimension` 控制输出维度。 |
| Mistral AI | Endpoint 覆盖、retries、timeout、rate-limit wait time 和最大并发请求数。 |
| Cohere | Truncation mode、embedding types、retries、request timeout 和 user agent。 |
| Perplexity | Request timeout 和 retries。 |
| Cloudflare | Account ID、batch size、newline stripping、API base URL 和 request headers。 |

## 分配

需要检索的地方会使用 embedding 配置，尤其是角色模拟和记忆工作流。可以在世界或模拟配置页面分配 embedding 配置。

<!-- Screenshot placeholder: World or simulation embedding assignment rows. -->
