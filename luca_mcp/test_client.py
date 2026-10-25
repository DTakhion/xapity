# luca_mcp/test_client.py
# ============================================================
# XAPITY — LUCA MCP
# Cliente local de prueba — PoC v0.3
# ============================================================

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def print_tool_response(result):
    """
    Muestra un resumen de la respuesta MCP sin
    imprimir todos los documentos comerciales.
    """

    if result.is_error:
        for content in result.content:
            if content.type == "text":
                print(content.text)
        raise RuntimeError("La herramienta MCP devolvió un error.")

    # El SDK puede proporcionar el resultado estructurado.
    data = getattr(result, "structuredContent", None)

    if data is None:
        for content in result.content:
            if content.type == "text":
                try:
                    data = json.loads(content.text)
                    break
                except json.JSONDecodeError:
                    print(content.text)

    if isinstance(data, dict):
        if "libros" in data:
            print("Business ID:", data.get("businessId"))
            print("Año:", data.get("year"))
            print("Mes:", data.get("month"))
            print("Total documentos:", data.get("totalRecords"))
            print("Página:", data.get("page"))
            print("Documentos recibidos:", len(data["libros"]))
            print("Siguiente página:", data.get("hasNextPage"))

            print("\nDocumentos:")
            for doc in data["libros"]:
                print(
                    "  Folio:", doc.get("folio"),
                    "| Tipo:", doc.get("nombreFolio"),
                    "| Estado:", doc.get("status"),
                )
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))


async def main():

    print("\n" + "=" * 60)
    print("XAPITY — LUCA MCP CLIENT TEST")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "luca_mcp.server"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()
            print("\n[OK] Sesión MCP inicializada")

            # ------------------------------------------------
            # Descubrir herramientas
            # ------------------------------------------------

            tools = await session.list_tools()

            tool_names = [tool.name for tool in tools.tools]

            print("\nHerramientas disponibles:")
            for name in tool_names:
                print(f"  - {name}")

            required_tools = [
                "get_luca_connection_status",
                "get_luca_sales_movements",
            ]

            for name in required_tools:
                if name not in tool_names:
                    raise RuntimeError(
                        f"Herramienta no encontrada: {name}"
                    )

            # ------------------------------------------------
            # Prueba 1 — Diagnóstico
            # ------------------------------------------------

            print("\n" + "-" * 60)
            print("PRUEBA 1 — DIAGNÓSTICO")
            print("-" * 60)

            result = await session.call_tool(
                "get_luca_connection_status",
                arguments={},
            )

            print_tool_response(result)

            # ------------------------------------------------
            # Prueba 2 — Movimientos comerciales
            # ------------------------------------------------

            print("\n" + "-" * 60)
            print("PRUEBA 2 — VENTAS LUCA")
            print("-" * 60)

            result = await session.call_tool(
                "get_luca_sales_movements",
                arguments={
                    "year": 2026,
                    "month": 1,
                    "page": 0,
                    "page_size": 5,
                },
            )

            print_tool_response(result)

    print("\n[OK] Prueba MCP finalizada correctamente")


if __name__ == "__main__":
    asyncio.run(main())
