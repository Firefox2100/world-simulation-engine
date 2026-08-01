# 通过 Cloudflare 暴露 Linux 服务器

Cloudflare Tunnel 可以让 Linux 服务器通过 Cloudflare 暴露网页应用，而不需要打开入站防火墙端口。`cloudflared` 会向 Cloudflare 建立出站连接，公共 hostname 再路由回本地服务，例如 `http://localhost:9798`。

这适合私人或低风险部署。应用本身仍被设计为本地使用，不包含内置认证；如果要暴露给自己之外的人，请先在前面加 Cloudflare Access 或其他访问控制层。

参考：

- [Cloudflare Tunnel overview](https://developers.cloudflare.com/tunnel/)
- [Locally-managed tunnel setup](https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/)
- [Run cloudflared as a Linux service](https://developers.cloudflare.com/tunnel/advanced/local-management/as-a-service/linux/)
- [Tunnel routing](https://developers.cloudflare.com/tunnel/routing/)

## 1. 在 Linux 服务器运行应用

最快的服务器部署方式是使用完整 Docker Compose 栈：

```bash
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
cp .env.example .env
```

编辑 `.env` 和 `docker-compose.yml`，不要使用默认 Neo4j 密码。然后启动：

```bash
docker compose up --build -d
```

Compose 后的应用会通过 nginx 发布在宿主机 `9798` 端口。

在服务器本地检查：

```bash
curl http://localhost:9798
```

## 2. 安装并认证 `cloudflared`

按 Cloudflare 当前 Linux package 或 release binary 文档安装 `cloudflared`，然后认证：

```bash
cloudflared tunnel login
```

登录流程需要你的 Cloudflare 账户中已经添加了一个域名。

## 3. 创建 tunnel

```bash
cloudflared tunnel create world-simulation-engine
```

记录命令打印的 tunnel UUID。

## 4. 创建 tunnel 配置

创建 `~/.cloudflared/config.yml`：

```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /home/<USER>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: wse.example.com
    service: http://localhost:9798
  - service: http_status:404
```

替换 `<USER>`、`<TUNNEL-UUID>` 和 `wse.example.com`。

## 5. 把 DNS 路由到 tunnel

对于 locally managed tunnel：

```bash
cloudflared tunnel route dns world-simulation-engine wse.example.com
```

Cloudflare 会创建一个 CNAME，让该 hostname 指向 tunnel 目标。

## 6. 测试 tunnel

先以前台方式运行：

```bash
cloudflared tunnel run world-simulation-engine
```

打开 `https://wse.example.com`。如果正常，用 `Ctrl+C` 停止前台进程。

## 7. 安装为服务

安装并启动 Linux 服务：

```bash
sudo cloudflared --config /home/<USER>/.cloudflared/config.yml service install
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

如果修改了 `config.yml`，重启服务：

```bash
sudo systemctl restart cloudflared
```

## 8. 保护应用

分享 hostname 前：

- 在 hostname 前加 Cloudflare Access。
- 不要把 Neo4j 端口开放到互联网。
- 只通过 tunnel 访问应用，不要同时公开暴露 `9798`。
- 轮换默认 Neo4j 密码。
- 把所有模型/提供商凭据都视为密钥。
