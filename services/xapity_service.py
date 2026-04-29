# services/xapity_service.py

from __future__ import annotations

import json
import re
import unicodedata

from schemas.xapity_chat import XapityIntentAnalysis
from services.ollama_client import generate


INTENT_MODEL_TEMPERATURE = 0.0

ALLOWED_INTENTS = {"greeting", "farewell", "list_services", "sales_total", "unknown"}


def normalize_message(text: str) -> str:
    """
    Normaliza el mensaje para facilitar detección semántica y fallback liviano.
    - trim
    - lowercase
    - sin acentos
    - sin puntuación periférica
    - espacios normalizados
    """
    text = text.strip().lower()

    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def detect_intent_fastpath(message: str) -> XapityIntentAnalysis | None:
    """
    Fallback mínimo para casos ultra evidentes.
    No reemplaza a la IA: solo evita errores torpes en inputs muy cortos.
    """
    normalized = normalize_message(message)

    greeting_aliases = {
        "hola",
        "buenas",
        "buenos dias",
        "buen dia",
        "buenas tardes",
        "buenas noches",
        "holi",
        "hello",
        "hi",
    }

    farewell_aliases = {
        "chao",
        "adios",
        "nos vemos",
        "hasta luego",
        "hasta pronto",
        "bye",
        "gracias chao",
        "ok chao",
    }

    list_services_aliases = {
        "servicios",
        "servicio",
        "que servicios",
        "que servicios tienes",
        "servicios disponibles",
        "ver servicios",
        "mostrar servicios",
        "lista de servicios",
    }

    if normalized in greeting_aliases:
        return XapityIntentAnalysis(
            intent="greeting",
            confidence=0.98,
            is_ambiguous=False,
            has_noise=False,
            needs_clarification=False,
        )

    if normalized in farewell_aliases:
        return XapityIntentAnalysis(
            intent="farewell",
            confidence=0.98,
            is_ambiguous=False,
            has_noise=False,
            needs_clarification=False,
        )

    if normalized in list_services_aliases:
        return XapityIntentAnalysis(
            intent="list_services",
            confidence=0.98,
            is_ambiguous=False,
            has_noise=False,
            needs_clarification=False,
        )
    
    sales_keywords = {
        "venta",
        "ventas",
        "ingreso",
        "ingresos",
        "monto total",
        "total ventas",
        "total ingresos",
        "ingresos por venta",
        "concepto de venta",
    }

    if any(keyword in normalized for keyword in sales_keywords):
        return XapityIntentAnalysis(
            intent="sales_total",
            confidence=0.9,
            is_ambiguous=False,
            has_noise=False,
            needs_clarification=False,
        )

    return None


def build_intent_prompt(message: str) -> str:
    """
    Construye un prompt cerrado para que Ollama actúe solo como
    clasificador de intención de Xapity.
    """
    return f"""
Eres un clasificador de intención para Xapity.

Tu tarea es analizar el mensaje del usuario y devolver únicamente un JSON válido.
No respondas explicaciones.
No agregues texto antes ni después del JSON.
No inventes intenciones fuera de las permitidas.

Intenciones permitidas:
- greeting
- farewell
- list_services
- sales_total
- unknown

Definiciones:
1. Usa "greeting" cuando el usuario salude o abra la conversación.
   Ejemplos:
   - hola
   - buenas
   - buenos días
   - hola xapity

2. Usa "farewell" cuando el usuario se despida o cierre la conversación.
   Ejemplos:
   - chao
   - adiós
   - nos vemos
   - hasta luego
   - gracias, chao

3. Usa "list_services" cuando el usuario quiera ver, conocer, listar, consultar,
   mostrar o revisar los servicios disponibles del sistema, negocio o aplicación.
   Esto incluye mensajes breves, directos o telegráficos como:
   - servicios
   - servicios?
   - qué servicios
   - ver servicios
   - lista de servicios

4. Usa "sales_total" cuando el usuario quiera conocer el monto total de ventas,
   ingresos por venta, ventas de un periodo, ingresos comerciales o total vendido.
   Ejemplos:
   - cuál es el monto total de ingresos por concepto de venta el mes pasado
   - cuánto vendí en marzo
   - total de ventas del mes pasado
   - ingresos por ventas entre el 1 y el 31 de marzo

5. Usa "unknown" cuando el mensaje sea realmente ambiguo, incoherente, demasiado ruidoso
   o no exprese una intención razonablemente inferible.

Criterios importantes:
- No trates los mensajes cortos como ruido solo por ser cortos.
- Si la intención es razonablemente clara, no pidas aclaración.
- Solo marca "has_noise" como true si existe ruido real.
- Solo marca "is_ambiguous" como true si hay más de una interpretación razonable.
- Solo marca "needs_clarification" como true si de verdad falta contexto para actuar.

Debes devolver exactamente este formato JSON:
{
  "intent": "greeting | farewell | list_services | sales_total | unknown",
  "confidence": 0.0,
  "is_ambiguous": false,
  "has_noise": false,
  "needs_clarification": false
}

Mensaje del usuario:
\"\"\"{message}\"\"\"
""".strip()


