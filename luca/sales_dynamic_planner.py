# luca/sales_dynamic_planner.py

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import requests
from pymongo.collection import Collection

from luca.sales_query_service import (
    get_sales_overview,
    get_total_documents,
    get_total_sales_amount,
    get_overdue_receivable_invoices,
    get_top_customers_by_sales,
    get_top_customers_by_receivables,
)




OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_LLM_MODEL",
    "llama3.2:3b",
)


# ==================================================
# TIPOS
# ==================================================


DynamicToolHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DynamicTool:
    """
    Herramienta determinista disponible para el planner.

    allowed_arguments describe los parámetros que
    Ollama puede solicitar para esta herramienta.
    """

    name: str
    description: str
    result_semantics: str
    handler: DynamicToolHandler
    allowed_arguments: Mapping[str, tuple[Any, ...]] | None = None


@dataclass(frozen=True, slots=True)
class DynamicPlanResult:
    """
    Resultado de una consulta comercial dinámica.
    """

    answer: str
    tool_name: str
    tool_result: dict[str, Any]
    plan: dict[str, Any]


# ==================================================
# CATÁLOGO DE HERRAMIENTAS
# ==================================================


DYNAMIC_TOOLS: dict[str, DynamicTool] = {
    "sales_overview": DynamicTool(
        name="sales_overview",
        description=(
            "Obtiene un resumen comercial de ventas. "
            "Incluye cantidad total de documentos, monto total, "
            "documentos y monto por cobrar, cantidad de clientes "
            "únicos, notas de crédito, documentos anulados y "
            "documentos vinculados. "
            "IMPORTANTE: esta es la herramienta que debes utilizar "
            "cuando el usuario pregunte cuántos clientes tiene, "
            "cuántos clientes únicos existen o solicite el total "
            "de clientes. El campo uniqueCustomers contiene esa "
            "cantidad. La herramienta total_documents NO permite "
            "contar clientes."            
            "Esta herramienta solo entrega indicadores agregados. "
            "NO identifica clientes individuales ni permite ordenar "
            "clientes por facturación. "
            "Si el usuario pregunta a qué cliente le ha facturado más, "
            "cuál es su principal cliente o solicita un ranking de "
            "clientes, utiliza top_customers_by_sales. "
            "NO utilices sales_overview para esas preguntas."
            "Si el usuario pregunta qué clientes le deben más, "
            "quiénes son sus mayores deudores o solicita un ranking "
            "de clientes por cobrar, utiliza "
            "top_customers_by_receivables. "

        ),
        result_semantics=(
            "result.uniqueCustomers representa la cantidad de "
            "clientes únicos identificados en los documentos "
            "comerciales del período consultado."
        ),
        handler=get_sales_overview,
    ),
    "total_documents": DynamicTool(
        name="total_documents",
        description=(
            "Cuenta documentos comerciales y calcula su monto total. "
            "Permite seleccionar todos los documentos, solamente "
            "facturas o solamente notas de crédito. "
            "También permite filtrar por estado de cobranza. "
            "Utiliza esta herramienta cuando la pregunta requiera "
            "contar documentos aplicando estos filtros."
        ),
        result_semantics=(
            "result.documentsCount representa la cantidad de "
            "documentos que cumplen todos los filtros aplicados. "
            "result.totalAmount representa la suma de sus montos "
            "documentales. Los filtros efectivamente utilizados "
            "se encuentran en filters."
        ),
        handler=get_total_documents,
        allowed_arguments={
            "document_type": (
                "all",
                "invoice",
                "credit_note",
            ),
            "status": (
                None,
                "POR COBRAR",
            ),
        },
    ),
    "total_sales_amount": DynamicTool(
        name="total_sales_amount",
        description=(
            "Obtiene el monto total de ventas documentadas para "
            "un período. Considera facturas menos notas de crédito "
            "y excluye documentos anulados."
        ),
        result_semantics=(
            "result.totalAmount representa el monto total de "
            "ventas documentadas del período según las reglas "
            "comerciales de Luca."
        ),
        handler=get_total_sales_amount,
    ),
    
    "overdue_receivable_invoices": DynamicTool(
        name="overdue_receivable_invoices",
        description=(
            "Obtiene el listado de las facturas por cobrar "
            "más atrasadas o vencidas. "
            "Selecciona exclusivamente facturas con estado "
            "POR COBRAR y fecha de vencimiento anterior a hoy. "
            "Ordena las facturas por días de atraso, de mayor "
            "a menor. Utiliza esta herramienta cuando el usuario "
            "pregunte cuáles son las facturas más atrasadas, "
            "más antiguas por vencimiento o más morosas. "
            "No la utilices para contar todas las facturas "
            "por cobrar sin considerar su vencimiento."
        ),
        result_semantics=(
            "result.documentsCount es la cantidad total de "
            "facturas vencidas que cumplen los filtros. "
            "result.returnedDocumentsCount es la cantidad "
            "de facturas incluidas en la respuesta. "
            "result.documents contiene las facturas ordenadas "
            "desde la más atrasada. "
            "Cada documento incluye customerName, documentName, "
            "dueDate, daysOverdue y amount. "
            "daysOverdue representa los días calendario "
            "transcurridos desde el vencimiento. "
            "amount representa el monto documental original, "
            "no necesariamente el saldo pendiente de cobro. "
            "No afirmes que result.totalAmount es el saldo "
            "insoluto. Las facturas sin fecha de vencimiento "
            "válida no se clasifican como atrasadas."
        ),
        handler=get_overdue_receivable_invoices,
        allowed_arguments={
            "limit": (5, 10, 20, 50, 100),
        },
    ),
    
    "top_customers_by_sales": DynamicTool(
        name="top_customers_by_sales",
        description=(
            "Obtiene el ranking de clientes con mayor facturación "
            "bruta en el período consultado. "
            "Agrupa las facturas válidas por cliente y ordena "
            "de mayor a menor monto facturado. "
            "Utiliza esta herramienta cuando el usuario pregunte "
            "cuál es el cliente al que más ha facturado, "
            "quién es su principal cliente por facturación, "
            "qué cliente tiene la mayor facturación o solicite "
            "un ranking de clientes por montos facturados. "
            "Si pregunta por un solo cliente, utiliza limit=1. "
            "Si solicita un top 5, utiliza limit=5. "
            "Si no indica una cantidad, utiliza el límite "
            "predeterminado de la herramienta. "
            "No utilices sales_overview para identificar "
            "al cliente con mayor facturación."
        ),
        result_semantics=(
            "result.customers contiene los clientes ordenados "
            "de mayor a menor facturación bruta. "
            "Cada cliente incluye customerRut, customerName, "
            "invoicesCount y totalAmount. "
            "result.customersCount representa el número total "
            "de clientes identificados en el período. "
            "result.returnedCustomersCount representa el número "
            "de clientes incluidos en el ranking solicitado. "
            "result.invoicesCount y result.totalAmount "
            "corresponden a todas las facturas válidas del período, "
            "no solamente a los clientes mostrados. "
            "Los montos corresponden al total documental "
            "de facturas 33 y 34, con IVA incluido cuando aplica. "
            "Se excluyen documentos anulados. "
            "Las notas de crédito no se descuentan. "
            "Si el usuario solicita un único cliente, "
            "identifica el primer elemento de result.customers. "
            "No confundas la facturación del primer cliente "
            "con result.totalAmount."
        ),
        handler=get_top_customers_by_sales,
        allowed_arguments={
            "limit": (1, 5, 10, 20, 50, 100),
        },
    ),
    
    "top_customers_by_receivables": DynamicTool(
        name="top_customers_by_receivables",
        description=(
            "Obtiene el ranking de clientes con mayores montos "
            "documentales por cobrar. "
            "Agrupa las facturas con estado POR COBRAR por cliente "
            "y ordena de mayor a menor monto pendiente documental. "
            "Utiliza esta herramienta cuando el usuario pregunte "
            "qué clientes le deben más, quiénes son sus mayores "
            "deudores, qué cliente tiene más dinero por cobrar "
            "o solicite un ranking de clientes por cobranza. "
            "Si pregunta por un solo cliente, utiliza limit=1. "
            "Si solicita un top 5, utiliza limit=5. "
            "Si no indica cantidad, utiliza el límite "
            "predeterminado de la herramienta. "
            "NO utilices sales_overview ni top_customers_by_sales "
            "para identificar clientes con mayores montos por cobrar."
        ),
        result_semantics=(
            "result.customers contiene clientes ordenados de "
            "mayor a menor monto documental por cobrar. "
            "Cada cliente incluye customerRut, customerName, "
            "invoicesCount y totalAmount. "
            "result.customersCount representa el total de clientes "
            "identificados con facturas POR COBRAR. "
            "result.returnedCustomersCount representa los clientes "
            "incluidos en el ranking solicitado. "
            "result.invoicesCount y result.totalAmount corresponden "
            "a todas las facturas POR COBRAR del período, "
            "no solamente a los clientes mostrados. "
            "Solo considera facturas 33 y 34 con estado POR COBRAR. "
            "Excluye facturas parcialmente cobradas y notas de crédito. "
            "Los montos son valores documentales originales, "
            "no saldos efectivos verificados. "
            "No confundas el monto del primer cliente "
            "con result.totalAmount."
        ),
        handler=get_top_customers_by_receivables,
        allowed_arguments={
            "limit": (1, 5, 10, 20, 50, 100),
        },
    ),

}


