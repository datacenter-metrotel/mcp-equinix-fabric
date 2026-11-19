# Equinix MCP — Docker Swarm deployment

Las credenciales se guardan como **Docker Swarm secrets** (encriptados en el
raft del swarm), y se montan al container como archivos en `/run/secrets/`.
Un entrypoint inline los lee y los expone como env vars antes de arrancar el
server, sin tocar la imagen.

## 1. Inicializar Swarm (una sola vez)

```bash
docker swarm init --advertise-addr 172.18.208.166
```

Si es un nodo standalone alcanza; para cluster real hay que hacer `join` de
otros nodos con el token que devuelve `swarm init`.

## 2. Crear los secrets

Desde el `.env` existente (parseando línea por línea):

```bash
set -a; source ../.env; set +a

echo -n "$EQUINIX_CLIENT_ID"     | docker secret create equinix_client_id -
echo -n "$EQUINIX_CLIENT_SECRET" | docker secret create equinix_client_secret -
echo -n "$MCP_SERVER_API_KEY"    | docker secret create mcp_server_api_key -

docker secret ls
```

O si preferís ingresarlas a mano:

```bash
printf '...' | docker secret create equinix_client_id -
```

Los secrets viven en el raft encriptado del swarm, **no** en disco plano.

## 3. Deploy del stack

```bash
docker stack deploy -c docker-compose.swarm.yml equinix
```

## 4. Verificar

```bash
docker stack ps equinix
docker service logs -f equinix_equinix-mcp
curl -H "Authorization: Bearer <MCP_SERVER_API_KEY>" http://172.18.208.166:8081/mcp \
  -X POST -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"qa","version":"1"}}}'
```

## 5. Rotar credenciales

Docker Swarm no permite actualizar un secret existente — hay que crear uno
nuevo, apuntar el servicio a él, y borrar el viejo:

```bash
echo -n "NEW_VALUE" | docker secret create equinix_client_secret_v2 -

# Update en caliente
docker service update \
  --secret-rm equinix_client_secret \
  --secret-add source=equinix_client_secret_v2,target=equinix_client_secret \
  equinix_equinix-mcp

docker secret rm equinix_client_secret
```

O más simple: bumpear el compose file y hacer `stack deploy` con nombres nuevos.

## 6. Tear down

```bash
docker stack rm equinix
docker secret rm equinix_client_id equinix_client_secret mcp_server_api_key
```

## Cómo se ven los secrets dentro del container

```bash
docker exec $(docker ps -qf 'label=com.docker.swarm.service.name=equinix_equinix-mcp') \
  ls -la /run/secrets/
# equinix_client_id  equinix_client_secret  mcp_server_api_key

docker exec ... env | grep -E '^(EQUINIX_|MCP_)'
# EQUINIX_CLIENT_ID=...  (expandido por el entrypoint)
```

## Diferencia con `.env` local

| | `.env` local | Swarm secrets |
|---|---|---|
| Almacenamiento | Archivo plano en disco (0600) | Raft encriptado |
| Distribución | Manual por host | Automática entre nodos del swarm |
| Rotación | Editar archivo + restart | `docker secret create` + `service update` |
| Auditoría | Depende del filesystem | `docker secret inspect` (metadata) |
| Multi-nodo | Copiar en cada host | Un secret, N nodos |
