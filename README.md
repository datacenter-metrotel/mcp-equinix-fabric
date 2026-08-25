# mcp-equinix-fabric

MCP (Model Context Protocol) server para **Equinix Fabric API**, empaquetado
como microservicio Docker. Expone las operaciones de la API de Fabric v4
(conexiones, puertos, cloud routers, service profiles, metros) a cualquier
cliente MCP compatible — Claude Desktop, Claude Code, Cursor, etc.

**Imagen en Docker Hub**: [`metrotel/mcp-equinix-fabric`](https://hub.docker.com/r/metrotel/mcp-equinix-fabric)

- 🐳 Imagen Docker portable (~86 MB comprimida, sin secretos embebidos)
- 🔐 Credenciales por env vars / Swarm secrets / Kubernetes Secrets
- 🌐 Transporte Streamable HTTP + SSE con Bearer auth
- 🛠 8 tools: `list_connections`, `get_connection`, `list_ports`, `get_port`,
  `list_cloud_routers`, `search_service_profiles`, `list_metros`,
  `connection_actions`
- 🚀 Deploy: `docker compose`, Docker Swarm, o Kubernetes

## Arquitectura

```
┌─────────────────────┐   HTTP+SSE     ┌────────────────────┐   OAuth2   ┌──────────────┐
│  Cliente MCP        │ ─────────────▶ │  Container         │ ─────────▶ │  Equinix API │
│  (Claude Desktop,   │  Bearer auth   │  equinix-mcp:X.Y.Z │            │  Fabric v4   │
│   Claude Code, …)   │                │  FastMCP + Python  │            │              │
└─────────────────────┘                └────────────────────┘            └──────────────┘
                                              ▲
                                              │ env vars (o /run/secrets)
                                       ┌──────┴─────────┐
                                       │  .env  |  K8s  │
                                       │        | Swarm │
                                       └────────────────┘
```

## Requisitos

- Docker Engine ≥ 24 y Docker Compose v2 (para deploy local)
- Docker Swarm (para deploy multi-nodo con secrets nativos), o
- Kubernetes ≥ 1.24 (para deploy en cluster)
- Credenciales OAuth2 de Equinix Console (Client Credentials flow)

## Quickstart

### Opción A — `docker run` sin clonar el repo

```bash
docker run -d --name equinix-mcp -p 8081:8080 \
  -e EQUINIX_CLIENT_ID='...' \
  -e EQUINIX_CLIENT_SECRET='...' \
  -e MCP_SERVER_API_KEY='emcp-...' \
  --restart unless-stopped \
  metrotel/mcp-equinix-fabric:0.2.0
```

### Opción B — Docker Compose (clonando el repo)

```bash
# 1) Cloná el repo
git clone https://github.com/datacenter-metrotel/mcp-equinix-fabric.git
cd mcp-equinix-fabric

# 2) Configurá credenciales
cp .env.example .env
chmod 600 .env
# editá .env con tus valores reales

# 3) Up (pull automático desde Docker Hub, no requiere build local)
docker compose up -d

# 4) Verificar
docker compose ps
# STATUS: Up X seconds (healthy)

curl -sS -L -X POST http://127.0.0.1:8081/mcp/ \
  -H "Authorization: Bearer $(grep MCP_SERVER_API_KEY .env | cut -d= -f2)" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}'
```

Si querés buildear la imagen desde el código (en vez de usar Docker Hub),
descomentá `build: .` en `docker-compose.yml` y corré `docker compose up -d --build`.

## Configurar Claude Desktop

Agregá al `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "equinix": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "http://<HOST_IP>:8081/mcp/",
        "--allow-http",
        "--transport", "http-only",
        "--header", "Authorization:Bearer <MCP_SERVER_API_KEY>"
      ]
    }
  }
}
```

Rutas:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux** (community build): `~/.config/Claude/claude_desktop_config.json`

Reiniciá Claude Desktop y en la UI vas a ver el server `equinix` con 8 tools
disponibles.

## Deploy avanzado

### Docker Swarm (secrets encriptados en raft)

Ver [`swarm/README.md`](swarm/README.md). Resumido:

```bash
docker swarm init --advertise-addr <IP>
echo -n "..." | docker secret create equinix_client_id -
echo -n "..." | docker secret create equinix_client_secret -
echo -n "..." | docker secret create mcp_server_api_key -
docker stack deploy -c swarm/docker-compose.swarm.yml equinix
```

### Kubernetes (Secrets nativos)

Ver [`k8s/README.md`](k8s/README.md). Resumido:

```bash
kubectl create secret generic equinix-mcp-secrets --from-env-file=.env
kubectl apply -k k8s/
```

## Estructura del repo

```
.
├── Dockerfile                 # Imagen basada en python:3.12-slim + uv
├── docker-compose.yml         # Deploy local con .env
├── equinix_mcp_server.py      # Server FastMCP (8 tools)
├── .env.example               # Template de credenciales
├── k8s/                       # Manifests Kubernetes
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── kustomization.yaml
│   ├── secret.yaml.example
│   └── README.md
└── swarm/                     # Deploy Docker Swarm
    ├── docker-compose.swarm.yml
    └── README.md
```

## Variables de entorno

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `EQUINIX_CLIENT_ID` | ✅ | — | Client ID OAuth2 de Equinix Console |
| `EQUINIX_CLIENT_SECRET` | ✅ | — | Client Secret OAuth2 |
| `MCP_SERVER_API_KEY` | ✅ | (genera uno) | Bearer para autenticar clientes MCP contra este server |
| `MCP_HOST` | ❌ | `0.0.0.0` | Bind del listener HTTP |
| `MCP_PORT` | ❌ | `8080` | Puerto interno del container |
| `MCP_HOST_IP` | ❌ | (auto-detect) | IP anunciada en el banner al arrancar |

## Rotar credenciales

**Compose**: editá `.env` y `docker compose up -d` (recrea container, sin rebuild).

**Swarm**: crear un secret con nombre nuevo + `docker service update --secret-rm/--secret-add`.

**Kubernetes**: `kubectl create secret … --dry-run=client -o yaml | kubectl apply -f -` + `kubectl rollout restart deployment/equinix-mcp`.

## Rebuild y publicar imagen (mantenedores)

```bash
docker build -t metrotel/mcp-equinix-fabric:0.2.1 -t metrotel/mcp-equinix-fabric:latest .

docker login -u metrotel
docker push metrotel/mcp-equinix-fabric:0.2.1
docker push metrotel/mcp-equinix-fabric:latest
```

Después bumpear el tag en `docker-compose.yml`, `swarm/docker-compose.swarm.yml`
y `k8s/deployment.yaml`, y crear tag git de release (`v0.2.1`).

## Seguridad

Ver [`SECURITY.md`](SECURITY.md). En resumen:
- La imagen **no contiene secretos** — verificado con `docker history`.
- Los secretos viven fuera del código: `.env` (0600), Swarm raft, o K8s Secret.
- Middleware Bearer bloquea toda ruta excepto `/` y `/health` (bypasear con
  auth válida por el header `Authorization: Bearer <MCP_SERVER_API_KEY>`).
- Container corre como usuario no-root (uid 1001).

## Contribuir

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licencia

MIT — ver [`LICENSE`](LICENSE).