# ==================================================
# HELPERS OLLAMA
# ==================================================


def _call_ollama_json(
    prompt: str,
) -> dict[str, Any]:
    """
    Ejecuta Ollama esperando exclusivamente JSON.
    """

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
        },
        timeout=45,
    )

    response.raise_for_status()

    payload = response.json()
    raw_answer = payload.get("response")

    if not isinstance(raw_answer, str):
        raise ValueError(
            "Ollama no devolvió una respuesta válida."
        )

    result = json.loads(raw_answer)

    if not isinstance(result, dict):
        raise ValueError(
            "Ollama no devolvió un objeto JSON."
        )

    return result


def _call_ollama_text(
    prompt: str,
) -> str:
    """
    Ejecuta Ollama esperando una respuesta textual.
    """

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        },
        timeout=45,
    )

    response.raise_for_status()

    payload = response.json()
    raw_answer = payload.get("response")

    if not isinstance(raw_answer, str):
        raise ValueError(
            "Ollama no devolvió una respuesta válida."
        )

    answer = raw_answer.strip()

    if not answer:
        raise ValueError(
            "Ollama devolvió una respuesta vacía."
        )

    return answer


# ==================================================
# DESCRIPCIÓN DE TOOLS
# ==================================================


def _build_tools_description() -> str:
    """
    Construye el catálogo de herramientas y argumentos
    que Ollama puede utilizar para planificar.
    """

    lines: list[str] = []

    for tool in DYNAMIC_TOOLS.values():
        lines.append(
            f"- {tool.name}: {tool.description}"
        )

        if tool.allowed_arguments:
            for argument, allowed_values in (
                tool.allowed_arguments.items()
            ):
                values = json.dumps(
                    allowed_values,
                    ensure_ascii=False,
                )

                lines.append(
                    f"    {argument}: {values}"
                )

    return "\n".join(lines)


