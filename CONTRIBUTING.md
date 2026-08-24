# Contributing

## Flujo básico

1. Forkeá el repo, creá branch `feat/xyz` o `fix/xyz`.
2. Hacé el cambio local, testealo (ver **Test local**).
3. Corré la auditoría de seguridad antes de commit (`grep` que documentamos en
   `SECURITY.md`).
4. Commit con mensaje conciso y prefijo (`feat:`, `fix:`, `docs:`, `chore:`).
5. Push y abrí PR contra `main`.

## Test local

```bash
# Build
docker compose build

# Up
docker compose up -d

# Smoke con curl
export MCP_SERVER_API_KEY=$(grep MCP_SERVER_API_KEY .env | cut -d= -f2)
curl -sS -L -X POST http://127.0.0.1:8081/mcp/ \
  -H "Authorization: Bearer $MCP_SERVER_API_KEY" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dev","version":"1"}}}'
```

## Agregar una tool nueva

En `equinix_mcp_server.py`:

```python
@mcp.tool()
async def my_new_tool(param: str) -> str:
    """Descripción breve, un renglón. Ayuda al LLM a decidir cuándo usarla."""
    data = await _get(f"some/endpoint/{param}")
    return json.dumps(data, indent=2, ensure_ascii=False)
```

Reglas:
- El docstring va como description en el MCP (el modelo lo lee)
- Devolver string (idealmente formateado legible; JSON grande para data cruda)
- Manejar errores con try/except y devolver mensaje útil

## Estilo

- Python 3.12+.
- No agregar dependencias sin justificación (aumenta la superficie).
- Preferir stdlib cuando sea posible.
- `ruff` y `mypy --strict` deberían pasar (no está en CI todavía).

## Testing con Claude Desktop

Configurá tu `claude_desktop_config.json` apuntando a `127.0.0.1:8081` y
probá las tools desde la UI. Reiniciar Desktop tras cada cambio de config.
