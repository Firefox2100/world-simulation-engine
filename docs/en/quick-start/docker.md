# Fastest Local Deploy with Docker

This is the fastest way to get the app running: one Docker image builds and serves the frontend and backend together
behind nginx, plus a Neo4j container with the plugins it needs. You don't need Python or Node.js installed at all.
The steps are identical on Windows, macOS, and Linux.

If you'd rather run the backend/frontend from source (for development, or to avoid Docker for the app itself), use
[Fast local deploy on Windows from source](windows-source.md) instead. Neo4j is still run via Docker either way.

## 1. Install Docker

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS) or Docker Engine plus the
Compose plugin (Linux). Check that both are available:

```bash
docker --version
docker compose version
```

## 2. Get the source

```bash
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
```

## 3. Create a local `.env`

```bash
cp .env.example .env
```

The defaults work as-is for a local trial: the app container talks to Neo4j over the Docker network, and
`WSE_NEO4J_PASSWORD` matches `NEO4J_AUTH` in `docker-compose.yml`. If you change the password in one place, change it
in the other too. Always change it before exposing the app beyond your own machine — see
[Expose a Linux server with Cloudflare](cloudflare-linux.md) for that step.

## 4. Build and start everything

```bash
docker compose up --build -d
```

The first run builds the frontend, builds the backend, and pulls the Neo4j image with the APOC and Graph Data
Science plugins enabled, so it can take a few minutes. Later runs are much faster.

## 5. Check it's running

```bash
docker compose ps
```

Both `world-simulation-engine` and `neo4j` should show as running. Open `http://localhost:9798` in a browser — that's
the app, served by nginx (proxying the frontend and the backend API on the same port). Neo4j Browser is separately
available at `http://localhost:7474` if you want to inspect the database directly.

## 6. First check

In the app, go to **Configurations** and create at least:

1. A provider connection, such as Ollama or OpenAI.
2. An LLM config using that connection.
3. An embedding config using a supported embedding provider.

For the next step, continue with [Create the first world and start a simulation](first-world.md).

## Stopping the stack

```bash
docker compose stop
```

This pauses both containers without removing them, so your world data is untouched when you start them again with
`docker compose up -d`. `docker compose down` also removes the containers themselves; that's fine for a clean
teardown, but don't rely on it if you still need the Neo4j data afterwards.
