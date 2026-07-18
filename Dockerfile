FROM node:22-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential pkg-config libicu-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./src/world_simulation_engine /app/src/world_simulation_engine
COPY ./pyproject.toml /app/pyproject.toml
COPY ./LICENSE /app/LICENSE
COPY ./README.md /app/README.md

RUN pip install --upgrade pip && \
    pip wheel --wheel-dir /wheels .[all-llm]


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WSE_LOGGING_LEVEL="INFO"
ENV WSE_DATABASE_PATH="/app/data/database.db"
ENV WSE_DATA_FOLDER="/app/data/storage"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nginx supervisor bash ca-certificates curl libicu-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./src/world_simulation_engine /app/src/world_simulation_engine
COPY ./pyproject.toml /app/pyproject.toml
COPY ./example.env /app/.env
COPY ./LICENSE /app/LICENSE
COPY ./README.md /app/README.md

COPY --from=python-builder /wheels /wheels
RUN pip install --upgrade pip && \
    pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default
COPY scripts/nginx.conf /etc/nginx/conf.d/default.conf
COPY scripts/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80
VOLUME ["/app/data"]

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
