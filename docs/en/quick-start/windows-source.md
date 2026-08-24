# Fast Local Deploy on Windows from Source

This path runs the backend and frontend from the source tree on Windows, using Python and Node.js/npm installed from their official release packages. It uses Docker only for Neo4j, because the app expects Neo4j with APOC and Graph Data Science available.

Use this if you want to develop against the source or don't want the app itself running in Docker. If you just want the app running as fast as possible, use [Fastest local deploy with Docker](docker.md) instead — it needs only Docker and works the same way on Windows, macOS, and Linux.

## 1. Install prerequisites

Install these first:

- Python 3.11 or newer from the official Python Windows installer.
- Node.js from the official Node.js release package. npm is included with Node.js.
- Git for Windows.
- Docker Desktop, used here only for the Neo4j dependency container.

Restart PowerShell after installing Python or Node so `python`, `node`, and `npm` are on `PATH`.

Check:

```powershell
python --version
node --version
npm --version
docker --version
```

## 2. Get the source

```powershell
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
```

## 3. Create a local `.env`

Copy `.env.example` to `.env`, then change the Neo4j URI for a host-run backend:

```powershell
Copy-Item .env.example .env
notepad .env
```

Use this local value:

```dotenv
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
```

Change the password before any non-local use. If you change it here, change `NEO4J_AUTH` in `docker-compose.dependencies.yml` as well.

## 4. Start Neo4j

```powershell
docker compose -f docker-compose.dependencies.yml up -d
```

Neo4j Browser is available at `http://localhost:7474`. The backend uses Bolt on `localhost:7687`.

## 5. Install and start the backend

Create a virtual environment and install the app. Pick only the provider extras you need, or use `all-llm` for every supported chat/embedding integration.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[all-llm]"
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797 --reload
```

Backend API docs should open at `http://127.0.0.1:9797/docs`.

## 6. Install and start the frontend

Open a second PowerShell window:

```powershell
cd world-simulation-engine\frontend
npm install
npm run dev
```

Vite prints the frontend URL, usually `http://localhost:5173`.

## 7. First check

Open the frontend, then go to **Configurations**. Create at least:

1. A provider connection, such as Ollama or OpenAI.
2. An LLM config using that connection.
3. An embedding config using a supported embedding provider.

For the next step, continue with [Create the first world and start a simulation](first-world.md).
