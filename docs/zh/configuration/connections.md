# 连接

连接包含 LLM、embedding、图像、TTS 和 STT 配置共用的提供商访问细节。

| 字段 | 说明 |
| --- | --- |
| `type` | 提供商类型：`ollama`、`openai`、`anthropic`、`openrouter`、`ai21`、`google_genai`、`mistralai`、`cohere`、`perplexity`、`groq`、`deepseek`、`xai`、`cloudflare`、`comfyui`、`alltalk` 或 `whispercpp`。 |
| `name` | 下拉菜单中显示的名称。名称应描述端点，而不仅仅是提供商。 |
| `base_url` | 提供商 base URL。本地提供商通常需要填写；官方或 SDK 默认提供商可以留空。 |
| `api_key` | 可选 API key。本地或自托管且不需要认证的提供商可以留空。 |

<!-- Screenshot placeholder: New/Edit Connection modal with provider type, name, base URL, and API key fields. -->

## 推荐示例

| 提供商 | 常见 base URL 或说明 |
| --- | --- |
| Ollama | `http://localhost:11434` |
| OpenAI | 官方 OpenAI 端点可留空，也可以设置 OpenAI-compatible base URL。 |
| Anthropic | 官方 Anthropic 端点可留空。 |
| OpenRouter | 集成默认端点可留空，也可以设置自定义 OpenRouter-compatible 端点。 |
| AI21 | 官方 AI21 端点可留空。 |
| Google GenAI | 官方 Google GenAI 端点可留空。 |
| Mistral AI | 官方 Mistral 端点可留空，也可以使用配置级 endpoint 覆盖。 |
| Cohere | 官方 Cohere 端点可留空。 |
| Perplexity | 官方 Perplexity 端点可留空。 |
| Groq | 官方 Groq 端点可留空。 |
| DeepSeek | 官方 DeepSeek 端点可留空。 |
| xAI | 官方 xAI 端点可留空。 |
| Cloudflare | 通常留空；在模型配置中设置 account 和 gateway 细节。 |
| ComfyUI | `http://localhost:8188` |
| AllTalk | 后端可访问到的 AllTalk V2 服务器 URL。 |
| whisper.cpp | 后端可访问到的 whisper.cpp `examples/server` URL。 |

当后端运行在 Docker 中时，`localhost` 表示“应用容器内部”。请根据你的部署方式使用 Docker service 名称、`host.docker.internal` 或其他可访问的主机地址。
