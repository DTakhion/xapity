# luca_mcp/server.py
# ============================================================
# XAPITY — LUCA MCP SERVER
# ============================================================

from mcp.server.mcpserver import MCPServer

from luca_mcp.luca_sales import get_luca_sales
from mcp.server.auth.settings import AuthSettings
from luca_mcp.oauth import LucaTokenVerifier

# ------------------------------------------------------------
# Configuración OAuth
# ------------------------------------------------------------

XAPITY_ISSUER_URL = (
    "https://xapity-api-dev-179536772092.us-central1.run.app"
)

XAPITY_MCP_RESOURCE_URL = (
    f"{XAPITY_ISSUER_URL}/mcp"
)

# ------------------------------------------------------------
# Servidor MCP
# ------------------------------------------------------------

mcp = MCPServer(
    name="xapity-luca",
    title="Xapity Luca MCP",
    description=(
        "Adaptador MCP de Xapity para conectar ChatGPT "
        "con la plataforma Luca y consultar información "
        "comercial mediante herramientas estructuradas."
    ),
    version="0.3.0",
    token_verifier=LucaTokenVerifier(
        resource=XAPITY_MCP_RESOURCE_URL,
    ),
    auth=AuthSettings(
        issuer_url=XAPITY_ISSUER_URL,
        resource_server_url=XAPITY_MCP_RESOURCE_URL,
        required_scopes=["luca:sales:read"],
        validate_token_resource=True,
    ),
)


# ------------------------------------------------------------
# Herramienta MCP — Diagnóstico
# ------------------------------------------------------------

@mcp.tool()
def get_luca_connection_status() -> dict:
    """
    Verifica que ChatGPT puede comunicarse correctamente
    con Xapity MCP.

    No consulta Luca ni requiere credenciales.
    """

    return {
        "service": "xapity-luca-mcp",
        "version": "0.3.0",
        "status": "ok",
        "lucaConnected": False,
        "message": (
            "Xapity MCP conectado correctamente. "
            "La autenticación multiusuario con Luca "
            "todavía está pendiente."
        ),
    }


# ------------------------------------------------------------
# Herramienta MCP — Movimientos comerciales
# ------------------------------------------------------------

@mcp.tool()
def get_luca_sales_movements(
    year: int = 2026,
    month: int = 0,
    page: int = 0,
    page_size: int = 30,
) -> dict:
    """
    Consulta los documentos de ingresos/ventas de Luca.

    Parámetros:
    - year: año de los documentos.
    - month: 0 para todo el año; 1 a 12 para un mes.
    - page: página solicitada, comenzando desde 0.
    - page_size: documentos por página, máximo 100.

    Devuelve los registros originales de Luca, incluyendo
    sus atributos contables, comerciales y vinculaciones.

    Reglas de interpretación:
    - 'libros' contiene documentos comerciales.
    - 'code' y 'nombreFolio' identifican el tipo documental.
    - 'montoTotal' es el monto total del documento.
    - 'status' indica el estado reportado por Luca.
    - 'linkage' contiene vinculaciones con otros movimientos.
    - 'linkageCredito' contiene vinculaciones de crédito.
    - 'fecha' es la fecha del documento.
    - 'fechaVencimiento' indica su vencimiento.
    - 'fechaPago' puede representar la fecha comercial
      del cobro; no confundir con fechas internas de linkage.
    - 'centroCosto' puede contener asignaciones porcentuales.

    Importante:
    - No asumir que todos los ingresos son ventas netas.
    - No sumar notas de crédito como ventas positivas.
    - No interpretar automáticamente cada linkage como
      una conciliación bancaria.
    - No confundir documentos con vinculaciones.
    - No inferir significados de atributos desconocidos.
    """

    if page < 0:
        raise ValueError("page debe ser mayor o igual a 0.")

    if not 1 <= page_size <= 100:
        raise ValueError("page_size debe estar entre 1 y 100.")

    result = get_luca_sales(
        year=year,
        month=month,
    )

    documents = result["libros"]

    start = page * page_size
    end = start + page_size

    return {
        "businessId": result["businessId"],
        "year": year,
        "month": month,
        "page": page,
        "pageSize": page_size,
        "totalRecords": len(documents),
        "totalPages": (
            (len(documents) + page_size - 1) // page_size
        ),
        "hasNextPage": end < len(documents),
        "libros": documents[start:end],
    }


# ------------------------------------------------------------
# Ejecución HTTP
# ------------------------------------------------------------

# if __name__ == "__main__":
#     mcp.run(transport="streamable-http")
if __name__ == "__main__":
    mcp.run(transport="stdio")
