# Security Policy

## Manejo de credenciales

**Ningún archivo del repositorio debe contener credenciales reales.** Los
únicos archivos que existen para credenciales son plantillas con
placeholders:

- `.env.example` — plantilla del `.env` local
- `k8s/secret.yaml.example` — plantilla del Secret de Kubernetes

Los archivos reales están en `.gitignore`:

- `.env` (credenciales para Docker Compose)
- `k8s/secret.yaml` (Secret real de Kubernetes)

### Auditoría rápida antes de commit

```bash
# Buscar cualquier valor que parezca token/secret embebido
git diff --cached | grep -iE '(client_id|client_secret|api_key|bearer|password)' \
  | grep -vE '(example|placeholder|\<REDACTED\>|\$\{)'
```

### La imagen Docker no contiene secretos

Verificado con `docker history` — la imagen solo lleva código y defaults
técnicos (`MCP_PORT=8080`, `MCP_HOST=0.0.0.0`). Las credenciales se inyectan
en runtime desde:

- **Compose**: variables interpoladas desde `.env`
- **Swarm**: `/run/secrets/<name>` (raft encriptado) → entrypoint las expande
- **Kubernetes**: `envFrom.secretRef` (etcd cifrado con KMS)

## Superficie de auth del server

| Endpoint | Auth |
|---|---|
| `/` | pública (health) |
| `/health` | pública (health check) |
| `/mcp/*` | **Bearer obligatorio** (`Authorization: Bearer <MCP_SERVER_API_KEY>`) |

Sin header válido devuelve `401 Unauthorized`.

## Recomendaciones de deploy

1. **Rotar** el `MCP_SERVER_API_KEY` con cierta frecuencia (mínimo cuando
   alguien deja de tener acceso al sistema).
2. **No exponer** el puerto 8081 a internet sin TLS. En producción, poner
   un reverse proxy (nginx/traefik) con Let's Encrypt.
3. **Restringir** a red interna (LAN, VPN o SG/NSG del cloud provider).
4. **Auditar** los logs del container (`docker logs`, `journalctl`,
   `kubectl logs`) — el server no loguea el bearer, pero sí loguea las
   URL de la API de Equinix que se llaman.
5. **No commitear** claude_desktop_config.json real (contiene el Bearer del
   cliente).

## Reportar una vulnerabilidad

Enviar un mail a `security@metrotel.com.ar` con:
- Descripción y pasos para reproducir
- Impacto potencial
- Sugerencia de fix si la tenés

No abrir un issue público hasta que se coordine un fix.