# ==================================================
# PLANIFICACIÓN
# ==================================================

def _normalize_allowed_argument(
    *,
    argument: str,
    value: Any,
    allowed_values: tuple[Any, ...],
) -> Any:
    """
    Normaliza strings numéricos cuando el argumento
    admite valores enteros explícitamente autorizados.

    No modifica argumentos de texto ni amplía
    los valores permitidos.
    """

    if (
        isinstance(value, str)
        and value.isascii()
        and value.isdecimal()
        and any(
            type(allowed) is int
            for allowed in allowed_values
        )
    ):
        value = int(value)

    return value

def _build_plan(
    *,
    question: str,
    year: int | None,
    month: int | None,
) -> dict[str, Any]:
    """
    Pide al LLM seleccionar una herramienta disponible.

    El LLM decide qué capacidad necesita, pero no
    ejecuta consultas ni calcula datos comerciales.
    """

    tools_description = _build_tools_description()

    prompt = f"""
Eres el planificador comercial de Xapity-Luca.

Debes decidir qué herramienta disponible permite
obtener la información necesaria para responder
la pregunta del usuario.

No inventes herramientas.
No inventes datos.
No respondas todavía la pregunta.
No hagas cálculos comerciales.

Selecciona solamente una herramienta.

Identifica los argumentos necesarios para responder
la pregunta completa del usuario.

Los campos descritos como resultados de una herramienta
NO son argumentos de entrada.

En particular, uniqueCustomers es un campo de resultado
de sales_overview, NO un argumento.

Si una herramienta no declara argumentos permitidos,
debes devolver "arguments": {{}}.

Para responder cuántos clientes únicos existen,
selecciona sales_overview con "arguments": {{}}.

Para identificar al cliente con mayor facturación,
selecciona top_customers_by_sales con
"arguments": {{"limit": 1}}.

Distingue estas dos preguntas:

"¿Cuántos clientes tengo?"
-> sales_overview

"¿A qué cliente le he facturado más?"
-> top_customers_by_sales

"¿Qué clientes me deben más?"
-> top_customers_by_receivables

"¿Quién es mi mayor deudor?"
-> top_customers_by_receivables con limit=1

Distingue facturación de cobranza:

top_customers_by_sales identifica a los clientes
a quienes se les ha facturado más.

top_customers_by_receivables identifica a los clientes
con mayores montos documentales POR COBRAR.

Si la pregunta contiene "deben", "deudores",
"me adeudan" o "clientes por cobrar", selecciona
top_customers_by_receivables.

No utilices sales_overview para identificar
clientes deudores. uniqueCustomers solamente
representa una cantidad de clientes.

La palabra "cliente" por sí sola NO implica
que debas seleccionar sales_overview.

Si la pregunta pide identificar, comparar u ordenar
clientes según montos facturados, utiliza
top_customers_by_sales.

El campo uniqueCustomers es únicamente una cantidad.
NO contiene nombres de clientes ni montos individuales.


Cada argumento debe contener un único valor escalar
(string, número o null), nunca una lista ni un objeto.

Los valores mostrados en el catálogo representan
opciones permitidas, no listas que debas devolver.

Por ejemplo, si document_type permite:
["all", "invoice", "credit_note"]

Y necesitas facturas, debes devolver:
"document_type": "invoice"

NO debes devolver:
"document_type": ["invoice"]

No omitas condiciones expresadas por el usuario.

No inventes filtros que el usuario no haya solicitado.

Si la herramienta permite responder solamente una
parte de la pregunta, no la selecciones.

No incluyas business_id, year ni month dentro de
arguments. Esos valores son administrados por
la aplicación.

HERRAMIENTAS DISPONIBLES:

{tools_description}

CONTEXTO TEMPORAL YA RESUELTO:

year: {year}
month: {month}

PREGUNTA:

{question}

Responde exclusivamente con JSON:

{{
  "tool": "nombre_de_herramienta",
  "arguments": {{
    "nombre_argumento": "valor_permitido"
  }},
  "reason": "explicación breve"
}}

Si ninguna herramienta disponible permite obtener
la información necesaria, responde:

{{
  "tool": null,
  "arguments": {{}},
  "reason": "explicación breve"
}}
""".strip()

    plan = _call_ollama_json(prompt)
    
    
    # Diagnóstico temporal del planner
    print("\n=== OLLAMA RAW PLAN ===")
    print(json.dumps(
        plan,
        indent=2,
        ensure_ascii=False,
    ))
    print("=======================\n")


    tool_name = plan.get("tool")

    if tool_name is not None:
        if (
            not isinstance(tool_name, str)
            or tool_name not in DYNAMIC_TOOLS
        ):
            raise ValueError(
                "El planner seleccionó una herramienta "
                "no autorizada."
            )
    
    # ----------------------------------------------
    # Validación estructural de argumentos
    # ----------------------------------------------

    arguments = plan.get("arguments", {})

    if not isinstance(arguments, dict):
        raise ValueError(
            "El planner debe devolver arguments como objeto."
        )
        
    # --------------------------------------------------
    # Los filtros de contexto son administrados por Xapity.
    # Ollama no puede definir ni sobrescribir estos valores.
    # --------------------------------------------------

    context_arguments = {
        "business_id",
        "year",
        "month",
    }

    ignored_context = {
        key: arguments.pop(key)
        for key in tuple(arguments)
        if key in context_arguments
    }

    if ignored_context:
        plan["ignored_context_arguments"] = ignored_context


    if tool_name is None:
        if arguments:
            raise ValueError(
                "Un plan sin herramienta no puede tener argumentos."
            )
    else:
        tool = DYNAMIC_TOOLS[tool_name]

        allowed_arguments = tool.allowed_arguments or {}
        
        # Corrección controlada:
        # uniqueCustomers es un campo de salida,
        # nunca un argumento de sales_overview.
        if (
            tool_name == "sales_overview"
            and set(arguments) == {"uniqueCustomers"}
        ):
            arguments = {}
            plan["arguments"] = arguments

        for argument, value in arguments.items():
            if argument not in allowed_arguments:
                raise ValueError(
                    f"Argumento no autorizado: {argument}"
                )

            # Normalización segura:
            # ["invoice"] -> "invoice"
            # No se aceptan listas con múltiples valores.
            if isinstance(value, list):
                if len(value) != 1:
                    raise ValueError(
                        f"El argumento {argument} debe contener "
                        "un único valor."
                    )

                value = value[0]
                arguments[argument] = value

            # Rechazar valores estructurados no permitidos.
            if isinstance(value, (list, dict)):
                raise ValueError(
                    f"Formato no autorizado para {argument}."
                )

            value = _normalize_allowed_argument(
                argument=argument,
                value=value,
                allowed_values=allowed_arguments[argument],
            )

            arguments[argument] = value

            if (
                isinstance(value, bool)
                or value not in allowed_arguments[argument]
            ):
                raise ValueError(
                    f"Valor no autorizado para {argument}: {value}"
                )

    return plan


