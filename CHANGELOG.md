# Changelog

Todos los cambios notables se documentan acá.
Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.2.0] - 2026-08-25

### Added
- Empaquetado Docker (`Dockerfile`, `docker-compose.yml`).
- **Imagen pública en Docker Hub**: `metrotel/mcp-equinix-fabric:0.2.0`.
- Manifests de Kubernetes con `envFrom.secretRef` (`k8s/`).
- Deploy con Docker Swarm y secrets encriptados en raft (`swarm/`).
- Documentación: `README.md`, `SECURITY.md`, `.env.example`.
- Healthcheck TCP en el container.
- Container corre como usuario no-root (uid 1001).

### Security
- Credenciales fuera del código y de la imagen.
- Bearer auth via middleware Starlette en todas las rutas excepto health.

## [0.1.0] - Fecha previa

### Added
- Server FastMCP inicial con 8 tools de Equinix Fabric.
- Soporte OAuth2 Client Credentials contra `api.equinix.com`.
- Deploy manual vía `uv run equinix_mcp_server.py` + systemd unit.
