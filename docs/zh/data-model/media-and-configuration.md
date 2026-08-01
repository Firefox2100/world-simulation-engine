# 媒体与配置

## 目的

Media nodes 把图实体连接到上传、生成、prompt、workflow、图像和语音资产。Configuration nodes 把 worlds 和 simulations 连接到模型供应商和运行时生成行为。

## 重要属性

| 实体 | 重要属性 |
| --- | --- |
| `Media` | `id`, `type`, `title`, `hash`, `filename`, `created_at` |
| `PromptMediaFile` | media fields 加 `prompt_name`, `language`, `component` |
| `WorkflowMediaFile` | media fields 加 `workflow_name` |
| `GeneratedImageMediaFile` | generation type, component, workflow name, canonical 和 transient tags/descriptions, negative prompt |
| `GeneratedVoiceMediaFile` | presentation block id, turn id, character id, text, voice reference |
| `ConnectionConfig` | `id`, `type`, `name`, `base_url`, `api_key` |
| Model config nodes | provider-specific chat, embedding, image, TTS, STT settings |
| Generation config nodes | `ImageGenerationConfig.mode`, `fallback_turns`; `TtsGenerationConfig.mode`, browser autoplay, narrator voice fields |

## 关系

- `(:Entity)-[:HAS_MEDIA]->(:Media)`
- `(:Entity)-[:HAS_COVER]->(:Media)`
- `(:Entity)-[:HAS_IMAGE]->(:GeneratedImageMediaFile)`
- `(:Turn)-[:GENERATES_IMAGE]->(:GeneratedImageMediaFile)`
- `(:TurnPresentationBlock)-[:GENERATES_IMAGE]->(:GeneratedImageMediaFile)`
- `(:TurnPresentationBlock)-[:HAS_VOICE]->(:GeneratedVoiceMediaFile)`
- `(:World|Simulation)-[:USE_PROMPT]->(:PromptMediaFile)`
- `(:World|Simulation)-[:USE_WORKFLOW]->(:WorkflowMediaFile)`
- `(:World|Simulation)-[:USES {component}]->(:ChatModelConfig|EmbedModelConfig|ImageModelConfig|TtsModelConfig|SttModelConfig)`
- `(:ModelConfig)-[:USES]->(:ConnectionConfig)`
- `(:Simulation)-[:HAS_IMAGE_GENERATION_CONFIG]->(:ImageGenerationConfig)`
- `(:Simulation)-[:HAS_TTS_GENERATION_CONFIG]->(:TtsGenerationConfig)`
- `(:Character)-[:HAS_CONFIG]->(:CharacterTtsConfig)`
- `(:CharacterTtsConfig)-[:USE_CONFIG]->(:TtsModelConfig)`

## 归属与生命周期

Media 可以附着到 worlds、simulations、characters、background characters、locations、landmarks、items、stacks、equipment 和 containers。Cover media 是每个 entity 的单个选中 media relationship。Prompt 和 workflow media 可以由 simulation 从 world 继承，除非 simulation 有 override。

Connection configs 是可复用的供应商连接记录。Model configs 指向 connection configs。Worlds 和 simulations 再用带 `component` 关系属性的链接为各组件选择 model configs。

## 创建与删除行为

上传 media 会创建 `Media` 节点，保存文件元数据，并可选地附着到 source entity。分配 cover media 会替换之前的 `HAS_COVER` 关系。从 entity 移除 media 会删除关系；在对应 source flow 中不再使用时，也可以删除 media node。

创建 prompt 和 workflow media 会把上传定义保存为 specialized media。分配 prompts 或 workflows 会替换 world 或 simulation 上匹配 component 的 assignment。

删除 connection 或 model config 会移除 config node 及其 `USES` links。删除 simulation 会移除该 simulation 拥有的 generation configs、jobs、snapshots 和 media assignments。

## 不变量

- Media identity 通过 `hash` 内容寻址，并用 `filename` 命名。
- 每个 entity 的 cover assignment 是单一的。
- Model config 应指向兼容的 `ConnectionConfig`。
- World-level prompt、workflow 和 model assignments 是默认值；simulation-level assignments 会覆盖它们。
- Character TTS config 可以为单个 character 覆盖所选 TTS backend。
- Generated voice media 应指回请求它的 presentation block 和 turn。

## 示例 Cypher 表示

```cypher
MATCH (simulation:Simulation {id: "sim-1"})
MATCH (mira:Character {id: "char-1"})
CREATE (connection:ConnectionConfig {
  id: "conn-1",
  type: "openai",
  name: "OpenAI",
  base_url: null
})
CREATE (llm:OpenAiChatModelConfig {
  id: "llm-1",
  name: "Narration model",
  model: "gpt-4.1"
})
CREATE (portrait:Media {
  id: "media-1",
  type: "image",
  title: "Mira portrait",
  hash: "sha256:...",
  filename: "mira.png",
  created_at: datetime()
})
CREATE (llm)-[:USES]->(connection)
CREATE (simulation)-[:USES {component: "narrator"}]->(llm)
CREATE (mira)-[:HAS_MEDIA]->(portrait)
CREATE (mira)-[:HAS_COVER]->(portrait);
```

## 相关 API 端点

- `/media`, `/media/{media_id}`
- `/{entity}/{entity_id}/media`, `/{entity}/{entity_id}/media-connections`, `/{entity}/{entity_id}/cover-image`，适用于 worlds、simulations、characters、background characters、locations、landmarks、items、stacks、equipment 和 containers
- `/prompts`, `/prompts/{media_id}`, `/prompts/builtin/{language}/{prompt_name}`, `/prompts/{media_id}/messages`
- `/worlds/{world_id}/prompt-connections`, `/simulations/{simulation_id}/prompt-connections`, `/simulations/{simulation_id}/prompts/{language}/{prompt_name}`
- `/workflows`, `/workflows/{media_id}`, `/workflows/builtin/{workflow_name}`, `/workflows/{media_id}/data`
- `/worlds/{world_id}/workflow-connections`, `/simulations/{simulation_id}/workflow-connections`, `/simulations/{simulation_id}/workflows/{workflow_name}`
- `/config/connections`, `/config/llm`, `/config/embeddings`, `/config/images`, `/config/tts`, `/config/stt`
- `/worlds/{world_id}/{llm|embedding|tts|image}-connection`
- `/simulations/{simulation_id}/{llm|embedding|tts|image}-connection`
- `/characters/{character_id}/tts-config`
- `/characters/{character_id}/generate-image/state`, `/locations/{location_id}/generate-image/state`, `/items/{item_id}/generate-image/state`