# ==================================================
# EJECUCIÓN DE TOOL
# ==================================================


def _execute_tool(
    *,
    tool_name: str,
    business_id: int,
    year: int | None,
    month: int | None,
    arguments: dict[str, Any],
    collection: Collection | None,
) -> dict[str, Any]:
    """
    Ejecuta únicamente una herramienta registrada.
    """

    tool = DYNAMIC_TOOLS.get(tool_name)

    if tool is None:
        raise ValueError(
            f"Herramienta dinámica no soportada: {tool_name}"
        )

    kwargs: dict[str, Any] = {
        "business_id": business_id,
        "year": year,
        "month": month,
    }
    
    # Validación defensiva antes de ejecutar.
    allowed_arguments = tool.allowed_arguments or {}

    for argument, value in arguments.items():
        if argument not in allowed_arguments:
            raise ValueError(
                f"Argumento no autorizado: {argument}"
            )

        if isinstance(value, (list, dict)):
            raise ValueError(
                f"Formato no autorizado para {argument}."
            )

        if value not in allowed_arguments[argument]:
            raise ValueError(
                f"Valor no autorizado para {argument}: {value}"
            )

        kwargs[argument] = value

    if collection is not None:
        kwargs["collection"] = collection

    result = tool.handler(**kwargs)

    if not isinstance(result, dict):
        raise TypeError(
            "La herramienta dinámica debe retornar un dict."
        )

    return result


