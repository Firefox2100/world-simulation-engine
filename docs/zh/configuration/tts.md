# TTS 配置

使用 **TTS** 标签页创建 AllTalk 后端配置。共享后端配置控制引擎级设置；旁白和角色声音会单独选择。

<!-- Screenshot placeholder: TTS config editor with AllTalk connection, engine status, text filtering, language, speed, temperature, and playback fields. -->

## 后端配置

前端会从所选连接读取 AllTalk 当前实时的引擎、已加载模型、声音和能力标记。本应用不会更改 AllTalk 自己的引擎/模型配置；它只镜像当前服务器状态，并保存该引擎支持的生成时选项。

常见字段包括文本过滤、如何处理发言标签外文本、输出文件名时间戳、服务器自动播放、自动播放音量、语言、速度、温度和重复惩罚。

## 每个模拟的生成设置

每个模拟的 TTS 生成设置：

| 字段 | 说明 |
| --- | --- |
| `mode` | `manual` 或 `auto`。Manual 按需生成音频。Auto 在回合提交后为叙事/发言生成语音。 |
| `autoplay_in_browser` | 与 auto 模式一起启用时，前端会在浏览器中顺序播放生成的片段。 |
| `narrator_voice` | 旁白和未归属发言使用的声音。 |
| `rvc_narrator_voice` | 可选 narrator 语音转换 RVC 模型。 |
| `rvc_narrator_pitch` | 可选 narrator RVC 音高调整，范围 `-24` 到 `24`。 |

每个角色的具体声音选择保存在角色自己的 TTS 配置中，并可以指向共享 TTS 后端。
