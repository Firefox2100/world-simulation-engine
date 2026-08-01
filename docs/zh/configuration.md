# 配置

世界模拟引擎有两层配置：

1. **启动配置** 从环境变量读取。这些设置用于让后端启动、找到 Neo4j、写入媒体文件，并设置服务级限制。
2. **运行时服务配置** 在网页界面中管理。这些设置决定某个世界或模拟使用哪些模型提供商、提示词、图像服务和语音服务。

第一层配置属于 `.env`、Docker Compose 或 shell。第二层配置存储在 Neo4j 中，可以在不修改环境变量的情况下更改。

## 启动配置

后端通过 `src/world_simulation_engine/misc/config.py` 读取带 `WSE_` 前缀的变量。默认从 `.env` 加载；如果要使用其他文件，可以设置 `WSE_ENV_FILE`。

```shell
WSE_ENV_FILE=/path/to/local.env uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

对于 Docker Compose，项目提供的 `docker-compose.yml` 会将 `.env` 传入应用容器：

```yaml
services:
  app:
    env_file:
      - .env
```

### 必需变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_NEO4J_PASSWORD` | 必需 | 连接 Neo4j 使用的密码。Docker Compose 依赖示例使用 `neo4j/password`；在任何非本地使用场景前都应修改。 |

### 常用变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_APP_HOST` | `127.0.0.1` | 本地启动脚本使用的主机地址。通过 Docker/nginx 运行时，容器入口和代理决定外部可访问地址。 |
| `WSE_APP_PORT` | `9797` | 本地启动脚本使用的端口。完整 Docker Compose 栈会在宿主机 `9798` 端口暴露网页应用。 |
| `WSE_LOGGING_LEVEL` | `INFO` | Python 日志级别。支持 `CRITICAL`、`ERROR`、`WARNING`、`INFO`、`DEBUG` 和 `NOTSET`。 |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI。请使用后端进程或容器可访问到的主机和端口。 |
| `WSE_NEO4J_USERNAME` | `neo4j` | 连接 Neo4j 使用的用户名。 |
| `WSE_DATA_FOLDER` | `data/storage` | 上传媒体、生成图像、提示词覆盖和工作流文件的内容寻址存储目录。在 Docker 中通常挂载到 `/app/data/storage`。 |

### TTS 服务限制

这些变量不选择 TTS 提供商。它们只在界面中配置好 TTS 后控制后端行为。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_TTS_MAX_CONCURRENCY` | `3` | 并发发起 TTS 生成请求的最大数量。如果 TTS 后端在压力下不稳定，可以降低此值。 |
| `WSE_TTS_MEDIA_RETENTION_TURNS` | `50` | 每个模拟保留最近多少个回合的生成语音媒体，超过后会清理旧生成文件。 |

### `.env` 示例

```dotenv
WSE_LOGGING_LEVEL=INFO
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
WSE_TTS_MAX_CONCURRENCY=3
WSE_TTS_MEDIA_RETENTION_TURNS=50
```

!!! warning "仅限本地使用的安全模型"
    应用被设计为本地使用。它不包含认证或多用户隔离，并且提示词或世界内容可能会发送给已配置的外部模型提供商。

### 哪些内容不通过环境变量配置

不要把 LLM、embedding、图像、TTS、STT、提示词或各组件模型分配写入 `.env`。这些都是通过网页界面管理并存储在 Neo4j 中的运行时服务设置。

## 运行时服务配置

打开网页界面，然后从主导航进入 **Configurations** 或 **Connections**。这里用于定义可复用的提供商连接和模型配置。世界和模拟会把这些配置分配给需要它们的组件。

<!-- Screenshot placeholder: Configurations page showing tabs for Connections, Embeddings, LLMs, TTS, Images, and STT. -->

### 配置层级

运行时设置有意设计为可复用：

- **连接**：提供商的网络端点和可选 API key，例如 Ollama、OpenAI、Anthropic、OpenRouter、AI21、Google GenAI、Mistral AI、Cohere、Perplexity、Groq、DeepSeek、xAI、Cloudflare、ComfyUI、AllTalk 或 whisper.cpp。
- **模型配置**：某一服务类型的可复用模型配置，例如带采样设置的 LLM 模型，或带图像尺寸的 ComfyUI 图像配置。
- **世界分配**：世界的默认模型、图像、embedding、TTS 和提示词分配。
- **模拟分配**：针对某个具体模拟的覆盖设置。当某次运行需要与世界默认值不同的模型、图像行为或提示词时使用。

实际使用时，先创建提供商连接，再创建模型配置，最后把这些配置分配给世界或模拟。

## 连接

连接包含共享的提供商访问细节：

| 字段 | 说明 |
| --- | --- |
| `type` | 提供商类型：`ollama`、`openai`、`anthropic`、`openrouter`、`ai21`、`google_genai`、`mistralai`、`cohere`、`perplexity`、`groq`、`deepseek`、`xai`、`cloudflare`、`comfyui`、`alltalk` 或 `whispercpp`。 |
| `name` | 下拉菜单中显示的名称。名称应描述端点，而不仅仅是提供商。 |
| `base_url` | 提供商 base URL。本地提供商通常需要填写；官方或 SDK 默认提供商可以留空。 |
| `api_key` | 可选 API key。本地或自托管且不需要认证的提供商可以留空。 |

<!-- Screenshot placeholder: New/Edit Connection modal with provider type, name, base URL, and API key fields. -->

推荐示例：

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
| Cloudflare | 通常留空；在聊天模型配置中设置 account 和 gateway 细节。 |
| ComfyUI | `http://localhost:8188` |
| AllTalk | 后端可访问到的 AllTalk V2 服务器 URL |
| whisper.cpp | 后端可访问到的 whisper.cpp `examples/server` URL |

