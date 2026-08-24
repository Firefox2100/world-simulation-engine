# 前端

前端是 `frontend/` 下的 React + Vite 应用。它不是一个很薄的聊天框，而是管理和交互 UI。用户可以在同一个应用中创建世界、管理模拟、配置供应商、编辑 prompt、检查媒体，并与运行中的模拟聊天。

## 路由

React router 定义了这些主要路由：

| Route | Page | Purpose |
| --- | --- | --- |
| `/` | `SimulationPage` | 模拟列表和入口。 |
| `/simulations/:simulationId` | `SimulationChatPage` | 主要模拟交互视图、详情、配置 tabs、媒体生成、prompt overrides 和聊天。 |
| `/worlds` | `WorldPage` | 世界列表和世界创建/编辑工作流。 |
| `/authors` | `AuthorsPage` | 作者记录。 |
| `/media` | `MediaPage` | 上传/生成媒体管理。 |
| `/prompts` | `PromptsPage` | Prompt media 创建和编辑。 |
| `/connections` 和 `/configurations` | `ConfigurationsPage` | 供应商连接和可复用模型配置。 |
| `/worlds/import/sillytavern` | `SillyTavernImportPage` | SillyTavern 角色卡导入：解析、审阅/编辑、流式提取，并提交为一个新世界。渲染时不使用共享的 `AppLayout` 外壳。 |

## API 形状

前端 API modules 与后端资源保持镜像关系。它们通过 JSON 请求和媒体端点调用 FastAPI 后端。配置页面使用和模拟编辑器相同的 API surface，因此可复用配置以及 per-world/per-simulation 分配能保持一致。

## 模拟视图

`SimulationChatPage` 组合了多项职责：

- 显示 turn presentation blocks，而不是原始模型输出；
- 向 generation API 发送用户输入；
- 跟踪生成状态和运行输出；
- 暴露模拟 tabs，用于配置分配、图像生成、TTS 生成、prompt overrides、可观测性和实体详情；
- 提供重新生成某个 turn（「swipe」）的入口，以及浏览、回退到其归档备份版本；
- 在配置为手动模式时触发媒体生成；
- 在可用时显示生成的场景、角色、地点、物品和语音媒体。

重要的前端边界是：它显示已提交回合和呈现记录。它不决定拟议动作是否真实、有效或已提交。这些决定留在后端生成 graph 中。

## 配置编辑器

前端有两个层级的配置 UI：

- **Configurations** 下的全局可复用配置；
- 创建、编辑、详情工作流里的 world 或 simulation assignment matrices。

这与后端模型一致：供应商连接和模型配置是可复用节点；world 和 simulation 记录按组件链接到这些配置。

