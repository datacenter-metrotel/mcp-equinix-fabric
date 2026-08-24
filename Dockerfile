FROM python:3.12-slim

# uv permite ejecutar el script self-contained con deps inline (# /// script)
RUN pip install --no-cache-dir uv==0.4.*

WORKDIR /app
COPY equinix_mcp_server.py /app/

# Pre-warm: instala las deps declaradas en el script para que el primer run sea rápido
RUN uv run --no-project /app/equinix_mcp_server.py --help >/dev/null 2>&1 || true

# Usuario no-root
RUN useradd -m -u 1001 app && chown -R app:app /app
USER app

ENV MCP_PORT=8080 \
    MCP_HOST=0.0.0.0

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import socket,os; s=socket.socket(); s.settimeout(3); s.connect(('127.0.0.1',int(os.environ.get('MCP_PORT','8080')))); s.close()" || exit 1

CMD ["uv", "run", "--no-project", "/app/equinix_mcp_server.py"]