当后端运行在 Docker 中时，`localhost` 表示“应用容器内部”。请根据你的部署方式使用 Docker service 名称、`host.docker.internal` 或其他可访问的主机地址。

## LLM 模型配置

使用 **LLMs** 标签页创建聊天模型配置。每个配置指向一个特定提供商的聊天连接，并保存模型标识符和生成参数。

支持的聊天模型提供商包括 Ollama、OpenAI、Anthropic、OpenRouter、AI21、Google GenAI、Mistral AI、Cohere、Perplexity、Groq、DeepSeek、xAI 和 Cloudflare。选择提供商后，UI 会显示对应的提供商特定字段，并且只允许选择相同提供商类型的连接。

<!-- Screenshot placeholder: LLM config editor with provider connection, model, temperature, context window, reasoning, and stop token fields. -->

通用字段：

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

提供商特定字段：

| 提供商 | 额外配置 |
| --- | --- |
| Ollama | Mirostat 控制、预测长度、重复惩罚控制、初始化时模型校验、GPU/线程选项、logprobs、`top_k`、`top_p`、输出 `format`、`keep_alive`，以及同步/异步 client kwargs。 |
| OpenAI | `model_kwargs`、organization、proxy、request timeout、retries、penalties、logprobs、streaming、`top_p`、completion token limit、reasoning effort、verbosity、tiktoken model name、default headers/query、socket options、stream timeout、extra body、response headers、disabled params、Responses API context/include/service-tier/store/truncation 选项，以及 Responses API conversation flags。 |
| Anthropic | `model_kwargs`、max tokens、timeout、retries、`top_p`、`top_k`、thinking config、output config、usage streaming、streaming、default headers、beta flags、service tier、MCP servers、container 和 inference geography。 |
| OpenRouter | OpenAI-compatible 控制项，以及通过 `model_kwargs` 或 `extra_body` 传入的 OpenRouter 特定请求体值。 |
| AI21 | `model_kwargs`、streaming、max/min tokens、`top_p`、number of results、logit bias，以及 presence/count/frequency penalty 配置。 |
| Google GenAI | `model_kwargs`、max output tokens、`top_p`、`top_k`、candidate count、retries、timeout、safety settings、response MIME type、response schema、cached content、thinking budget、thought inclusion、transport 和 client options。 |
| Mistral AI | `model_kwargs`、max tokens、`top_p`、random seed、safe mode、streaming、endpoint override、timeout、retries 和 concurrent request limit。 |
| Cohere | `model_kwargs`、preamble、streaming、user agent 和 request timeout。 |
| Perplexity | OpenAI-compatible 控制项。某些不支持的参数可能会被提供商忽略或拒绝，具体取决于模型/API。 |
| Groq | OpenAI-compatible 控制项，加上 max tokens、reasoning format、response format 和 parallel tool-call control。 |
| DeepSeek | OpenAI-compatible 控制项，提供商特定值可通过 `model_kwargs` 或 `extra_body` 传入。 |
| xAI | OpenAI-compatible 控制项，加上 live search parameters。 |
| Cloudflare | `model_kwargs`、account ID、endpoint format、AI Gateway slug、max tokens、`top_p`、`top_k` 和 streaming。 |

