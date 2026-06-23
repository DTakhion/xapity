# # rag/deterministic/matcher.py
# from __future__ import annotations

# import re
# import unicodedata
# from typing import Any


# def normalize_text(text: str) -> str:
#     """
#     Normaliza texto:
#     - minúsculas
#     - elimina tildes
#     - elimina caracteres especiales
#     """
#     text = text.lower()

#     text = unicodedata.normalize("NFD", text)
#     text = "".join(c for c in text if unicodedata.category(c) != "Mn")

#     text = re.sub(r"[^a-z0-9\s]", " ", text)
#     text = re.sub(r"\s+", " ", text).strip()

#     return text


# def tokenize(text: str) -> set[str]:
#     """
#     Tokenización simple.
#     """
#     normalized = normalize_text(text)
#     return set(normalized.split())


# def calculate_overlap_score(
#     question_tokens: set[str],
#     candidate_tokens: set[str],
# ) -> float:
#     """
#     Calcula overlap simple orientado a la pregunta.

#     La confianza se calcula respecto de los tokens de la pregunta,
#     no respecto del texto completo del beneficio.
#     """
#     if not question_tokens:
#         return 0.0

#     overlap = question_tokens.intersection(candidate_tokens)

#     return len(overlap) / len(question_tokens)


# def build_benefit_search_text(benefit: dict[str, Any]) -> str:
#     """
#     Construye texto consolidado para matching.
#     """

#     parts: list[str] = []

#     parts.append(benefit.get("title", ""))
#     parts.append(benefit.get("summary", ""))

#     # tags
#     metadata = benefit.get("metadata", {})
#     tags = metadata.get("tags", [])

#     if tags:
#         parts.extend(tags)

#     # humanQuestions
#     for q in benefit.get("humanQuestions", []):
#         parts.append(q)

#     # chunks
#     for chunk in benefit.get("chunks", []):
#         parts.append(chunk.get("content", ""))

#     return " ".join(parts)


# def match_benefit(
#     question: str,
#     benefits: list[dict[str, Any]],
# ) -> dict[str, Any]:
#     """
#     Busca el beneficio más cercano para una pregunta.
#     """

#     question_tokens = tokenize(question)

#     best_match = None
#     best_score = 0.0

#     for benefit in benefits:
#         search_text = build_benefit_search_text(benefit)

#         candidate_tokens = tokenize(search_text)

#         score = calculate_overlap_score(
#             question_tokens=question_tokens,
#             candidate_tokens=candidate_tokens,
#         )

#         if score > best_score:
#             best_score = score
#             best_match = benefit

#     return {
#         "question": question,
#         "matched": best_match is not None,
#         "confidence": round(best_score, 4),
#         "benefit": best_match,
#     }


# if __name__ == "__main__":
#     from rag.deterministic.loader import load_structured_benefits

#     benefits = load_structured_benefits()

#     test_questions = [
#         "¿Cuánto pagan por natalidad?",
#         "¿Qué pasa si ambos padres trabajan en MAF?",
#         "¿Cuántos días tengo por matrimonio?",
#     ]

#     for question in test_questions:
#         result = match_benefit(question, benefits)

#         benefit = result.get("benefit")

#         print("\n========================")
#         print(f"Pregunta: {question}")
#         print(f"Confidence: {result['confidence']}")

#         if benefit:
#             print(f"BenefitId: {benefit.get('benefitId')}")
#             print(f"Title: {benefit.get('title')}")

# rag/deterministic/matcher.py
from __future__ import annotations

import re
import unicodedata
from typing import Any


MIN_CONFIDENCE = 0.70 # 0.55


STOPWORDS_ES = {
    "a", "al", "algo", "ante", "antes", "como", "con", "contra", "cual",
    "cuando", "cuanto", "cuantos", "cuanta", "cuantas", "de", "del", "desde",
    "donde", "dos", "el", "ella", "ellas", "ellos", "en", "entre", "era",
    "eres", "es", "esa", "esas", "ese", "eso", "esos", "esta", "estas",
    "este", "esto", "estos", "haber", "hay", "la", "las", "le", "les",
    "lo", "los", "mas", "me", "mi", "mis", "no", "nos", "o", "para",
    "pero", "por", "porque", "que", "quien", "se", "si", "sin", "sobre",
    "son", "su", "sus", "te", "tengo", "tiene", "tienen", "tu", "un",
    "una", "unas", "uno", "unos", "y", "ya", "yo",
    "maf", "empresa", "colaborador", "colaboradores", "trabajador",
    "trabajadores", "beneficio", "beneficios", "bono", "necesito", "documento", "documentos", "requiere", "requerido", "requeridos",
}


FIELD_WEIGHTS = {
    "title": 3.0,
    "tags": 2.5,
    "humanQuestions": 2.4,
    "documents": 2.2,
    "summary": 1.5,
    "restrictions": 1.3,
    "chunks": 1.0,
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str, remove_stopwords: bool = True) -> set[str]:
    normalized = normalize_text(text)
    tokens = set(normalized.split())

    if remove_stopwords:
        tokens = {
            token
            for token in tokens
            if token not in STOPWORDS_ES and len(token) >= 3
        }

    return tokens


