# 环境变量

启动配置通过 `src/world_simulation_engine/misc/config.py` 读取带 `WSE_` 前缀的变量。默认从 `.env` 加载；如果要使用其他文件，可以设置 `WSE_ENV_FILE`。

```shell
WSE_ENV_FILE=/path/to/local.env uvicorn world_simulation_engine.app:app --host 127.0.0.1 --port 9797
```

对于 Docker Compose，项目提供的 `docker-compose.yml` 会将 `.env` 传入应用容器：

```yaml
services:
  app:
    env_file:
      - .env
```

## 必需变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_NEO4J_PASSWORD` | 必需 | 连接 Neo4j 使用的密码。Docker Compose 依赖示例使用 `neo4j/password`；在任何非本地使用场景前都应修改。 |

## 常用变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_APP_HOST` | `127.0.0.1` | 本地启动脚本使用的主机地址。通过 Docker/nginx 运行时，容器入口和代理决定外部可访问地址。 |
| `WSE_APP_PORT` | `9797` | 本地启动脚本使用的端口。完整 Docker Compose 栈会在宿主机 `9798` 端口暴露网页应用。 |
| `WSE_LOGGING_LEVEL` | `INFO` | Python 日志级别。支持 `CRITICAL`、`ERROR`、`WARNING`、`INFO`、`DEBUG` 和 `NOTSET`。 |
| `WSE_NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI。请使用后端进程或容器可访问到的主机和端口。 |
| `WSE_NEO4J_USERNAME` | `neo4j` | 连接 Neo4j 使用的用户名。 |
| `WSE_DATA_FOLDER` | `data/storage` | 上传媒体、生成图像、提示词覆盖和工作流文件的内容寻址存储目录。在 Docker 中通常挂载到 `/app/data/storage`。 |

## TTS 服务限制

这些变量不选择 TTS 提供商。它们只在界面中配置好 TTS 后控制后端行为。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_TTS_MAX_CONCURRENCY` | `3` | 并发发起 TTS 生成请求的最大数量。如果 TTS 后端在压力下不稳定，可以降低此值。 |
| `WSE_TTS_MEDIA_RETENTION_TURNS` | `50` | 每个模拟保留最近多少个回合的生成语音媒体，超过后会清理旧生成文件。 |

## SillyTavern 导入限制

这些变量用于调整 SillyTavern 角色卡导入流水线。正常的模拟使用场景不需要设置它们。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WSE_SILLYTAVERN_IMPORT_MAX_CONCURRENCY` | `4` | 导入流水线单个阶段内并发 LLM 调用的最大数量（例如一次性分类多条 lorebook entry）。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_MAX_CONCURRENCY` | `4` | 探测或下载卡片中图片链接时，并发出站 HEAD/GET 请求的最大数量。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_MAX_BYTES` | `10485760` | 下载候选图片时接受的最大响应体大小（字节）。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_CONNECT_TIMEOUT` | `5.0` | 出站图片链接请求的连接超时（秒）。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_READ_TIMEOUT` | `10.0` | 出站图片链接 GET 请求的读取超时（秒）。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_HEAD_TIMEOUT` | `5.0` | 在向用户展示未加入白名单的图片链接供审阅之前，用于探测的轻量 HEAD 请求的总超时（秒）。 |
| `WSE_SILLYTAVERN_IMAGE_DOWNLOAD_MAX_REDIRECTS` | `3` | 下载候选图片链接时允许跟随的最大重定向跳数；每一跳都会重新经过 SSRF 过滤校验。 |

## `.env` 示例

```dotenv
WSE_LOGGING_LEVEL=INFO
WSE_NEO4J_URI=bolt://localhost:7687
WSE_NEO4J_USERNAME=neo4j
WSE_NEO4J_PASSWORD=password
WSE_DATA_FOLDER=data/storage
WSE_TTS_MAX_CONCURRENCY=3
WSE_TTS_MEDIA_RETENTION_TURNS=50
```

!!! warning "仅限本地使用的安全模型"
    应用只面向本地使用，不包含认证或多用户隔离，提示词和世界内容也可能被发送给已配置的外部模型提供商。

## 哪些内容不通过环境变量配置

不要把 LLM、embedding、图像、TTS、STT、提示词或各组件模型分配写入 `.env`。这些都是通过网页界面管理并存储在 Neo4j 中的运行时服务设置。
