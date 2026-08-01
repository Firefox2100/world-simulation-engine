# TTS 与 STT

语音支持分为两部分：为生成的 turn presentation blocks 做 text-to-speech，以及为用户输入做 speech-to-text。两者都是可选运行时服务，并通过与其他提供商相同的连接/配置系统管理。

## Text-to-speech

TTS 当前通过 AllTalk V2 实现。共享后端配置保存 engine 和生成参数，而 voice 存在别处：

- `AllTalk*ModelConfig` 保存后端级设置，例如 engine、language、speed、temperature、text filtering 和 server-side playback 选项。
- `TtsGenerationConfig` 保存 per-simulation 生成模式和 narrator voice。
- `CharacterTtsConfig` 保存每个角色的 voice 和可选 RVC 设置。

这允许许多角色共享同一个后端，同时每个角色和每个 simulation narrator 都可以使用不同 voice。

## TTS 模式

`TtsGenerationConfig.mode` 控制何时创建 voice 文件：

| 模式 | 行为 |
| --- | --- |
| `manual` | 不自动生成语音。前端或 API 可以为单个 presentation block 请求语音。 |
| `auto` | 已提交 turn 中的每个 narration 和 speech presentation block 都会自动配音。 |

手动语音生成调用 `/turn-presentations/blocks/{block_id}/voice`。它是幂等的：如果 block 已经有 voice media，会直接返回已有 media。

自动生成由 `TurnVoiceTrigger.maybe_generate_for_turn` 处理。它查找所有没有 voice media 的 `narration` 和 `speech` blocks，为每个 block 解析正确 voice，生成音频，链接回 presentation block，并根据 `WSE_TTS_MEDIA_RETENTION_TURNS` 清理旧的生成语音媒体。

生成使用由 `WSE_TTS_MAX_CONCURRENCY` 控制的进程级 semaphore，因此一个繁忙 simulation 不会开启无限并发 TTS 调用。

## 分段 voice

Voice 选择遵循 presentation 结构：

- 带 `speaker_id` 的 `speech` blocks 会在存在时使用该角色的 `CharacterTtsConfig`。
- `narration` blocks 和未归属 speech 使用 `TtsGenerationConfig` 中的 simulation narrator voice。
- RVC voice 和 pitch 从角色或 narrator 配置解析。

后端会为 turn-block TTS 调用禁用 AllTalk 自己的 narrator splitting。应用已经把 turn 分成单 voice segments，后端再次按引号解析可能会把语音分配给错误 voice。

## Speech-to-text

STT 当前是全局配置，而不是按 simulation 配置。`/speech-recognition/transcribe` 端点会读取唯一配置的 global STT model 和 connection，然后把上传音频发送给后端。

已实现提供商是 whisper.cpp HTTP server：

- `WhisperCppSttModelConfig` 保存 language、translation、temperature、fallback temperature increment、initial prompt 和 carry-initial-prompt 选项。
- `SttWhisperCpp` 调用 whisper.cpp 的 `/inference` 端点。
- 浏览器录音会先通过 `ffmpeg` 转换为 16 kHz、mono、16-bit PCM WAV，再上传给 whisper.cpp，因为默认 whisper.cpp server 需要 WAV，除非启动时启用了 conversion 支持。

前端 recorder 会把音频发送给 STT，并把返回文本插入用户输入流程。单次调用可以传入 language override，而不必修改全局模型配置。

```mermaid
flowchart LR
    Mic["浏览器录音"] --> Api["/speech-recognition/transcribe"]
    Api --> Convert["ffmpeg 转为 16 kHz mono WAV"]
    Convert --> Whisper["whisper.cpp /inference"]
    Whisper --> Text["转写文本"]
    Text --> Input["用户动作输入"]
```
