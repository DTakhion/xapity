# rag/deterministic/matcher.py
from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> str:
    """
    Normaliza texto:
    - minúsculas
    - elimina tildes
    - elimina caracteres especiales
    """
    text = text.lower()

    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text: str) -> set[str]:
    """
    Tokenización simple.
    """
    normalized = normalize_text(text)
    return set(normalized.split())


def calculate_overlap_score(
    question_tokens: set[str],
    candidate_tokens: set[str],
) -> float:
    """
    Calcula overlap simple orientado a la pregunta.

    La confianza se calcula respecto de los tokens de la pregunta,
    no respecto del texto completo del beneficio.
    """
    if not question_tokens:
        return 0.0

    overlap = question_tokens.intersection(candidate_tokens)

    return len(overlap) / len(question_tokens)


def build_benefit_search_text(benefit: dict[str, Any]) -> str:
    """
    Construye texto consolidado para matching.
    """

    parts: list[str] = []

    parts.append(benefit.get("title", ""))
    parts.append(benefit.get("summary", ""))

    # tags
    metadata = benefit.get("metadata", {})
    tags = metadata.get("tags", [])

    if tags:
        parts.extend(tags)

    # humanQuestions
    for q in benefit.get("humanQuestions", []):
        parts.append(q)

    # chunks
    for chunk in benefit.get("chunks", []):
        parts.append(chunk.get("content", ""))

    return " ".join(parts)


def match_benefit(
    question: str,
    benefits: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Busca el beneficio más cercano para una pregunta.
    """

    question_tokens = tokenize(question)

    best_match = None
    best_score = 0.0

    for benefit in benefits:
        search_text = build_benefit_search_text(benefit)

        candidate_tokens = tokenize(search_text)

        score = calculate_overlap_score(
            question_tokens=question_tokens,
            candidate_tokens=candidate_tokens,
        )

        if score > best_score:
            best_score = score
            best_match = benefit

    return {
        "question": question,
        "matched": best_match is not None,
        "confidence": round(best_score, 4),
        "benefit": best_match,
    }


if __name__ == "__main__":
    from rag.deterministic.loader import load_structured_benefits

    benefits = load_structured_benefits()

    test_questions = [
        "¿Cuánto pagan por natalidad?",
        "¿Qué pasa si ambos padres trabajan en MAF?",
        "¿Cuántos días tengo por matrimonio?",
    ]

    for question in test_questions:
        result = match_benefit(question, benefits)

        benefit = result.get("benefit")

        print("\n========================")
        print(f"Pregunta: {question}")
        print(f"Confidence: {result['confidence']}")

        if benefit:
            print(f"BenefitId: {benefit.get('benefitId')}")
            print(f"Title: {benefit.get('title')}")