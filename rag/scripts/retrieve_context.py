# rag/scripts/retrieve_context.py
from pathlib import Path
import json
import requests
import numpy as np


# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

EMBEDDINGS_PATH = (
    BASE_DIR
    / "embeddings"
    / "manual_beneficios_2025_2027_embeddings.json"
)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "nomic-embed-text"

TOP_K = 3 # antes 5
MIN_SCORE = 0.65 # antes 0.45

# =========================
# Utilidades
# =========================

def load_embeddings() -> list[dict]:
    """
    Carga embeddings previamente generados.
    """
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró archivo de embeddings: {EMBEDDINGS_PATH}"
        )

    with open(EMBEDDINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_query_embedding(query: str) -> list[float]:
    """
    Genera embedding para la pregunta del usuario.
    """
    payload = {
        "model": MODEL_NAME,
        "prompt": query,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()
    data = response.json()

    return data["embedding"]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calcula similitud coseno entre dos vectores.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)

    denominator = np.linalg.norm(a) * np.linalg.norm(b)

    if denominator == 0:
        return 0.0

    return float(np.dot(a, b) / denominator)


def retrieve_context(
    query: str,
    top_k: int = TOP_K,
    min_score: float = MIN_SCORE,
) -> dict:
    """
    Recupera los chunks más relevantes para una pregunta.
    """
    embedded_chunks = load_embeddings()
    query_embedding = generate_query_embedding(query)

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


def print_results(results: dict) -> None:
    """
    Imprime resultados de manera legible en terminal.
    """
    print("\n==============================")
    print("Consulta")
    print("==============================")
    print(results["query"])

    print("\n==============================")
    print("Resultados encontrados")
    print("==============================")
    print(f"Total matches: {results['matches_count']}")

    for index, match in enumerate(results["matches"], start=1):
        metadata = match.get("metadata", {})

        print("\n------------------------------")
        print(f"Resultado #{index}")
        print(f"Chunk ID: {match['chunk_id']}")
        print(f"Score: {match['score']}")
        print(f"Fuente: {metadata.get('source')}")
        print(f"Página: {metadata.get('page')}")
        print("------------------------------")
        print(match["text"][:900])


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Recupera contexto relevante desde embeddings RAG."
    )

    parser.add_argument(
        "query",
        type=str,
        help="Pregunta o consulta del usuario.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help="Cantidad máxima de chunks a recuperar.",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=MIN_SCORE,
        help="Score mínimo de similitud coseno.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime salida en formato JSON.",
    )

    args = parser.parse_args()

    results = retrieve_context(
        query=args.query,
        top_k=args.top_k,
        min_score=args.min_score,
    )

    if args.json:
        print(
            json.dumps(
                results,
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_results(results)


if __name__ == "__main__":
    main()