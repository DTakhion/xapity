# rag/scripts/answer_with_context.py
from pathlib import Path
import sys
import json
import requests


# =========================
# Paths
# =========================

CURRENT_DIR = Path(__file__).resolve().parent
RAG_DIR = CURRENT_DIR.parent

sys.path.append(str(CURRENT_DIR))

from retrieve_context import retrieve_context  # noqa: E402


# =========================
# Configuración
# =========================

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

# Puedes cambiar luego a mistral, llama3, gemma, etc.
LLM_MODEL_NAME = "llama3.2:3b"  #"llama3"

TOP_K = 2
MIN_SCORE = 0.68


# =========================
# Prompt RAG
# =========================

# def build_context(matches: list[dict]) -> str:
#     """
#     Convierte los chunks recuperados en contexto legible para el LLM.
#     """
#     context_blocks = []

#     for index, match in enumerate(matches, start=1):
#         metadata = match.get("metadata", {})

#         block = f"""
# [Contexto {index}]
# Fuente: {metadata.get("source")}
# Página: {metadata.get("page")}
# Score: {match.get("score")}

# Texto:
# {match.get("text")}
# """
#         context_blocks.append(block.strip())

#     return "\n\n".join(context_blocks)

def build_context(matches: list[dict]) -> str:
    """
    Convierte los chunks recuperados en contexto legible para el LLM.
    """
    context_blocks = []

    for index, match in enumerate(matches, start=1):
        metadata = match.get("metadata", {})

        source = (
            match.get("source")
            or metadata.get("source")
            or metadata.get("document_name")
        )

        page = match.get("page") or metadata.get("page")
        section = match.get("section") or metadata.get("section")
        benefit_title = (
            match.get("benefit_title")
            or metadata.get("benefit_title")
            or "Sin título específico"
        )

        block = f"""
[Contexto {index}]
Fuente: {source}
Página: {page}
Sección: {section}
Beneficio: {benefit_title}
Score: {match.get("score")}

Texto:
{match.get("text")}
"""
        context_blocks.append(block.strip())

    return "\n\n".join(context_blocks)


def build_prompt(query: str, context: str) -> str:
    """
    Construye el prompt final para responder usando solo el contexto recuperado.
    """
    return f"""
Eres Xapity, un asistente corporativo especializado en responder preguntas sobre beneficios internos de la empresa.

INSTRUCCIONES:
- Responde únicamente usando la información entregada en el CONTEXTO.
- No inventes información ni agregues supuestos.
- Si el contexto indica que un beneficio es "único y anual", no lo describas como mensual. Puedes decir que se paga junto con la remuneración del mes correspondiente, pero no que es mensual.
- Si el contexto no contiene información suficiente para responder con certeza, indica exactamente:
  "No encontré información suficiente en el manual disponible para responder con certeza."

- Antes de responder, revisa TODOS los bloques de contexto recuperados.
- Si varios bloques contienen información complementaria sobre el mismo beneficio, intégralos en una sola respuesta.
- Si existe un permiso legal y además un permiso adicional entregado por la empresa, menciona ambos explícitamente.

- No generes listas de requisitos, límites, restricciones o excepciones si el contexto no las menciona explícitamente.
- No digas "no hay requisitos" o "no hay restricciones" a menos que el contexto lo indique expresamente.
- Responde de forma breve, natural y útil para un colaborador.
- No menciones scores internos, chunks, embeddings ni detalles técnicos.
- Puedes mencionar la página del manual si ayuda.
- Distingue claramente entre beneficios legales y beneficios adicionales otorgados por la empresa.
- No confundas beneficios legales con beneficios corporativos adicionales.

CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{query}

RESPUESTA:
""".strip()


# =========================
# Ollama
# =========================

def generate_answer(prompt: str) -> str:
    """
    Genera respuesta final usando Ollama.
    """
    payload = {
        "model": LLM_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
        },
    }

    response = requests.post(
        OLLAMA_GENERATE_URL,
        json=payload,
        timeout=180,
    )

    response.raise_for_status()

    data = response.json()
    return data.get("response", "").strip()


def answer_with_context(query: str) -> dict:
    """
    Recupera contexto y genera respuesta final.
    """
    retrieval = retrieve_context(
        query=query,
        top_k=TOP_K,
        min_score=MIN_SCORE,
    )

    matches = retrieval.get("matches", [])

    if not matches:
        return {
            "query": query,
            "answer": "No encontré información suficiente en el manual disponible para responder con certeza.",
            "matches_count": 0,
            "sources": [],
        }

    context = build_context(matches)
    prompt = build_prompt(query, context)
    answer = generate_answer(prompt)

    sources = [
        {
            "chunk_id": match.get("chunk_id"),
            "score": match.get("score"),
            "semantic_score": match.get("semantic_score"),
            "source": match.get("source")
            or match.get("metadata", {}).get("source")
            or match.get("metadata", {}).get("document_name"),
            "page": match.get("page") or match.get("metadata", {}).get("page"),
            "section": match.get("section") or match.get("metadata", {}).get("section"),
            "benefit_title": match.get("benefit_title")
            or match.get("metadata", {}).get("benefit_title"),
        }
        
        for match in matches
    ]

    return {
        "query": query,
        "answer": answer,
        "matches_count": len(matches),
        "sources": sources,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Genera respuesta RAG usando contexto recuperado."
    )

    parser.add_argument(
        "query",
        type=str,
        help="Pregunta del usuario.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime salida completa en JSON.",
    )

    args = parser.parse_args()

    result = answer_with_context(args.query)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n==============================")
        print("Pregunta")
        print("==============================")
        print(result["query"])

        print("\n==============================")
        print("Respuesta")
        print("==============================")
        print(result["answer"])

        print("\n==============================")
        print("Fuentes")
        print("==============================")
        for source in result["sources"]:
            print(
                f"- {source['source']} | Página {source['page']} | "
                f"{source.get('section')} | {source.get('benefit_title')} | "
                f"{source['chunk_id']} | score {source['score']}"
            )

if __name__ == "__main__":
    main()