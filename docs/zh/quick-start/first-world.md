# 创建第一个世界并启动模拟

本快速开始假设后端和前端已经运行。如果还没有，请先阅读[在 Windows 从源码快速本地部署](windows-source.md)。

## 1. 创建提供商配置

打开 **Configurations**，创建最小运行时配置：

1. **Connection**：为 LLM 提供商创建连接。对于本地 Ollama，base URL 使用 `http://localhost:11434`。
2. **LLM config**：选择该连接，输入模型 id，第一次运行先保留默认生成设置。
3. **Embedding config**：选择支持 embedding 的提供商。当前 embedding 提供商包括 Ollama、OpenAI、Google GenAI、Mistral AI、Cohere、Perplexity 和 Cloudflare Workers AI。

图像、TTS 或 STT 配置可以之后再加。第一次模拟不需要它们。

## 2. 创建作者

打开 **Authors**，创建一个作者配置。世界需要归属作者，所以先创建作者再创建世界。

## 3. 创建世界

打开 **Worlds**，创建一个世界，填写：

- 简短名称。
- 简洁的设定描述。
- 刚创建的作者。

保存后打开世界详情页。

## 4. 添加足够的世界状态

第一次运行建议保持世界很小：

1. 添加一个地点。
2. 在该地点添加一个玩家可交互角色。
3. 可选添加一个背景角色、物品、地标或装备。

小世界更容易调试，因为每个生成动作都能追溯到少量结构化状态。

## 5. 分配模型配置

在世界配置区域分配：

- 把 LLM 配置分配给核心 LLM 组件。
- 把 embedding 配置分配给支持 embedding 的组件。

至少确保 narrator、input interpreter、action validator、character simulator、scene coordinator、state committer、memory summarizer 和 perspective resolver 都有可用 LLM 配置。

## 6. 启动模拟

从世界页面创建一个 simulation。打开 simulation chat 页面，然后发送一个简单的第一步动作，例如：

```text
I look around and greet the nearest person.
```

模拟会解释输入、校验动作、模拟角色反应、提交状态变更，并渲染这一回合。

## 7. 如果第一回合失败

按这个顺序检查：

1. 后端终端是否有提供商认证或连接错误。
2. 选中的 LLM 模型 id 是否存在于提供商。
3. 创建记忆后是否更换过 embedding 模型维度。
4. 是否有必要组件没有分配 LLM 或 embedding 配置。
5. 模型是否连续多次返回了无法修复的结构化输出。

第一个世界跑通后，再逐步加入媒体生成、语音、提示词覆盖和更复杂的背景状态。
