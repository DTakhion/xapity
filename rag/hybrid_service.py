# rag/hybrid_service.py
from __future__ import annotations

from typing import Any

from rag.deterministic.service import answer_deterministic_question
from rag.service import answer_user_question


DETERMINISTIC_THRESHOLD = 0.70
RAG_CONFIDENCE_ACCEPTED = {"high", "medium"}

def map_numeric_confidence(score: float | int | None) -> str:
    """
    Convierte confianza numérica determinística al formato
    high | medium | low | none.
    """
    try:
        numeric_score = float(score or 0.0)
    except (TypeError, ValueError):
        return "none"

    if numeric_score >= 0.85:
        return "high"

    if numeric_score >= 0.70:
        return "medium"

    if numeric_score > 0:
        return "low"

    return "none"


def build_fallback_response(query: str) -> dict[str, Any]:
    return {
        "status": "no_context",
        "mode": "fallback",
        "answer": (
            "No encontré información suficiente en el manual disponible "
            "para responder con certeza."
        ),
        "query": query,
        "confidence": "none",
        "sources": [],
        "matches_count": 0,
    }


def answer_hybrid_question(
    query: str,
    deterministic_threshold: float = DETERMINISTIC_THRESHOLD,
) -> dict[str, Any]:
    """
    Orquestador híbrido Xapity-MAF.

    Flujo:
    1. Intenta responder con motor determinístico.
    2. Si no hay match suficiente, usa RAG.
    3. Si RAG no encuentra contexto útil, entrega fallback seguro.
    """

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "mode": "hybrid",
            "answer": "La pregunta no puede estar vacía.",
            "query": query,
            "confidence": "none",
            "sources": [],
            "matches_count": 0,
        }

    deterministic_result = answer_deterministic_question(
        question=query,
        confidence_threshold=deterministic_threshold,
    )

    if deterministic_result.get("matched") is True:
        deterministic_source = deterministic_result.get("source")

        return {
            "status": "answered",
            "mode": "deterministic",
            "answer": deterministic_result.get("answer"),
            "query": query,
            "confidence": map_numeric_confidence(
                deterministic_result.get("confidence")
            ),
            "benefitId": deterministic_result.get("benefitId"),
            "title": deterministic_result.get("title"),
            "category": deterministic_result.get("category"),
            "sources": (
                [deterministic_source]
                if deterministic_source
                else []
            ),
            "matches_count": 1,
            "metadata": deterministic_result.get("metadata", {}),
        }

    try:
        rag_result = answer_user_question(query)

    except Exception as exc:
        fallback = build_fallback_response(query)

        fallback["status"] = "rag_error"
        fallback["mode"] = "fallback"

        fallback["deterministic_attempt"] = {
            "matched": deterministic_result.get("matched"),
            "confidence": deterministic_result.get("confidence"),
            "benefitId": deterministic_result.get("benefitId"),
            "title": deterministic_result.get("title"),
            "reason": deterministic_result.get("reason"),
        }

        fallback["rag_attempt"] = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

        return fallback

    if rag_result.get("status") == "answered":
        return {
            "status": "answered",
            "mode": "rag",
            "answer": rag_result.get("answer"),
            "query": query,
            "confidence": rag_result.get("confidence"),
            "sources": rag_result.get("sources", []),
            "matches_count": rag_result.get("matches_count", 0),
            "deterministic_attempt": {
                "matched": deterministic_result.get("matched"),
                "confidence": deterministic_result.get("confidence"),
                "benefitId": deterministic_result.get("benefitId"),
                "title": deterministic_result.get("title"),
                "reason": deterministic_result.get("reason"),
            },
        }

    fallback = build_fallback_response(query)

    fallback["deterministic_attempt"] = {
        "matched": deterministic_result.get("matched"),
        "confidence": deterministic_result.get("confidence"),
        "benefitId": deterministic_result.get("benefitId"),
        "title": deterministic_result.get("title"),
        "reason": deterministic_result.get("reason"),
    }

    fallback["rag_attempt"] = {
        "status": rag_result.get("status"),
        "confidence": rag_result.get("confidence"),
        "matches_count": rag_result.get("matches_count"),
        "sources": rag_result.get("sources", []),
        "error_detail": rag_result.get("error_detail"),
    }

    return fallback


if __name__ == "__main__":
    test_questions = [
        "¿Cuánto pagan por natalidad?",
        "¿Qué documentos necesito para el bono de natalidad?",
        "¿Qué pasa si ambos padres trabajan en MAF?",
        "¿Cuántos días tengo por matrimonio?",
        "¿Tienen convenio con gimnasio?",
    ]

    for question in test_questions:
        response = answer_hybrid_question(question)

        print("\n========================")
        print(f"Pregunta: {question}")
        print(f"Status: {response.get('status')}")
        print(f"Mode: {response.get('mode')}")
        print(f"Confidence: {response.get('confidence')}")
        print(f"BenefitId: {response.get('benefitId')}")
        print(f"Title: {response.get('title')}")
        print(f"Matches: {response.get('matches_count')}")
        print(f"Answer:\n{response.get('answer')}")