def token_overlap_score(
    question_tokens: set[str],
    candidate_tokens: set[str],
) -> float:
    if not question_tokens or not candidate_tokens:
        return 0.0

    overlap = question_tokens.intersection(candidate_tokens)
    return len(overlap) / len(question_tokens)


def field_score(question_tokens: set[str], text: str, weight: float) -> float:
    candidate_tokens = tokenize(text)
    return token_overlap_score(question_tokens, candidate_tokens) * weight


# def build_field_texts(benefit: dict[str, Any]) -> dict[str, str]:
#     metadata = benefit.get("metadata", {})
#     tags = metadata.get("tags", [])

#     human_questions = benefit.get("humanQuestions", [])
#     chunks = benefit.get("chunks", [])

#     return {
#         "title": benefit.get("title", ""),
#         "summary": benefit.get("summary", ""),
#         "tags": " ".join(tags),
#         "humanQuestions": " ".join(human_questions),
#         "chunks": " ".join(chunk.get("content", "") for chunk in chunks),
#     }

def build_field_texts(benefit: dict[str, Any]) -> dict[str, str]:
    metadata = benefit.get("metadata", {})
    tags = metadata.get("tags", [])

    human_questions = benefit.get("humanQuestions", [])
    chunks = benefit.get("chunks", [])
    documents = benefit.get("documents", [])
    restrictions = benefit.get("restrictions", [])

    document_parts = []
    for doc in documents:
        document_parts.append(doc.get("name", ""))
        document_parts.append(doc.get("issuer", ""))

    restriction_parts = [
        restriction.get("description", "")
        for restriction in restrictions
    ]

    return {
        "title": benefit.get("title", ""),
        "summary": benefit.get("summary", ""),
        "tags": " ".join(tags),
        "humanQuestions": " ".join(human_questions),
        "documents": " ".join(document_parts),
        "restrictions": " ".join(restriction_parts),
        "chunks": " ".join(chunk.get("content", "") for chunk in chunks),
    }


def score_benefit(
    question: str,
    benefit: dict[str, Any],
) -> dict[str, Any]:
    question_tokens = tokenize(question)

    field_texts = build_field_texts(benefit)

    weighted_scores: dict[str, float] = {}

    for field_name, field_text in field_texts.items():
        weight = FIELD_WEIGHTS.get(field_name, 1.0)
        weighted_scores[field_name] = field_score(
            question_tokens=question_tokens,
            text=field_text,
            weight=weight,
        )

    max_possible = max(FIELD_WEIGHTS.values())

    raw_score = max(weighted_scores.values()) if weighted_scores else 0.0
    confidence = raw_score / max_possible if max_possible else 0.0

    matched_terms = sorted(
        question_tokens.intersection(
            tokenize(" ".join(field_texts.values()))
        )
    )

    return {
        "benefit": benefit,
        "confidence": round(confidence, 4),
        "raw_score": round(raw_score, 4),
        "matched_terms": matched_terms,
        "field_scores": {
            key: round(value, 4)
            for key, value in weighted_scores.items()
        },
    }


def match_benefit(
    question: str,
    benefits: list[dict[str, Any]],
    min_confidence: float = MIN_CONFIDENCE,
    top_n: int = 3,
) -> dict[str, Any]:
    question = question.strip()

    if not question:
        return {
            "question": question,
            "matched": False,
            "confidence": 0.0,
            "benefit": None,
            "candidates": [],
            "reason": "empty_question",
        }

    candidates = [
        score_benefit(question, benefit)
        for benefit in benefits
    ]

    candidates.sort(
        key=lambda item: item["confidence"],
        reverse=True,
    )

    best = candidates[0] if candidates else None

    matched = bool(best and best["confidence"] >= min_confidence)

    return {
        "question": question,
        "matched": matched,
        "confidence": best["confidence"] if best else 0.0,
        "benefit": best["benefit"] if matched else None,
        "best_candidate": best,
        "candidates": candidates[:top_n],
        "min_confidence": min_confidence,
    }


if __name__ == "__main__":
    from loader import load_structured_benefits

    benefits = load_structured_benefits()

    test_questions = [
        "¿Cuánto pagan por natalidad?",
        "¿Qué pasa si ambos padres trabajan en MAF?",
        "¿Cuántos días tengo por matrimonio?",
        "¿Cuánto es el bono de escolaridad?",
    ]

    for question in test_questions:
        result = match_benefit(question, benefits)

        print("\n========================")
        print(f"Pregunta: {question}")
        print(f"Matched: {result['matched']}")
        print(f"Confidence: {result['confidence']}")

        benefit = result.get("benefit")
        if benefit:
            print(f"BenefitId: {benefit.get('benefitId')}")
            print(f"Title: {benefit.get('title')}")

        print("\nTop candidates:")
        for candidate in result["candidates"]:
            candidate_benefit = candidate["benefit"]
            print(
                f"- {candidate_benefit.get('benefitId')} | "
                f"{candidate_benefit.get('title')} | "
                f"confidence={candidate['confidence']} | "
                f"terms={candidate['matched_terms']}"
            )