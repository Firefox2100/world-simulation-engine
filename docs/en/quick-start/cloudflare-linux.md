# Expose a Linux Server with Cloudflare Tunnel

Cloudflare Tunnel lets a Linux server expose the web app through Cloudflare without opening inbound firewall ports. `cloudflared` creates outbound connections to Cloudflare, and a public hostname routes back to a local service such as `http://localhost:9798`.

Use this for a private or low-risk deployment. The app is still designed for local use and does not include built-in authentication, so put Cloudflare Access or another access control layer in front of it before exposing it beyond yourself.

References:

- [Cloudflare Tunnel overview](https://developers.cloudflare.com/tunnel/)
- [Locally-managed tunnel setup](https://developers.cloudflare.com/tunnel/advanced/local-management/create-local-tunnel/)
- [Run cloudflared as a Linux service](https://developers.cloudflare.com/tunnel/advanced/local-management/as-a-service/linux/)
- [Tunnel routing](https://developers.cloudflare.com/tunnel/routing/)

## 1. Run the app on the Linux server

For the quickest server deploy, use the full Docker Compose stack:

```bash
git clone https://github.com/firefox2100/world-simulation-engine.git
cd world-simulation-engine
cp .env.example .env
```

Edit `.env` and `docker-compose.yml` so the Neo4j password is not the default. Then start:

```bash
docker compose up --build -d
```

The composed app publishes the frontend/backend through nginx on host port `9798`.

Check locally on the server:

```bash
curl http://localhost:9798
```

## 2. Install and authenticate `cloudflared`

Install `cloudflared` using Cloudflare's current Linux package instructions or release binary, then authenticate:

```bash
cloudflared tunnel login
```

The login flow requires a domain already added to your Cloudflare account.

## 3. Create a tunnel

```bash
cloudflared tunnel create world-simulation-engine
```

Record the tunnel UUID printed by the command.

## 4. Create the tunnel config

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL-UUID>
credentials-file: /home/<USER>/.cloudflared/<TUNNEL-UUID>.json

ingress:
  - hostname: wse.example.com
    service: http://localhost:9798
  - service: http_status:404
```

Replace `<USER>`, `<TUNNEL-UUID>`, and `wse.example.com`.

## 5. Route DNS to the tunnel

For a locally managed tunnel:

```bash
cloudflared tunnel route dns world-simulation-engine wse.example.com
```

Cloudflare creates a CNAME pointing the hostname at the tunnel target.

## 6. Test the tunnel

Run it in the foreground first:

```bash
cloudflared tunnel run world-simulation-engine
```

Open `https://wse.example.com`. If it works, stop the foreground process with `Ctrl+C`.

## 7. Install as a service

Install and start the Linux service:

```bash
sudo cloudflared --config /home/<USER>/.cloudflared/config.yml service install
sudo systemctl start cloudflared
sudo systemctl status cloudflared
```

If you change `config.yml`, restart the service:

```bash
sudo systemctl restart cloudflared
```

## 8. Protect the app

Before sharing the hostname:

- Add Cloudflare Access in front of the hostname.
- Keep Neo4j ports closed to the internet.
- Keep the app behind the tunnel only; do not also expose `9798` publicly.
- Rotate the default Neo4j password.
- Treat all configured model/provider credentials as secrets.
