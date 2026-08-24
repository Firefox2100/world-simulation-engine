# 配置

世界模拟引擎有两层配置：

1. **启动配置** 从环境变量读取。这些设置用于让后端启动、找到 Neo4j、写入媒体文件，并设置服务级限制。
2. **运行时服务配置** 在网页界面中管理。这些设置决定某个世界或模拟使用哪些模型提供商、提示词、图像服务和语音服务。

第一层配置属于 `.env`、Docker Compose 或 shell。第二层配置存储在 Neo4j 中，可以在不修改环境变量的情况下更改。

## 配置小节

- [环境变量](configuration/environment.md)：后端启动设置和服务级限制。
- [连接](configuration/connections.md)：可复用的提供商端点和 API key。
- [LLM 模型配置](configuration/llm.md)：聊天模型配置和各提供商生成参数。
- [Embedding 配置](configuration/embedding.md)：检索和记忆使用的嵌入配置，包括最新扩展的 embedding 提供商支持。
- [图像生成配置](configuration/image.md)：ComfyUI 图像配置和图像生成行为。
- [TTS 配置](configuration/tts.md)：AllTalk 后端配置和每个模拟的语音生成设置。
- [STT 配置](configuration/stt.md)：whisper.cpp 语音识别设置。

实际使用时，先配置环境变量，再创建提供商连接，然后创建模型/媒体配置，最后把这些配置分配给世界或模拟。

## 运行时层级

运行时设置刻意做成可复用的：

- **连接**：提供商的网络端点和可选 API key。
- **模型配置**：某一服务类型的可复用模型配置，例如带采样设置的 LLM 模型，或带图像尺寸的 ComfyUI 图像配置。
- **世界分配**：世界的默认模型、图像、embedding、TTS 和提示词分配。
- **模拟分配**：针对某个具体模拟的覆盖设置。当某次运行需要与世界默认值不同的模型、图像行为或提示词时使用。

打开网页界面，然后从主导航进入 **Configurations** 或 **Connections**。

<!-- Screenshot placeholder: Configurations page showing tabs for Connections, Embeddings, LLMs, TTS, Images, and STT. -->
