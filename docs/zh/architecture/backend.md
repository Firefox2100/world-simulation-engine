# 后端

后端是位于 `src/world_simulation_engine` 的 FastAPI 应用。它暴露资源路由，负责应用生命周期设置，并持有生成运行需要的长期服务。

## 启动

`create_app()` 注册路由。lifespan 函数完成关键运行时接线：

1. 配置事件日志。
2. 根据 `WSE_NEO4J_*` 环境变量打开异步 Neo4j driver。
3. 创建 `DatabaseService`。
4. 根据 `WSE_DATA_FOLDER` 创建 `StorageService`。
5. 重启后把中断的 generation jobs 标记为失败。
6. 创建 prompt 和 workflow loaders。
7. 创建 `WorldSimulator`。
8. 把这些服务保存到 `app.state`。
9. 应用停止时关闭后台模拟工作并关闭 Neo4j。

## 路由分组

路由刻意按资源形状组织：

| 路由区域 | 职责 |
| --- | --- |
| 世界和模拟 | 创建世界、创建模拟、导入/导出世界、启动生成、流式运行、检查快照。 |
| 领域实体 | 角色、背景角色、地点、地标、物品、装备、容器、intent、事件、记忆、variable。 |
| 作者 | 作者档案，以及把世界（或其他 authored content）归属给某个作者。 |
| 故事脚本化 | Trigger 的增删改查和状态控制（`trigger_router`），用于驱动故事推进的脚本化 cue。 |
| SillyTavern 导入 | 解析上传的角色卡、通过 SSE 流式执行提取流水线，再把审阅后的结果提交为新的 `World`（`sillytavern_import_router`）。 |
| 配置 | 供应商连接、LLM/embedding/image/TTS/STT 配置、世界和模拟组件分配。 |
| 媒体、prompt、workflow | 上传并关联媒体、prompt JSON、workflow JSON、封面图、prompt/workflow 覆盖。 |
| 回合和呈现 | 回合记录、已渲染呈现块、生成图像/音频片段端点、归档 turn 版本以及回退到某个版本。 |
| 语音识别 | 面向已配置语音识别后端的 STT 转写端点。 |

simulation router 使用 `WorldSimulator.start_generation()` 启动生成。随后可以通过 `WorldSimulator.stream_generation()` 流式传输图更新，让前端在后台任务运行时更新。

## 生成运行归属

`WorldSimulator` 通过活动 generation job 和按模拟的运行锁，阻止同一个 simulation 上的并发写入。这很重要，因为一次生成可能会应用图变更、推进时间、创建记忆、安排离场工作，并启动媒体副作用。

后端会保存 generation jobs 用于幂等性和恢复。如果应用在生成中途重启，启动流程会把未完成的 jobs 标记为失败，而不是默默假装它们已经完成。

## 供应商边界

后端组件不会把供应商凭据保存在环境变量中。它们在运行时从 Neo4j 加载供应商连接和模型配置。服务层随后把这些配置适配到相关外部服务：

- 通过 `LlmService` 执行 chat 和结构化输出，
- 通过 `EmbedService` 执行 embeddings，
- 通过 ComfyUI 图像服务执行 images，
- 通过 AllTalk TTS 服务执行 voice，
- 通过 whisper.cpp STT 服务执行 speech recognition。

这样部署配置和模拟行为配置可以分离。

