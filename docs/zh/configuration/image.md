# 图像生成配置

图像生成同时使用图像服务配置和 LLM 聊天配置：

- 图像配置把最终提示词发送给图像后端，目前是 ComfyUI。
- 聊天配置根据世界状态、角色状态或叙事构建图像提示词。

使用 **Images** 标签页创建可复用的 ComfyUI 图像模型配置。

<!-- Screenshot placeholder: Image model config editor with ComfyUI connection, model, VAE, CLIP, dimensions, seed, steps, and CFG. -->

## ComfyUI 图像字段

| 字段 | 说明 |
| --- | --- |
| `model` | 可选 checkpoint/model 名称。 |
| `vae` | 可选 VAE 模型名称。 |
| `clip` | 可选 CLIP 模型名称。 |
| `image_width` / `image_height` | 可选请求图像尺寸。 |
| `seed` | 可选确定性随机种子。 |
| `steps` | 可选生成步数。 |
| `cfg` | 可选 classifier-free guidance 数值。 |

## 分配

把图像配置分配给世界或模拟图像组件：

| 组件 | 用途 |
| --- | --- |
| `character_image_generator` | 角色状态/封面图像。 |
| `character_portrait_image_generator` | 角色头像。 |
| `location_image_generator` | 地点图像。 |
| `item_image_generator` | 物品图像。 |
| `scene_image_generator` | 回合或场景插图。 |

对于自动回合图像，请确保 `scene_image_generator` 和 `turn_image_trigger` 都有合适的聊天模型分配，并且 `scene_image_generator` 也有图像模型分配。

## 每个模拟的行为

每个模拟的图像生成行为由 `ImageGenerationConfig` 控制：

| 字段 | 说明 |
| --- | --- |
| `mode` | `manual`、`auto` 或 `always`。Manual 只在请求时生成。Auto 使用重要性检查和 fallback 间隔。Always 每个回合都生成。 |
| `fallback_turns` | 在 `auto` 模式中，如果连续这么多回合没有图像，则强制生成一张。 |

<!-- Screenshot placeholder: Simulation Image Generation tab showing image model assignments and generation behavior settings. -->
