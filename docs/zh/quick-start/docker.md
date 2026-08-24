# 使用 Docker 最快本地部署

这是让应用跑起来最快的方式：一个 Docker 镜像会构建并通过 nginx 同时提供前端和后端，再加一个装好所需插件的 Neo4j
容器。完全不需要安装 Python 或 Node.js。这些步骤在 Windows、macOS 和 Linux 上都是一样的。

如果你更想从源码运行后端/前端（用于开发，或者不想为应用本身使用 Docker），可以改用
[在 Windows 从源码快速本地部署](windows-source.md)。不管选哪条路径，Neo4j 都通过 Docker 运行。

## 1. 安装 Docker

安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows、macOS）或 Docker Engine 加 Compose
插件（Linux）。确认两者都可用：

```bash
docker --version
docker compose version
```

## 2. 获取源码

```bash
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
```

## 3. 创建本地 `.env`

```bash
cp .env.example .env
```

默认值可以直接用于本地试用：应用容器通过 Docker 网络连接 Neo4j，`WSE_NEO4J_PASSWORD` 与 `docker-compose.yml` 中的
`NEO4J_AUTH` 是一致的。如果改了其中一处的密码，另一处也要同步修改。在把应用暴露到自己电脑之外之前，务必修改密码——
具体步骤见[通过 Cloudflare 暴露 Linux 服务器](cloudflare-linux.md)。

## 4. 构建并启动全部服务

```bash
docker compose up --build -d
```

第一次运行会构建前端、构建后端，并拉取带 APOC 和 Graph Data Science 插件的 Neo4j 镜像，因此可能需要几分钟。之后
再运行会快很多。

## 5. 确认服务已启动

```bash
docker compose ps
```

`world-simulation-engine` 和 `neo4j` 都应显示为运行中。在浏览器中打开 `http://localhost:9798`——这就是应用地址，
由 nginx 在同一端口上同时提供前端和后端 API。如果想直接查看数据库，Neo4j Browser 单独运行在
`http://localhost:7474`。

## 6. 第一次检查

在应用中打开 **Configurations**，至少创建：

1. 一个提供商连接，例如 Ollama 或 OpenAI。
2. 一个使用该连接的 LLM 配置。
3. 一个使用支持 embedding 的提供商的 embedding 配置。

下一步见[创建第一个世界并启动模拟](first-world.md)。

## 停止服务栈

```bash
docker compose stop
```

这会暂停两个容器但不删除它们，所以下次用 `docker compose up -d` 启动时，世界数据不受影响。`docker compose down`
会连容器本身一起删除；如果确实要干净地拆除环境这样做没问题，但如果之后还需要 Neo4j 中的数据，就不要依赖这个命令。