# ==================================================
# SÍNTESIS DE RESPUESTA
# ==================================================

def _format_overdue_receivable_invoices(
    tool_result: Mapping[str, Any],
) -> str:
    """
    Construye una respuesta determinista para
    facturas vencidas, sin llamar a Ollama.
    """

    result = tool_result.get("result", tool_result)

    documents = result.get("documents", [])
    total = result.get("documentsCount", 0)

    if not documents:
        return (
            "No se encontraron facturas por cobrar "
            "con fecha de vencimiento anterior a hoy."
        )

    def format_amount(value: Any) -> str:
        amount = float(value or 0)
        return f"${amount:,.0f}".replace(",", ".")

    def format_date(value: Any) -> str:
        if not isinstance(value, str) or not value:
            return "Sin fecha"

        date_part = value[:10]
        parts = date_part.split("-")

        if len(parts) != 3:
            return date_part

        return f"{parts[2]}/{parts[1]}/{parts[0]}"

    lines = [
        f"Se encontraron {total} facturas vencidas.",
        "",
        f"Estas son las {len(documents)} facturas "
        "por cobrar más atrasadas:",
        "",
    ]

    for index, document in enumerate(documents, start=1):
        customer = document.get(
            "customerName",
            "Cliente no identificado",
        )
        due_date = format_date(
            document.get("dueDate")
        )
        days = document.get("daysOverdue", 0)
        amount = format_amount(
            document.get("amount")
        )

        lines.extend([
            f"{index}. {customer}",
            f"   Vencimiento: {due_date}",
            f"   Días de atraso: {days}",
            f"   Monto documental: {amount}",
            "",
        ])

    lines.append(
        "Nota: los montos corresponden al valor "
        "documental de las facturas, no necesariamente "
        "al saldo pendiente de cobro."
    )

    return "\n".join(lines)


