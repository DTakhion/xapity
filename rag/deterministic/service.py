# rag/deterministic/service.py

from __future__ import annotations

from pathlib import Path
from typing import Any

from rag.deterministic.loader import (
    DEFAULT_STRUCTURED_DIR,
    load_structured_benefits,
)
from rag.deterministic.matcher import match_benefit
from rag.deterministic.responder import build_deterministic_answer


DEFAULT_CONFIDENCE_THRESHOLD = 0.70


def answer_deterministic_question(
    question: str,
    structured_dir: Path | str = DEFAULT_STRUCTURED_DIR,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """
    Responde una pregunta usando únicamente el conocimiento estructurado
    disponible en rag/structured/*.json.

    No usa embeddings.
    No usa LLM.
    No consulta Mongo.
    No persiste información.
    """

    benefits = load_structured_benefits(structured_dir)

    match = match_benefit(
        question=question,
        benefits=benefits,
    )

    benefit = match.get("benefit")
    confidence = match.get("confidence", 0.0)

    if not benefit or confidence < confidence_threshold:
        return {
            "mode": "deterministic",
            "matched": False,
            "confidence": confidence,
            "benefitId": benefit.get("benefitId") if benefit else None,
            "title": benefit.get("title") if benefit else None,
            "answer": None,
            "reason": "No deterministic match above confidence threshold.",
        }

    return build_deterministic_answer(
        question=question,
        benefit=benefit,
        confidence=confidence,
    )


if __name__ == "__main__":
    test_questions = [
        "¿Cuánto pagan por natalidad?",
        "¿Qué documentos necesito para el bono de natalidad?",
        "¿Qué pasa si ambos padres trabajan en MAF?",
        "¿Cuántos días tengo por matrimonio?",
        "¿Tienen convenio con gimnasio?",
    ]

    for question in test_questions:
        response = answer_deterministic_question(question)

        print("\n========================")
        print(f"Pregunta: {question}")
        print(f"Matched: {response['matched']}")
        print(f"Mode: {response['mode']}")
        print(f"Confidence: {response['confidence']}")
        print(f"BenefitId: {response.get('benefitId')}")
        print(f"Title: {response.get('title')}")
        print(f"Reason: {response.get('reason')}")
        print(f"Answer:\n{response.get('answer')}")