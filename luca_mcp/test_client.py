# luca_mcp/test_client.py
# ============================================================
# XAPITY — LUCA MCP
# Cliente local de prueba
# ============================================================

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():

    print("\n" + "=" * 60)
    print("XAPITY — LUCA MCP CLIENT TEST")
    print("=" * 60)

    # Configuración del servidor MCP local
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "luca_mcp.server"],
    )

    # Conexión mediante stdio
    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Inicializar sesión MCP
            await session.initialize()

            print("\n[OK] Sesión MCP inicializada")

            # Descubrir herramientas disponibles
            tools = await session.list_tools()

            print("\nHerramientas disponibles:")

            for tool in tools.tools:
                print(f"  - {tool.name}")

            # Ejecutar herramienta
            result = await session.call_tool(
                "get_luca_sales_summary",
                arguments={
                    "year": 2026,
                    "month": 3,
                },
            )

            print("\nRespuesta del servidor MCP:")

            for content in result.content:
                if content.type == "text":
                    print(content.text)

            if result.is_error:
                raise RuntimeError(
                    "La herramienta MCP devolvió un error."
                )

    print("\n[OK] Prueba MCP finalizada correctamente")


if __name__ == "__main__":
    asyncio.run(main())