def _format_customer_ranking(
    *,
    tool_name: str,
    tool_result: Mapping[str, Any],
) -> str:
    """
    Construye rankings comerciales deterministas.

    Preserva exactamente los nombres y montos
    entregados por sales_query_service.
    """

    result = tool_result.get("result", {})
    customers = result.get("customers", [])

    is_receivables = (
        tool_name == "top_customers_by_receivables"
    )

    subject = (
        "monto documental por cobrar"
        if is_receivables
        else "facturación"
    )

    if not customers:
        return (
            f"No se encontraron clientes con {subject} "
            "para el período consultado."
        )

    def format_amount(value: Any) -> str:
        amount = float(value or 0)
        return f"${amount:,.0f}".replace(",", ".")

    filters = tool_result.get("filters", {})
    year = filters.get("year")
    month = filters.get("month")

    if year is not None and month is not None:
        period = f"en {int(month):02d}/{year}"
    elif year is not None:
        period = f"en {year}"
    else:
        period = "en el período consultado"

    if len(customers) == 1:
        customer = customers[0]

        answer = (
            f"El cliente con mayor {subject} {period} es "
            f"{customer['customerName']}, "
            f"con {format_amount(customer['totalAmount'])} "
            f"en {customer['invoicesCount']} facturas."
        )

    else:
        lines = [
            f"Clientes con mayor {subject} {period}:",
            "",
        ]

        for index, customer in enumerate(
            customers,
            start=1,
        ):
            lines.append(
                f"{index}. {customer['customerName']}: "
                f"{format_amount(customer['totalAmount'])} "
                f"({customer['invoicesCount']} facturas)"
            )

        answer = "\n".join(lines)

    if is_receivables:
        answer += (
            "\n\nNota: los montos corresponden al valor "
            "documental de facturas clasificadas como "
            "POR COBRAR; no incluyen parcialmente cobradas "
            "ni representan saldos efectivos verificados."
        )

    return answer


