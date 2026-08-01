# Installation

The recommended way to install the World Simulation Engine is to use Docker. This ensures that all dependencies are correctly installed and configured, and allows for easy updates and management of the software.

## Installing with Docker

There are two containers needed -- the main software container and Neo4j as its database. The main software container can be built from the source code, which handles all dependencies and reverse proxy automatically, using supervisord. The quickest way is to use docker compose:

```shell
git clone https://github.com/Firefox2100/world-simulation-engine.git
cd world-simulation-engine
cp .env.example .env
# Modify the .env file to set your preferred configuration before starting the containers
docker compose up -d
```

This builds the main software image from current code base. Using a stable tag is recommended for production usage, but the main branch may contain some new features and bug fixes.

## Installing from source

The software can also be installed from source, but this requires more manual steps to install dependencies and configure the software.

### Installing Neo4j

If docker is available, it's still recommended to use the docker image for Neo4j, as it handles plugins and configuration automatically. A docker compose file for dependencies is provided, and can be started with:

```shell
docker compose -f docker-compose.dependencies.yml up -d
```

Which will start a Neo4j instance with the APOC and Graph Data Science plugins installed. The default username and password is `neo4j` and `password`, which can be changed in the docker compose file.

However, if you prefer to install Neo4j manually, please refer to the [Neo4j installation guide](https://neo4j.com/docs/operations-manual/current/installation/) for your platform. Make sure to install the APOC and Graph Data Science plugins, and configure the database to allow remote connections. The software needs Cypher 25 or later, so please make sure to use a compatible version of Neo4j, usually 2025.x or later.

### Configuring the backend

The backend is a FastAPI service that is configured via environment variables. It's recommended to use a dedicated virtual environment or conda environment for the backend to avoid dependency conflicts. For example:

```shell
python --version
# Ensure your Python version is 3.11 or later
python -m venv .venv
source .venv/bin/activate
# Install drivers for all LLM providers, or only the ones you need
pip install -e .[all-llm]
cp .env.example .env
# Modify the .env file to set your preferred configuration before starting the backend
uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

The `all-llm` extra installs every supported chat provider integration. For a smaller environment, install only the
provider extras you plan to use:

| Extra | Installs |
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

For example, a local-only setup can use `pip install -e .[ollama]`, while a mixed local/cloud setup might use
`pip install -e .[ollama,openai,anthropic]`. Provider endpoints and API keys are configured later in the web
interface, not in the install command.

### Building the frontend

The frontend is a React JS application built with Vite. It can be built and served by a static file server, or using the node development server. To build the frontend, run:

```shell
cd frontend
npm install
npm run build
```

The output would be in the `frontend/dist` folder, which can be served by a static file server. If you want to use the development server, run:

```shell
npm run dev
```

This should start the server on the first available port after 5173, and the reverse proxy is automatically set to proxy to the backend on port 9797 at `/api`. If you are using a static file server, you may need to configure the reverse proxy manually. Please refer to the documentation of your static file server for more details.
