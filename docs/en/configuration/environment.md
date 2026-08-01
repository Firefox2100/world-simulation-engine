# Environment Variables

Startup configuration is read from `WSE_`-prefixed variables through `src/world_simulation_engine/misc/config.py`. By default the backend loads `.env`; set `WSE_ENV_FILE` if you want to use a different file.

```shell
WSE_ENV_FILE=/path/to/local.env uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

For Docker Compose, the provided `docker-compose.yml` passes `.env` into the application container:

```yaml
services:
  app:
    env_file:
      - .env
```

## Required variables

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_NEO4J_PASSWORD` | Required | Password used to connect to Neo4j. The Docker Compose dependency example uses `neo4j/password`; change it before any non-local use. |

## Common variables

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_APP_HOST` | `127.0.0.1` | Host used by the local start script. When running behind Docker/nginx, the container entrypoint and proxy decide the externally exposed host. |
| `WSE_APP_PORT` | `9797` | Port used by the local start script. The full Docker Compose stack exposes the web app on host port `9798`. |
| `WSE_LOGGING_LEVEL` | `INFO` | Python logging level. Supported values are `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, and `NOTSET`. |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Bolt URI for Neo4j. Use the host and port visible from the backend process or container. |
| `WSE_NEO4J_USERNAME` | `neo4j` | Username used to connect to Neo4j. |
| `WSE_DATA_FOLDER` | `data/storage` | Content-addressed storage folder for uploaded media, generated images, prompt overrides, and workflow files. In Docker, this is normally mounted under `/app/data/storage`. |

## TTS service limits

These variables do not choose a TTS provider. They only control backend behavior once TTS is configured in the interface.

| Variable | Default | Description |
| --- | --- | --- |
| `WSE_TTS_MAX_CONCURRENCY` | `3` | Maximum number of concurrent outbound TTS generation requests. Lower this if the TTS backend becomes unstable under load. |
| `WSE_TTS_MEDIA_RETENTION_TURNS` | `50` | Number of most-recent turns whose generated voice media are retained per simulation before older generated files are pruned. |

## Example `.env`

```dotenv
WSE_LOGGING_LEVEL=INFO
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
WSE_TTS_MAX_CONCURRENCY=3
WSE_TTS_MEDIA_RETENTION_TURNS=50
```

!!! warning "Local-only security model"
    The application is designed for local use. It does not include authentication or multi-user isolation, and prompts or world content may be sent to configured external model providers.

## What is not configured here

Do not put LLM, embedding, image, TTS, STT, prompt, or per-component model assignments in `.env`. Those are runtime service settings managed through the web interface and stored in Neo4j.