## Embedding 配置

使用 **Embeddings** 标签页创建 embedding 配置。Embeddings 用于检索和记忆查找。

Embedding 配置目前只支持 OpenAI 和 Ollama 连接。更广泛的提供商扩展只适用于 chat/LLM 模型配置。

<!-- Screenshot placeholder: Embedding config editor with provider connection, model, dimension, and context window. -->

| 字段 | 说明 |
| --- | --- |
| `name` | 可选显示名称。如果省略，UI 会回退显示模型标识符。 |
| `model` | Embedding 模型标识符。 |
| `dimension` | 可选输出向量维度，适用于支持选择维度的提供商/模型。 |
| `context_window` | 仅 Ollama 可用的可选上下文窗口。 |

世界中已有数据完成 embedding 后，请尽量持续使用同一个 embedding 模型。切换维度或 embedding 系列后，可能需要重建已存储的 embeddings。

## 分配 LLM 和 embedding 配置

创建模型配置后，可以从世界编辑器或模拟详情页把它们分配给世界或模拟。

<!-- Screenshot placeholder: World configuration assignment matrix for LLM and embedding components. -->

<!-- Screenshot placeholder: Simulation configuration tab showing LLM and embedding override rows. -->

可使用 LLM 的模拟组件：

| 组件 | 用途 |
| --- | --- |
| `input_interpreter` | 将用户输入转换为结构化候选动作。 |
| `action_validator` | 检查提出的动作在当前世界状态中是否有效。 |
| `character_simulator` | 提出角色动作和反应。 |
| `scene_coordinator` | 将同时发生或冲突的动作解析为已提交时间线。 |
| `state_committer` | 将解析后的事件转换为图状态变更。 |
| `memory_summarizer` | 根据事件和回合构建记忆摘要。 |
| `perspective_resolver` | 判断每个角色能够感知到什么。 |
| `narrator` | 将已提交状态渲染为面向用户的叙事。 |

图像相关聊天组件：

| 组件 | 用途 |
| --- | --- |
| `character_image_generator` | 为角色状态图像构建提示词。 |
| `character_portrait_image_generator` | 为角色头像构建提示词。 |
| `location_image_generator` | 为地点图像构建提示词。 |
| `item_image_generator` | 为物品图像构建提示词。 |
| `scene_image_generator` | 为场景插图构建提示词。 |
| `turn_image_trigger` | 判断一个回合是否足够重要，需要自动生成图像。 |

需要检索的地方会使用 embedding 配置，尤其是角色模拟和记忆工作流。

## 提示词配置

提示词与模型配置分开管理。打开 **Prompts** 区域可以创建或上传可复用的提示词媒体，然后在世界或模拟的 **Prompts** 部分进行分配。

<!-- Screenshot placeholder: Prompts page showing uploaded or created prompt media. -->

<!-- Screenshot placeholder: Prompt assignment matrix for a world or simulation. -->

每个提示词都是一组消息。每条消息包含：

| 字段 | 说明 |
| --- | --- |
| `role` | 消息角色：`system`、`user`、`assistant` 或 `tool`。 |
| `content` | 提示词文本。支持 Jinja2 模板。 |

提示词分配可以按语言、提示词名称和组件限定范围。这让模拟可以只覆盖需要修改的提示词，同时继承默认设置。

UI 中常见的提示词组包括：

| 角色组 | 提示词键 |
| --- | --- |
| Director | `generation_prompt`、`planning_prompt` |
| Memory | `briefing_prompt`、`summary_prompt` |
| Character | `action_prompt`、`reaction_prompt` |
| Resolver | `resolve_character_prompt`、`resolve_reaction_prompt`、`resolve_user_prompt` |
| Committer | `mutation_prompt`、`validation_prompt` |
| Narrator | `narrate_resolved_turn_prompt`、`narrate_user_input_failure_prompt`、`narrate_wait_for_user_prompt` |
| World generator | `location_generation_prompt`、`item_generation_prompt`、`equipment_generation_prompt`、`entity_generation_prompt`、`world_entry_generation_prompt`、`generation_package_prompt` |

