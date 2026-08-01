# 在 Windows 从源码快速本地部署

这条路径在 Windows 上从源码运行后端和前端，Python 与 Node.js/npm 使用官方发布包安装。这里仅用 Docker 运行 Neo4j，因为应用需要带 APOC 和 Graph Data Science 的 Neo4j。

## 1. 安装前置依赖

先安装：

- Python 3.11 或更新版本，使用官方 Python Windows 安装包。
- Node.js，使用官方 Node.js 发布包。npm 随 Node.js 一起安装。
- Git for Windows。
- Docker Desktop，这里只用于 Neo4j 依赖容器。

安装 Python 或 Node 后重启 PowerShell，让 `python`、`node` 和 `npm` 进入 `PATH`。

检查：

```powershell
python --version
node --version
npm --version
docker --version
```

## 2. 获取源码

```powershell
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
```

## 3. 创建本地 `.env`

复制 `.env.example` 到 `.env`，然后把 Neo4j URI 改成适合宿主机运行后端的值：

```powershell
Copy-Item .env.example .env
notepad .env
```

使用这个本地值：

```dotenv
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
```

任何非本地使用前都应修改密码。如果这里修改了密码，也要同步修改 `docker-compose.dependencies.yml` 中的 `NEO4J_AUTH`。

## 4. 启动 Neo4j

```powershell
docker compose -f docker-compose.dependencies.yml up -d
```

Neo4j Browser 在 `http://localhost:7474`。后端使用 `localhost:7687` 的 Bolt 连接。

## 5. 安装并启动后端

创建虚拟环境并安装应用。可以只安装需要的提供商 extras，也可以用 `all-llm` 安装所有支持的 chat/embedding 集成。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[all-llm]"
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797 --reload
```

后端 API 文档应可在 `http://127.0.0.1:9797/docs` 打开。

## 6. 安装并启动前端

打开第二个 PowerShell 窗口：

```powershell
cd world-simulation-engine\frontend
npm install
npm run dev
```

Vite 会打印前端 URL，通常是 `http://localhost:5173`。

## 7. 第一次检查

打开前端，进入 **Configurations**。至少创建：

1. 一个提供商连接，例如 Ollama 或 OpenAI。
2. 一个使用该连接的 LLM 配置。
3. 一个使用支持 embedding 的提供商的 embedding 配置。

下一步见[创建第一个世界并启动模拟](first-world.md)。
