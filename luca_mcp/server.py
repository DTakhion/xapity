# luca_mcp/server.py
# ============================================================
# XAPITY — LUCA MCP SERVER
# PoC v0.2 — ChatGPT Connectivity
# ============================================================

from mcp.server.mcpserver import MCPServer


# ------------------------------------------------------------
# Servidor MCP
# ------------------------------------------------------------


mcp = MCPServer(
    name="xapity-luca",
    title="Xapity Luca MCP",
    description=(
        "Adaptador MCP de Xapity para conectar "
        "ChatGPT con la plataforma Luca."
    ),
    version="0.2.0",
)



# ------------------------------------------------------------
# Herramienta MCP — Diagnóstico
# ------------------------------------------------------------

@mcp.tool()
def get_luca_connection_status() -> dict:
    """
    Verifica que ChatGPT puede comunicarse
    correctamente con Xapity MCP.

    Esta herramienta no consulta Luca,
    no requiere credenciales y no accede
    a información de clientes.
    """

    return {
        "service": "xapity-luca-mcp",
        "version": "0.2.0",
        "status": "ok",
        "lucaConnected": False,
        "message": (
            "Xapity MCP conectado correctamente. "
            "La vinculación con Luca está pendiente."
        ),
    }


# ------------------------------------------------------------
# Ejecución HTTP
# ------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
