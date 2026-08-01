# 安装

推荐使用 Docker 安装世界模拟引擎。这样可以确保依赖被正确安装和配置，也便于后续更新和管理。

## 使用 Docker 安装

软件需要两个容器：主程序容器，以及作为数据库的 Neo4j。主程序容器可以从源码构建，并会自动处理依赖和反向代理，使用 supervisord 管理进程。最快的方式是使用 docker compose：

```shell
git clone https://github.com/Firefox2100/world-simulation-engine.git
cd world-simulation-engine
cp .env.example .env
# 启动容器前，先修改 .env 文件中的配置
docker compose up -d
```

这会基于当前代码构建主程序镜像。生产使用时建议使用稳定标签，但 main 分支可能包含一些新功能和错误修复。

## 从源码安装

也可以从源码安装软件，但需要手动安装依赖并配置服务。

### 安装 Neo4j

如果可以使用 Docker，仍然推荐使用 Docker 镜像运行 Neo4j，因为它会自动处理插件和配置。项目提供了一个只启动依赖的 docker compose 文件：

```shell
docker compose -f docker-compose.dependencies.yml up -d
```

这会启动一个安装了 APOC 和 Graph Data Science 插件的 Neo4j 实例。默认用户名和密码是 `neo4j` 和 `password`，可以在 docker compose 文件中修改。

如果你希望手动安装 Neo4j，请参考对应平台的 [Neo4j 安装指南](https://neo4j.com/docs/operations-manual/current/installation/)。请确保安装 APOC 和 Graph Data Science 插件，并配置数据库允许远程连接。本软件需要 Cypher 25 或更新版本，因此通常需要使用 Neo4j 2025.x 或更新版本。

### 配置后端

后端是一个通过环境变量配置的 FastAPI 服务。建议为后端使用专门的虚拟环境或 conda 环境，以避免依赖冲突。例如：

```shell
python --version
# 确保 Python 版本为 3.11 或更新
python -m venv .venv
source .venv/bin/activate
# 安装所有 LLM 提供商驱动，或只安装你需要的提供商
pip install -e .[all-llm]
cp .env.example .env
# 启动后端前，先修改 .env 文件中的配置
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

`all-llm` extra 会安装所有受支持的聊天模型提供商集成。如果想让环境更小，可以只安装计划使用的提供商 extra：

| Extra | 安装内容 |
| --- | --- |
| `ollama` | `langchain-ollama` |
| `openai` | `langchain-openai` |
| `anthropic` | `langchain-anthropic` |
| `openrouter` | `langchain-openrouter` |
| `ai21` | `langchain-ai21` |
| `google-genai` | `langchain-google-genai` |
| `mistralai` | `langchain-mistralai` |
| `cohere` | `langchain-cohere` |
| `perplexity` | `langchain-perplexity` |
| `groq` | `langchain-groq` |
| `deepseek` | `langchain-deepseek` |
| `xai` | `langchain-xai` |
| `cloudflare` | `langchain-cloudflare` |

例如，只使用本地模型的安装可以运行 `pip install -e .[ollama]`；混合本地和云端模型的安装可以运行 `pip install -e .[ollama,openai,anthropic]`。提供商端点和 API key 稍后在网页界面中配置，不在安装命令中配置。

### 构建前端

前端是一个使用 Vite 构建的 React JS 应用。它可以由静态文件服务器提供，也可以使用 Node 开发服务器运行。构建前端：

```shell
cd frontend
npm install
npm run build
```

输出文件会位于 `frontend/dist` 文件夹中，可以用静态文件服务器提供。如果要使用开发服务器，运行：

```shell
npm run dev
```

它会在 5173 之后的第一个可用端口启动，并自动将 `/api` 反向代理到 9797 端口的后端。如果使用静态文件服务器，你可能需要手动配置反向代理。请参考所用静态文件服务器的文档。