def _build_dynamic_answer(
    *,
    question: str,
    tool_name: str,
    tool_result: Mapping[str, Any],
) -> str:
    """
    Construye la respuesta final utilizando exclusivamente
    datos obtenidos desde la herramienta determinista.
    """
    if tool_name == "overdue_receivable_invoices":
        return _format_overdue_receivable_invoices(
            tool_result
        )    
    
    if tool_name in (
        "top_customers_by_sales",
        "top_customers_by_receivables",
    ):
        return _format_customer_ranking(
            tool_name=tool_name,
            tool_result=tool_result,
        )


    tool = DYNAMIC_TOOLS[tool_name]
    
    presentation_instructions = ""

    if tool_name == "overdue_receivable_invoices":
        presentation_instructions = """
        Para esta consulta:

        - Indica cuántas facturas vencidas existen en total.
        - Presenta todas las facturas incluidas en result.documents.
        - Para cada factura muestra:
        cliente, fecha de vencimiento, días de atraso
        y monto documental.
        - Mantén el orden recibido.
        - No omitas documentos.
        - No confundas monto documental con saldo pendiente.
        - No afirmes que los resultados son una muestra
        aleatoria o que no son representativos.
        - Si hay más facturas que las mostradas, indica
        que se presentan las más atrasadas.
        - No inventes información ausente.
        """

    serialized_result = json.dumps(
        tool_result,
        ensure_ascii=False,
        default=str,
    )

    prompt = f"""
Eres el asistente comercial de Xapity-Luca.

Responde la pregunta del usuario utilizando
exclusivamente la información entregada por
la herramienta.

SEMÁNTICA DEL RESULTADO:

{tool.result_semantics}

INSTRUCCIONES DE PRESENTACIÓN:

{presentation_instructions}

Examina los datos y utiliza esta semántica para
interpretar correctamente sus campos.

No inventes cifras.
No inventes clientes.
No inventes documentos.
No agregues información que no pueda deducirse
del resultado entregado.

Si el resultado realmente no contiene información
suficiente para responder la pregunta, indícalo
claramente.

Sé breve, claro y directo.

PREGUNTA:

{question}

HERRAMIENTA UTILIZADA:

{tool_name}

RESULTADO DE LA HERRAMIENTA:

{serialized_result}
""".strip()

    return _call_ollama_text(prompt)


# ==================================================
# PLANNER PÚBLICO
# ==================================================


def execute_dynamic_sales_query(
    *,
    question: str,
    business_id: int,
    year: int | None = None,
    month: int | None = None,
    collection: Collection | None = None,
) -> DynamicPlanResult | None:
    """
    Intenta resolver una consulta comercial no cubierta
    por una intención determinista.

    Flujo:

        pregunta
            ↓
        LLM selecciona tool
            ↓
        ejecución determinista
            ↓
        LLM sintetiza respuesta

    Retorna None cuando ninguna herramienta disponible
    puede resolver la consulta.
    """

    if not isinstance(question, str):
        raise TypeError(
            "question debe ser un string."
        )

    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError(
            "question no puede estar vacía."
        )

    if not isinstance(business_id, int):
        raise TypeError(
            "business_id debe ser un entero."
        )

    if business_id <= 0:
        raise ValueError(
            "business_id debe ser mayor que cero."
        )

    plan = _build_plan(
        question=normalized_question,
        year=year,
        month=month,
    )

    tool_name = plan.get("tool")

    if tool_name is None:
        return None

    tool_result = _execute_tool(
        tool_name=tool_name,
        business_id=business_id,
        year=year,
        month=month,
        arguments=plan.get("arguments", {}),
        collection=collection,
    )

    answer = _build_dynamic_answer(
        question=normalized_question,
        tool_name=tool_name,
        tool_result=tool_result,
    )

    return DynamicPlanResult(
        answer=answer,
        tool_name=tool_name,
        tool_result=tool_result,
        plan=plan,
    )