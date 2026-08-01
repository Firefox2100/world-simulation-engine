# 世界模拟引擎

语言：[English](README.md) | 中文

[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=bugs)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine) [![Reliability Rating](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine) [![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=Firefox2100_world-simulation-engine&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=Firefox2100_world-simulation-engine)

World Simulation Engine 是一个实验性的、由 LLM 驱动的世界模拟器：它维护一个由角色、地点、物品和事件组成的持久世界，并按回合推进。每个角色，无论是否在当前场景中，都会由一个基于结构化、可查询世界状态的 LLM agent 来扮演，而不是依赖一整段不断增长的自由聊天记录。项目提供完全由 Neo4j 支撑的 FastAPI 后端，并包含一个 React 管理/交互前端，用于构建世界、接入 LLM 连接，以及与模拟进行聊天。

这是一个研究/爱好项目，不是生产级产品。它的存在是为了探索下面这些设计问题；代码库、prompt 和数据模型都仍在演进中。

## 它探索什么

- **带时间约束的模拟。** 每个角色活动都有预期持续时间和是否可打断的标记，模拟根据显式的 `current_time` 推进，而不是简单地“一条消息对应一次回复”。Turns 不只是“下一条聊天消息”，而是可被调度的事件：角色可能正在进行、等待或被打断。
- **同时模拟场景内和场景外角色。** 用户当前没有互动的角色也会继续生活：`WorldSimulator` 中的后台 worker 会在用户回合之间继续推进离场角色的活动，独立决定、校验并提交它们的动作；前台流水线只有在用户动作确实依赖这些后台工作时才会等待，例如用户进入某个离场角色正在行动的地点。目标是一个持续运动的世界，而不是镜头一转走，整个 cast 就冻结。
- **结构化数据是事实来源，而不是 prose。** 世界状态，包括角色、地点、物品、装备、容器、事件、intents、关系和记忆，被建模为图数据库中的类型化节点/关系，而不是一大段模型必须反复读取并重新推断事实的叙事文本。叙事是从已提交的结构化状态生成的呈现层，并与状态本身解耦，因此某个回合如何向某个 viewer 渲染，可以独立于真正发生了什么而变化。
- **记忆、事实和 agent 隔离，让模拟更接近真实感。** 每个角色的信念都有作用域且是私有的：`SubjectiveEntityClaim` 记录一个角色对另一个实体的可错信念，并带有明确 stance，例如 remembered、inferred、believed、doubted、denied 或 known-mistaken；`EntityRelationship` 同时携带客观/公开描述和 per-observer 私有描述；每个角色有私有 `Emotion` vector，包括 valence/arousal/dominance，以及随时间衰减的慢速 baseline 和快速 immediate component。情绪只作为柔性的语气/风险约束使用，不会跨角色泄露。记忆检索受 token budget 限制，而不是把完整历史塞进每个 prompt。每个流水线阶段，包括输入解释、动作校验、按角色动作提案、场景协调、情绪/关系/信念更新、叙事、状态提交和记忆总结，都作为各自有作用域的 LLM agent 运行，因此一个角色的私有上下文不会泄露到另一个角色的决策或叙事中。
- **为小型本地模型优化，而不只是前沿云模型。** 流水线假设模型有时会把结构化输出写错：`LlmService.invoke_structured_with_repair` 会重新提示以修复格式错误的结构化输出，动作提案会经过有界的校验/返工循环，而不是相信第一稿，schema 也会容忍常见的小模型问题，例如把全零 delta 输出成 `null`。每个流水线阶段都有自己的 LLM/embedding 连接配置，因此可以按阶段分配便宜的本地模型，而不是要求一个大模型负责所有事情。开发主要使用本地运行的 Qwen3 35B 测试，目的是验证这个设计在普通本地硬件上也能成立，而不只是在大型云端模型上成立。

## 架构速览

- **后端**（`src/world_simulation_engine`）：FastAPI 应用、由 Neo4j 支撑的 `DatabaseService`（每个实体类型一个 store class，不使用 ORM）、由 LangGraph 编排的模拟流水线（`WorldSimulator` 及其组件阶段），以及按 connection config 选择的 provider-agnostic LLM/embedding 服务。Chat models 支持 Ollama、OpenAI、Anthropic、OpenRouter、Google GenAI、Mistral AI、Cohere、Perplexity、Groq、DeepSeek、xAI 和 Cloudflare；embeddings 当前支持 Ollama 和 OpenAI。
- **前端**（`frontend/`）：React + Vite 管理/聊天 UI，用于管理 worlds、connections、prompts 和 simulations。

## 部署

### 通过 Docker Compose 启动完整栈

```bash
docker compose up --build
```

这会构建前端、构建后端，并通过单个镜像（`Dockerfile`）中的 nginx 提供服务，同时启动一个启用了 `apoc` 和 `graph-data-science` 插件的 `neo4j` 容器。应用发布在 `9798`（代理到容器内 nginx 的 `80`）；Neo4j 的 browser/bolt 端口（`7474`/`7687`）也会发布。

在部署到任何非本地环境之前，请务必修改 `docker-compose.yml` 中默认的 Neo4j 凭据（`neo4j`/`password`）。

### 仅启动后端 + Neo4j（用于本地前后端开发）

```bash
docker compose -f docker-compose.dependencies.yml up -d
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797 --reload
```

### 配置

后端完全通过带 `WSE_` 前缀的环境变量配置（见 `src/world_simulation_engine/misc/config.py`），这些变量可以从 `.env` 文件加载，也可以通过 `WSE_ENV_FILE` 指定路径：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `WSE_APP_HOST` / `WSE_APP_PORT` | `127.0.0.1` / `9797` | 本地开发服务器绑定地址。 |
| `WSE_LOGGING_LEVEL` | `INFO` | 日志详细程度。 |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Neo4j 连接 URI。 |
| `WSE_NEO4J_USERNAME` / `WSE_NEO4J_PASSWORD` | `neo4j` / *必填* | Neo4j 凭据。 |
| `WSE_DATA_FOLDER` | `data/storage` | 媒体的内容寻址存储位置，包括图像、自定义 prompt/workflow。 |

LLM/embedding provider 凭据以及 per-component 模型分配，会在运行时通过 API/前端按 simulation 配置（`ConnectionConfig`、chat/embed configs），而不是通过环境变量配置。只安装你需要的 provider extras，或者使用 `pyproject.toml` 中的 `all-llm` optional dependency group 安装所有支持的 chat 集成。

## 路线图

### 已完成

- 覆盖完整模拟领域的图中心数据模型：worlds、locations、landmarks、characters、background characters、items、equipment、containers、events、intents、memories、relationships、subjective beliefs、emotions、turns、media，以及 simulation/connection configuration。
- Input interpreter 和 action validator，把自由文本用户输入转成结构化、已校验动作。
- Per-character action proposal 和 scene coordinator，把同时/冲突动作解析为已接受时间线，包括被打断或争议动作的 reaction handling。
- 基于时间的角色调度，以及异步离场活动 worker，让不在场角色在用户回合之间继续行动。
- Perspective resolver，用于判断每个角色当前能感知到什么。
- 带有界 token budget 的记忆检索和总结，以及 recall-aware intent management。
- Entity relationship management，包括独立的公开/客观描述和私有/per-observer 描述。
- 私有 per-character emotion modeling（带 decay 的 baseline + immediate vectors），用于语气/风险约束，不会跨角色泄露。
- Subjective entity claims：按角色、带 stance 的私有信念，用于描述其他实体。
- 面向小型本地模型容错的 LLM output repair pipeline（structured-output repair、validation rework loop）。
- Turn presentation 与底层生成/提交状态解耦，并按 viewer 渲染。
- 每个 simulation 和每个 pipeline component 都可配置 LLM/embedding connections，chat backends 支持 Ollama、OpenAI、Anthropic、OpenRouter、Google GenAI、Mistral AI、Cohere、Perplexity、Groq、DeepSeek、xAI 和 Cloudflare。
- 内容寻址媒体管理，包括 cover images 和 per-simulation prompt/workflow overrides。
- 基于 `GraphStateSnapshot` 的 simulation run 重新生成/继续生成。
- 结构化 audit log 和 Langfuse tracing integration，用于调试生成运行，并支持 authored content 的 author attribution。
- React 前端覆盖 world/simulation management、LLM connection setup、prompt/workflow overrides、media 和 simulation chat interface。

### 计划中

- 基于 ComfyUI 的图像生成流水线，用于角色/地点/物品肖像和场景插图。
- Event hooks 和绑定 encounters/events。
- Scripting、guided generation 和 plots。
- LLM fine-tuning 和/或 LoRA 支持，用于角色特定行为。
- OOC commands。
