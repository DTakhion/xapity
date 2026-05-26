# rag/service.py
from pathlib import Path
import json
import requests
import numpy as np
import os
from dotenv import load_dotenv


# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parent

EMBEDDINGS_PATH = (
    BASE_DIR
    / "embeddings"
    / "manual_beneficios_2025_2027_embeddings.json"
)

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434"
)

OLLAMA_EMBEDDINGS_URL = (
    f"{OLLAMA_BASE_URL}/api/embeddings"
)

OLLAMA_GENERATE_URL = (
    f"{OLLAMA_BASE_URL}/api/generate"
)

EMBEDDING_MODEL_NAME = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "nomic-embed-text"
)

LLM_MODEL_NAME = os.getenv(
    "OLLAMA_LLM_MODEL",
    "llama3.2:3b"
)

DEFAULT_TOP_K = 2
DEFAULT_MIN_SCORE = 0.68


# =========================
# Utilidades internas
# =========================

def load_embeddings() -> list[dict]:
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró archivo de embeddings: {EMBEDDINGS_PATH}"
        )

    with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_embedding(text: str) -> list[float]:
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": text,
    }

    response = requests.post(
        OLLAMA_EMBEDDINGS_URL,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()
    data = response.json()

    return data["embedding"]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


def retrieve_context(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict:
    embedded_chunks = load_embeddings()
    query_embedding = generate_embedding(query)

    scored_chunks = []

    for item in embedded_chunks:
        score = cosine_similarity(
            query_embedding,
            item["embedding"],
        )

        if score >= min_score:
            scored_chunks.append(
                {
                    "chunk_id": item["chunk_id"],
                    "score": round(score, 4),
                    "text": item["text"],
                    "metadata": item.get("metadata", {}),
                }
            )

    scored_chunks.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    matches = scored_chunks[:top_k]

    return {
        "query": query,
        "top_k": top_k,
        "min_score": min_score,
        "matches_count": len(matches),
        "matches": matches,
    }


def build_context(matches: list[dict]) -> str:
    context_blocks = []

    for index, match in enumerate(matches, start=1):
        metadata = match.get("metadata", {})

        block = f"""
[Contexto {index}]
Fuente: {metadata.get("source")}
Página: {metadata.get("page")}

Texto:
{match.get("text")}
"""
        context_blocks.append(block.strip())

    return "\n\n".join(context_blocks)


def build_prompt(query: str, context: str) -> str:
    return f"""
Eres Xapity, un asistente corporativo especializado en responder preguntas sobre beneficios internos de la empresa.

INSTRUCCIONES:
- Responde únicamente usando la información entregada en el CONTEXTO.
- No inventes información ni agregues supuestos.
- Si el contexto no contiene información suficiente para responder con certeza, indica exactamente:
  "No encontré información suficiente en el manual disponible para responder con certeza."

- Antes de responder, revisa TODOS los bloques de contexto recuperados.
- Si varios bloques contienen información complementaria sobre el mismo beneficio, intégralos en una sola respuesta.
- Si existe un permiso legal y además un permiso adicional entregado por la empresa, menciona ambos explícitamente.
- Distingue claramente entre beneficios legales y beneficios adicionales otorgados por la empresa.
- No confundas beneficios legales con beneficios corporativos adicionales.

- No generes listas de requisitos, límites, restricciones o excepciones si el contexto no las menciona explícitamente.
- No digas "no hay requisitos" o "no hay restricciones" a menos que el contexto lo indique expresamente.
- Responde de forma breve, natural y útil para un colaborador.
- No menciones scores internos, chunks, embeddings ni detalles técnicos.
- Puedes mencionar la página del manual si ayuda.

CONTEXTO:
{context}

PREGUNTA DEL USUARIO:
{query}

RESPUESTA:
""".strip()


def generate_answer(prompt: str) -> str:
    payload = {
        "model": LLM_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
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


def infer_confidence(matches: list[dict]) -> str:
    if not matches:
        return "none"

    best_score = matches[0].get("score", 0)

    if best_score >= 0.75:
        return "high"

    if best_score >= 0.68:
        return "medium"

    return "low"


def build_sources(matches: list[dict]) -> list[dict]:
    return [
        {
            "chunk_id": match.get("chunk_id"),
            "score": match.get("score"),
            "source": match.get("metadata", {}).get("source"),
            "page": match.get("metadata", {}).get("page"),
        }
        for match in matches
    ]


# =========================
# Función pública principal
# =========================

def answer_user_question(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> dict:
    """
    Función principal para ser utilizada por FastAPI.

    Recibe una pregunta del usuario, recupera contexto relevante
    y genera una respuesta final usando RAG local con Ollama.
    """

    query = query.strip()

    if not query:
        return {
            "status": "error",
            "answer": "La pregunta no puede estar vacía.",
            "query": query,
            "matches_count": 0,
            "confidence": "none",
            "sources": [],
        }

    try:
        retrieval = retrieve_context(
            query=query,
            top_k=top_k,
            min_score=min_score,
        )

        matches = retrieval.get("matches", [])

        if not matches:
            return {
                "status": "no_context",
                "answer": "No encontré información suficiente en el manual disponible para responder con certeza.",
                "query": query,
                "matches_count": 0,
                "confidence": "none",
                "sources": [],
            }

        context = build_context(matches)
        prompt = build_prompt(query, context)
        answer = generate_answer(prompt)

        return {
            "status": "answered",
            "answer": answer,
            "query": query,
            "matches_count": len(matches),
            "confidence": infer_confidence(matches),
            "sources": build_sources(matches),
        }

    except FileNotFoundError as error:
        return {
            "status": "error",
            "answer": "No se encontró la base de conocimiento necesaria para responder.",
            "query": query,
            "matches_count": 0,
            "confidence": "none",
            "sources": [],
            "error_detail": str(error),
        }

    except requests.exceptions.ConnectionError:
        return {
            "status": "error",
            "answer": "No fue posible conectar con Ollama. Verifica que el servicio esté activo.",
            "query": query,
            "matches_count": 0,
            "confidence": "none",
            "sources": [],
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "answer": "La generación de respuesta tardó demasiado. Intenta nuevamente.",
            "query": query,
            "matches_count": 0,
            "confidence": "none",
            "sources": [],
        }

    except Exception as error:
        return {
            "status": "error",
            "answer": "Ocurrió un error inesperado al generar la respuesta.",
            "query": query,
            "matches_count": 0,
            "confidence": "none",
            "sources": [],
            "error_detail": str(error),
        }