# rag/deterministic/responder.py

from __future__ import annotations

from typing import Any


def _format_amount(rule: dict[str, Any]) -> str | None:
    amount = rule.get("amount")
    currency = rule.get("currency", "CLP")
    gross_amount = rule.get("grossAmount")

    if amount is None:
        return None

    formatted = f"${amount:,.0f}".replace(",", ".")

    if currency == "CLP":
        formatted = f"{formatted} CLP"

    if gross_amount is True:
        formatted += " brutos"

    return formatted


def _get_amount_text(benefit: dict[str, Any]) -> str | None:
    for rule in benefit.get("rules", []):
        amount_text = _format_amount(rule)

        if amount_text:
            return amount_text

    return None


def _get_documents_text(benefit: dict[str, Any]) -> list[str]:
    documents: list[str] = []

    for doc in benefit.get("documents", []):
        name = doc.get("name")
        issuer = doc.get("issuer")
        required = doc.get("required", False)

        if not name:
            continue

        text = name

        if issuer:
            text += f" emitido por {issuer}"

        if required:
            text += " (obligatorio)"

        documents.append(text)

    return documents


def _get_rules_descriptions(benefit: dict[str, Any]) -> list[str]:
    return [
        rule.get("description", "")
        for rule in benefit.get("rules", [])
        if rule.get("description")
    ]


def _get_restrictions_descriptions(benefit: dict[str, Any]) -> list[str]:
    return [
        restriction.get("description", "")
        for restriction in benefit.get("restrictions", [])
        if restriction.get("description")
    ]


def build_deterministic_answer(
    question: str,
    benefit: dict[str, Any],
    confidence: float,
) -> dict[str, Any]:
    """
    Construye una respuesta determinística usando solo el JSON estructurado.
    """

    title = benefit.get("title", "beneficio")
    summary = benefit.get("summary")
    source = benefit.get("source", {})
    metadata = benefit.get("metadata", {})
    chatbot_behavior = benefit.get("chatbotBehavior", {})

    answer_parts: list[str] = []

    if summary:
        answer_parts.append(summary)
    else:
        answer_parts.append(f"Según la información estructurada disponible, el beneficio corresponde a {title}.")

    amount_text = _get_amount_text(benefit)
    if amount_text:
        answer_parts.append(f"El monto indicado es {amount_text}.")

    documents = _get_documents_text(benefit)
    if documents:
        answer_parts.append(
            "Documentación requerida: " + "; ".join(documents) + "."
        )

    restrictions = _get_restrictions_descriptions(benefit)
    if restrictions:
        answer_parts.append(
            "Restricciones relevantes: " + " ".join(restrictions)
        )

    if chatbot_behavior.get("mustAvoidPersonalValidation"):
        answer_parts.append(
            "Esta respuesta no valida tu elegibilidad individual; para confirmar tu caso particular debes consultar con Gestión de Personas."
        )

    valid_from = source.get("validFrom")
    valid_to = source.get("validTo")

    if valid_from and valid_to:
        answer_parts.append(
            f"Vigencia documental considerada: desde {valid_from} hasta {valid_to}."
        )

    return {
        "mode": "deterministic",
        "matched": True,
        "confidence": confidence,
        "benefitId": benefit.get("benefitId"),
        "title": title,
        "category": benefit.get("category"),
        "answer": " ".join(answer_parts),
        "source": source,
        "metadata": {
            "requiresDocumentation": metadata.get("requiresDocumentation"),
            "requiresHRValidation": metadata.get("requiresHRValidation"),
            "hasMonetaryAmount": metadata.get("hasMonetaryAmount"),
            "hasDays": metadata.get("hasDays"),
            "legalBenefit": metadata.get("legalBenefit"),
            "corporateBenefit": metadata.get("corporateBenefit"),
        },
    }


if __name__ == "__main__":
    from rag.deterministic.loader import load_structured_benefits
    from rag.deterministic.matcher import match_benefit

    benefits = load_structured_benefits()

    test_questions = [
        "¿Cuánto pagan por natalidad?",
        "¿Qué documentos necesito para el bono de natalidad?",
        "¿Qué pasa si ambos padres trabajan en MAF?",
        "¿Cuántos días tengo por matrimonio?",
    ]

    for question in test_questions:
        match = match_benefit(question, benefits)

        benefit = match.get("benefit")

        print("\n========================")
        print(f"Pregunta: {question}")
        print(f"Confidence: {match['confidence']}")

        if not benefit:
            print("Sin beneficio detectado.")
            continue

        response = build_deterministic_answer(
            question=question,
            benefit=benefit,
            confidence=match["confidence"],
        )

        print(f"Mode: {response['mode']}")
        print(f"BenefitId: {response['benefitId']}")
        print(f"Title: {response['title']}")
        print(f"Answer:\n{response['answer']}")