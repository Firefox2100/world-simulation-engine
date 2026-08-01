# STT 配置

使用 **STT** 标签页配置 whisper.cpp HTTP server 连接，用于语音识别。

<!-- Screenshot placeholder: STT config editor with whisper.cpp connection, language, translate, temperature, and initial prompt fields. -->

系统只预期存在一个 STT 后端。它被所有模拟共享，而不是按世界或组件分配。

## 字段

| 字段 | 说明 |
| --- | --- |
| `connection` | 一个 `whispercpp` 连接，base URL 指向后端可访问的 whisper.cpp server。 |
| `model` | 可选模型标签，用于显示或在后端支持时选择模型。 |
| `language` | 语音语言代码，例如 `en`、`zh` 或 `auto`。 |
| `translate` | 是否把转写结果翻译为英文。 |
| `temperature` | 解码温度。 |
| `temperature_inc` | fallback 解码时使用的温度增量。 |
| `initial_prompt` | 可选提示词，用于偏置领域词汇或上下文。 |
| `carry_initial_prompt` | 是否每次请求都携带 initial prompt。 |

当后端运行在 Docker 中时，请确保 whisper.cpp URL 可从后端容器访问，而不仅是宿主机浏览器可访问。