def _extract_json_object(raw_text: str) -> dict:
    """
    Extrae el primer objeto JSON válido desde un texto.
    """
    raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")

    candidate = match.group(0)
    parsed = json.loads(candidate)

    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON is not an object.")

    return parsed


def parse_intent_response(raw_text: str) -> XapityIntentAnalysis:
    """
    Parsea y valida la respuesta del modelo hacia el schema interno.
    """
    parsed = _extract_json_object(raw_text)

    intent = str(parsed.get("intent", "unknown")).strip()
    if intent not in ALLOWED_INTENTS:
        intent = "unknown"

    try:
        confidence = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))

    is_ambiguous = bool(parsed.get("is_ambiguous", False))
    has_noise = bool(parsed.get("has_noise", False))
    needs_clarification = bool(parsed.get("needs_clarification", False))

    if intent == "unknown":
        confidence = min(confidence, 0.4)
        needs_clarification = True

    if intent in {"greeting", "farewell", "list_services", "sales_total"}:
        is_ambiguous = False if confidence >= 0.7 else is_ambiguous
        has_noise = False if confidence >= 0.7 else has_noise
        needs_clarification = False if confidence >= 0.7 else needs_clarification

    return XapityIntentAnalysis(
        intent=intent,
        confidence=confidence,
        is_ambiguous=is_ambiguous,
        has_noise=has_noise,
        needs_clarification=needs_clarification,
    )


def fallback_unknown_analysis() -> XapityIntentAnalysis:
    """
    Respuesta segura por defecto cuando el modelo falla.
    """
    return XapityIntentAnalysis(
        intent="unknown",
        confidence=0.0,
        is_ambiguous=False,
        has_noise=False,
        needs_clarification=True,
    )


# def detect_xapity_intent(message: str, model: str | None = None) -> XapityIntentAnalysis:
#     """
#     Detecta la intención del usuario usando:
#     1. fast-path mínimo para casos evidentes
#     2. Ollama como clasificador principal
#     3. fallback seguro si algo falla
#     """
#     try:
#         fastpath = detect_intent_fastpath(message)
#         if fastpath is not None:
#             return fastpath

#         prompt = build_intent_prompt(message)

#         llm_out = generate(
#             prompt=prompt,
#             model=model,
#             temperature=INTENT_MODEL_TEMPERATURE,
#         )

#         raw_response = llm_out.get("response", "")
#         if not isinstance(raw_response, str) or not raw_response.strip():
#             return fallback_unknown_analysis()

#         return parse_intent_response(raw_response)

#     except Exception:
#         return fallback_unknown_analysis()

def detect_xapity_intent(
    message: str,
    model: str | None = None,
) -> tuple[XapityIntentAnalysis, str]:
    """
    Detecta la intención del usuario usando:
    1. fast-path mínimo para casos evidentes
    2. Ollama como clasificador principal
    3. fallback seguro si algo falla

    Retorna:
    - analysis
    - detection_source: "fastpath" | "ollama" | "fallback"
    """
    try:
        fastpath = detect_intent_fastpath(message)
        if fastpath is not None:
            return fastpath, "fastpath"

        prompt = build_intent_prompt(message)

        llm_out = generate(
            prompt=prompt,
            model=model,
            temperature=INTENT_MODEL_TEMPERATURE,
        )

        raw_response = llm_out.get("response", "")
        if not isinstance(raw_response, str) or not raw_response.strip():
            return fallback_unknown_analysis(), "fallback"

        return parse_intent_response(raw_response), "ollama"

    except Exception:
        return fallback_unknown_analysis(), "fallback"


def build_xapity_reply(analysis: XapityIntentAnalysis, total: int | None = None) -> str:
    """
    Construye una respuesta amigable de Xapity en función del análisis detectado.
    """
    if analysis.intent == "greeting":
        return "Hola, soy Xapity. ¿En qué te puedo ayudar hoy?"

    if analysis.intent == "farewell":
        return "Perfecto, nos vemos. Cuando quieras, aquí estaré para ayudarte."

    if analysis.intent == "list_services":
        if total is None:
            return "Claro, te puedo mostrar los servicios disponibles."

        if total == 0:
            return "Por ahora no tengo servicios disponibles para mostrarte."

        if total == 1:
            return "Claro, tengo 1 servicio disponible en este momento."

        return f"Claro, tengo {total} servicios disponibles en este momento."
    
    if analysis.intent == "sales_total":
        return "Claro, puedo consultar el monto total de ingresos por ventas para el periodo solicitado."

    return (
        "No logré entender bien tu solicitud. "
        "Puedes preguntarme, por ejemplo: '¿Qué servicios tienes disponibles?'"
    )