提示词变化会显著改变模拟行为。建议保留一套可工作的基线提示词，并为实验做聚焦的覆盖。

## 图像生成配置

图像生成同时使用图像服务配置和 LLM 聊天配置：

- 图像配置把最终提示词发送给图像后端，目前是 ComfyUI。
- 聊天配置根据世界状态、角色状态或叙事构建图像提示词。

使用 **Images** 标签页创建可复用的 ComfyUI 图像模型配置。

<!-- Screenshot placeholder: Image model config editor with ComfyUI connection, model, VAE, CLIP, dimensions, seed, steps, and CFG. -->

ComfyUI 图像字段：

| 字段 | 说明 |
| --- | --- |
| `model` | 可选 checkpoint/model 名称。 |
| `vae` | 可选 VAE 模型名称。 |
| `clip` | 可选 CLIP 模型名称。 |
| `image_width` / `image_height` | 可选请求图像尺寸。 |
| `seed` | 可选确定性随机种子。 |
| `steps` | 可选生成步数。 |
| `cfg` | 可选 classifier-free guidance 数值。 |

把图像配置分配给世界或模拟图像组件：

| 组件 | 用途 |
| --- | --- |
| `character_image_generator` | 角色状态/封面图像。 |
| `character_portrait_image_generator` | 角色头像。 |
| `location_image_generator` | 地点图像。 |
| `item_image_generator` | 物品图像。 |
| `scene_image_generator` | 回合或场景插图。 |

<!-- Screenshot placeholder: Simulation Image Generation tab showing image model assignments and generation behavior settings. -->

每个模拟的图像生成行为由 `ImageGenerationConfig` 控制：

| 字段 | 说明 |
| --- | --- |
| `mode` | `manual`、`auto` 或 `always`。Manual 只在请求时生成。Auto 使用重要性检查和 fallback 间隔。Always 每个回合都生成。 |
| `fallback_turns` | 在 `auto` 模式中，如果连续这么多回合没有图像，则强制生成一张。 |

对于自动回合图像，请确保 `scene_image_generator` 和 `turn_image_trigger` 都有合适的聊天模型分配，并且 `scene_image_generator` 也有图像模型分配。

## TTS 和 STT 配置

语音服务是可选的，但它们遵循相同的连接/配置/分配模式。

### TTS

使用 **TTS** 标签页创建 AllTalk 后端配置。共享后端配置控制引擎级设置；旁白和角色声音会单独选择。

<!-- Screenshot placeholder: TTS config editor with AllTalk connection, engine status, text filtering, language, speed, temperature, and playback fields. -->

每个模拟的 TTS 生成设置：

| 字段 | 说明 |
| --- | --- |
| `mode` | `manual` 或 `auto`。Manual 按需生成音频。Auto 在回合提交后为叙事/发言生成语音。 |
| `autoplay_in_browser` | 与 auto 模式一起启用时，前端会在浏览器中顺序播放生成的片段。 |
| `narrator_voice` | 旁白和未归属发言使用的声音。 |
| `rvc_narrator_voice` | 可选 narrator 语音转换 RVC 模型。 |
| `rvc_narrator_pitch` | 可选 narrator RVC 音高调整，范围 `-24` 到 `24`。 |

每个角色的具体声音选择保存在角色自己的 TTS 配置中，并可以指向共享 TTS 后端。

### STT

使用 **STT** 标签页配置 whisper.cpp HTTP server 连接，用于语音识别。

<!-- Screenshot placeholder: STT config editor with whisper.cpp connection, language, translate, temperature, and initial prompt fields. -->

字段包括语言、是否翻译为英文、解码温度、fallback 温度增量，以及一个可选的领域词汇 initial prompt。

## 推荐配置顺序

1. 使用有效的 `.env` 启动 Neo4j 和后端。
2. 打开网页界面。
3. 为本地或远程服务创建提供商连接。
4. 创建 LLM 和 embedding 模型配置。
5. 如果计划使用媒体功能，创建图像、TTS 或 STT 配置。
6. 把 LLM 和 embedding 配置分配给世界。
7. 只在需要媒体生成的位置分配图像和语音配置。
8. 在基线模拟成功运行后，再添加提示词覆盖。

这个顺序可以把启动问题与模型或提示词问题分开：先证明应用可以运行，再证明每个服务连接可用，最后调优模拟行为。
