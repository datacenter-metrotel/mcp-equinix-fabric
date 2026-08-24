# /// script
# dependencies = [
#   "fastmcp>=2.0",
#   "httpx",
#   "starlette",
# ]
# ///
"""
Equinix Fabric MCP Server — HTTP/Streamable transport
Expone la API de Equinix Fabric como servidor MCP remoto para
Claude Desktop en otras máquinas.

Uso:
    uv run equinix_mcp_server.py

Claude Desktop (otra PC) config:
    {
      "mcpServers": {
        "equinix": {
          "url": "http://<esta-IP>:8080/mcp/",
          "headers": { "Authorization": "Bearer <SERVER_API_KEY>" }
        }
      }
    }
"""

import json
import os
import secrets
import sys
from pathlib import Path
from typing import Optional

import httpx
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ── Credenciales Equinix ────────────────────────────────────────────────────
CLIENT_ID = os.environ.get("EQUINIX_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("EQUINIX_CLIENT_SECRET", "")
TOKEN_URL = "https://api.equinix.com/oauth2/v1/token"
FABRIC_BASE = "https://api.equinix.com/fabric/v4"

# ── Config del servidor ─────────────────────────────────────────────────────
PORT = int(os.environ.get("MCP_PORT", "8080"))
HOST = os.environ.get("MCP_HOST", "0.0.0.0")

# Clave de acceso al MCP server (independiente de credenciales Equinix)
KEY_FILE = Path.home() / ".config" / "equinix-mcp" / "server_key.txt"

def _load_or_create_key() -> str:
    if env_key := os.environ.get("MCP_SERVER_API_KEY"):
        return env_key
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    key = "emcp-" + secrets.token_urlsafe(40)
    KEY_FILE.write_text(key)
    KEY_FILE.chmod(0o600)
    return key

SERVER_API_KEY = _load_or_create_key()


# ── Auth middleware ─────────────────────────────────────────────────────────
class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Health check sin auth
        if request.url.path in ("/", "/health"):
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {SERVER_API_KEY}":
            return Response(
                json.dumps({"error": "Unauthorized"}),
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


# ── Token Equinix (sin caché — siempre fresco) ──────────────────────────────
async def _equinix_token() -> str:
    async with httpx.AsyncClient() as c:
        r = await c.post(TOKEN_URL, json={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        })
        r.raise_for_status()
        return r.json()["access_token"]


async def _get(path: str) -> dict:
    token = await _equinix_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{FABRIC_BASE}/{path}",
                        headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict:
    token = await _equinix_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{FABRIC_BASE}/{path}",
                         headers={"Authorization": f"Bearer {token}"},
                         json=body)
        r.raise_for_status()
        return r.json()


# ── FastMCP server ──────────────────────────────────────────────────────────
mcp = FastMCP(
    "Equinix Fabric",
    instructions=(
        "Acceso a la API de Equinix Fabric. "
        "Soporta conexiones, puertos, cloud routers y service profiles. "
        "Filtrá por estado (ACTIVE, PENDING, DEPROVISIONED, FAILED) para reducir resultados."
    ),
)


@mcp.tool()
async def list_connections(
    state: str = "",
    limit: int = 25,
    offset: int = 0,
) -> str:
    """
    Lista conexiones de Equinix Fabric.
    state: filtra por ACTIVE, PENDING, DEPROVISIONED, FAILED (vacío = todos)
    limit: máximo resultados (1-100)
    """
    body: dict = {"pagination": {"offset": offset, "limit": min(limit, 100)}}
    if state:
        body["filter"] = {
            "and": [{"property": "/state", "operator": "=", "values": [state.upper()]}]
        }
    data = await _post("connections/search", body)
    items = data.get("data", [])
    total = data.get("pagination", {}).get("total", 0)

    lines = [f"Total: {total} | Mostrando: {len(items)}\n"]
    for c in items:
        a = c.get("aSide", {}).get("accessPoint", {})
        z = c.get("zSide", {}).get("accessPoint", {})
        a_port = a.get("port", {}).get("name") or a.get("type", "?")
        z_dest = z.get("profile", {}).get("name") or z.get("type", "?")
        lines.append(
            f"{'✅' if c.get('state')=='ACTIVE' else '⚫'} {c.get('name','?')}\n"
            f"  UUID:  {c.get('uuid')}\n"
            f"  Estado: {c.get('state')} | BW: {c.get('bandwidth')} Mbps\n"
            f"  {a_port} → {z_dest}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_connection(uuid: str) -> str:
    """Obtiene los detalles completos de una conexión por su UUID."""
    data = await _get(f"connections/{uuid}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_ports(metro_code: str = "", limit: int = 20) -> str:
    """
    Lista los puertos disponibles.
    metro_code: filtra por metro (ej: 'SV', 'NY', 'AM')
    """
    body: dict = {"pagination": {"offset": 0, "limit": limit}}
    if metro_code:
        body["filter"] = {
            "and": [{"property": "/location/metroCode", "operator": "=",
                     "values": [metro_code.upper()]}]
        }
    data = await _post("ports/search", body)
    items = data.get("data", [])
    total = data.get("pagination", {}).get("total", 0)

    lines = [f"Total puertos: {total}\n"]
    for p in items:
        loc = p.get("location", {})
        lines.append(
            f"📌 {p.get('name','?')} [{p.get('uuid','')}]\n"
            f"  Metro: {loc.get('metroCode','?')} — {loc.get('metroName','')}\n"
            f"  BW disponible: {p.get('availableBandwidth','?')} Mbps\n"
            f"  Estado: {p.get('state','?')}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_port(uuid: str) -> str:
    """Obtiene detalles completos de un puerto por UUID."""
    data = await _get(f"ports/{uuid}")
    return json.dumps(data, indent=2, ensure_ascii=False)


@mcp.tool()
async def list_cloud_routers(limit: int = 20) -> str:
    """Lista Cloud Routers de Equinix Fabric."""
    body = {"pagination": {"offset": 0, "limit": limit}}
    data = await _post("routers/search", body)
    items = data.get("data", [])
    total = data.get("pagination", {}).get("total", 0)

    lines = [f"Total Cloud Routers: {total}\n"]
    for r in items:
        loc = r.get("location", {})
        lines.append(
            f"🔀 {r.get('name','?')} [{r.get('uuid','')}]\n"
            f"  Metro: {loc.get('metroCode','?')}\n"
            f"  Package: {r.get('package',{}).get('code','?')}\n"
            f"  Estado: {r.get('state','?')}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def search_service_profiles(
    keyword: str = "",
    metros: str = "",
    limit: int = 20,
) -> str:
    """
    Busca service profiles (AWS, Azure, Google, etc).
    keyword: nombre o parte del nombre (ej: 'AWS', 'Azure', 'Google')
    metros: metros separados por coma (ej: 'SV,NY')
    """
    body: dict = {"pagination": {"offset": 0, "limit": limit}, "sort": [{"direction": "DESC", "property": "/name"}]}
    filters = []
    if keyword:
        filters.append({"property": "/name", "operator": "LIKE", "values": [keyword]})
    if metros:
        for m in metros.split(","):
            filters.append({"property": "/metros/code", "operator": "=", "values": [m.strip().upper()]})
    if filters:
        body["filter"] = {"and": filters}

    data = await _post("serviceProfiles/search", body)
    items = data.get("data", [])
    total = data.get("pagination", {}).get("total", 0)

    lines = [f"Profiles encontrados: {total}\n"]
    for sp in items:
        lines.append(
            f"☁️  {sp.get('name','?')}\n"
            f"  UUID: {sp.get('uuid','?')}\n"
            f"  Tipo: {sp.get('type','?')} | Estado: {sp.get('state','?')}\n"
            f"  Descripción: {sp.get('description','')[:80]}\n"
        )
    return "\n".join(lines)


@mcp.tool()
async def list_metros() -> str:
    """Lista todos los metros disponibles en Equinix Fabric."""
    data = await _get("metros")
    metros = data.get("data", [])
    lines = [f"Metros disponibles: {len(metros)}\n"]
    for m in sorted(metros, key=lambda x: x.get("code", "")):
        lines.append(
            f"  {m.get('code','?'):4} — {m.get('name','?'):25} "
            f"({m.get('region','?')})"
        )
    return "\n".join(lines)


@mcp.tool()
async def connection_actions(uuid: str) -> str:
    """Lista las acciones disponibles para una conexión específica."""
    data = await _get(f"connections/{uuid}/actions")
    return json.dumps(data, indent=2, ensure_ascii=False)


# ── Startup ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: EQUINIX_CLIENT_ID y EQUINIX_CLIENT_SECRET son requeridos", file=sys.stderr)
        sys.exit(1)

    local_ip = os.environ.get("MCP_HOST_IP", "")
    if not local_ip:
        try:
            import subprocess
            local_ip = subprocess.check_output(
                ["ip", "route", "get", "1"], text=True
            ).split()[6]
        except Exception:
            local_ip = "<esta-IP>"

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   ⚡ Equinix Fabric MCP Server — HTTP Transport             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"\n  Escuchando en:  http://{local_ip}:{PORT}/mcp/")
    print(f"  Server API Key: {SERVER_API_KEY}")
    print(f"\n  ─── Config para Claude Desktop (otra PC) ───────────────────")
    config = {
        "mcpServers": {
            "equinix": {
                "url": f"http://{local_ip}:{PORT}/mcp/",
                "headers": {
                    "Authorization": f"Bearer {SERVER_API_KEY}"
                }
            }
        }
    }
    print("  " + json.dumps(config, indent=4).replace("\n", "\n  "))
    print(f"\n  Guardá eso en claude_desktop_config.json de la otra PC.")
    print(f"  (macOS: ~/Library/Application Support/Claude/claude_desktop_config.json)")
    print(f"  (Windows: %APPDATA%\\Claude\\claude_desktop_config.json)")
    print(f"\n  Herramientas disponibles:")
    print(f"  • list_connections   • get_connection")
    print(f"  • list_ports         • get_port")
    print(f"  • list_cloud_routers • search_service_profiles")
    print(f"  • list_metros        • connection_actions")
    print(f"\n  Ctrl+C para detener\n")

    # Agregar auth middleware al ASGI app
    asgi_app = mcp.http_app(path="/mcp")
    asgi_app.add_middleware(BearerAuthMiddleware)

    import uvicorn
    uvicorn.run(asgi_app, host=HOST, port=PORT, log_level="warning")
