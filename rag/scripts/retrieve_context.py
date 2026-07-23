# rag/scripts/retrieve_context.py
from pathlib import Path
import json
import requests
import numpy as np
import re
import unicodedata

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

TOP_K = 2 # podria necesitar 3
MIN_SCORE = 0.65
MAX_SCORE_GAP = 0.07

# =========================
# Utilidades
# =========================

def normalize_search_text(text: str) -> str:
    """
    Normaliza texto para comparaciones léxicas.

    - Convierte a minúsculas.
    - Elimina tildes y diacríticos.
    - Normaliza espacios.
    """
    if not text:
        return ""

    text = text.casefold()

    text = unicodedata.normalize(
        "NFKD",
        text,
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()

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
    query = query.strip()

    if not query:
        raise ValueError("La consulta no puede estar vacía.")

    query_embedding_text = (
        f"search_query: {query}"
    )
    
    payload = {
        "model": MODEL_NAME,
        "prompt": query_embedding_text,
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            "No fue posible generar el embedding de la consulta. "
            "Verifica que Ollama esté activo en http://localhost:11434 "
            f"y que el modelo {MODEL_NAME} esté disponible."
        ) from exc

    data = response.json()
    
    embedding = data.get("embedding")
    
    if not embedding:
        raise RuntimeError(
            "Ollama no retornó un embedding válido "
            f"para la consulta. Respuesta: {data}"
        )
    
    if not isinstance(embedding, list):
        raise TypeError(
            "El embedding de la consulta "
            "no es una lista."
        )
        
    if not all(
        isinstance(value, (int, float))
        for value in embedding
    ):
        raise TypeError(
            "El embedding de la consulta contiene "
            "valores no numéricos."
        )
    
    return embedding


def cosine_similarity(
    vec_a: list[float],
    vec_b: list[float],
) -> float:
    """
    Calcula similitud coseno entre dos vectores.
    """
    a = np.asarray(
        vec_a,
        dtype=np.float32,
    )

    b = np.asarray(
        vec_b,
        dtype=np.float32,
    )

    if a.ndim != 1 or b.ndim != 1:
        raise ValueError(
            "Los embeddings deben ser vectores "
            "unidimensionales."
        )

    if a.shape != b.shape:
        raise ValueError(
            "Dimensiones incompatibles: "
            f"consulta={a.shape}, "
            f"documento={b.shape}"
        )

    denominator = (
        np.linalg.norm(a)
        * np.linalg.norm(b)
    )

    if denominator == 0:
        return 0.0

    return float(
        np.dot(a, b) / denominator
    )


def retrieve_context(
    query: str,
    top_k: int = TOP_K,
    min_score: float = MIN_SCORE,
) -> dict:
    """
    Recupera los chunks más relevantes para una pregunta.
    """
    if top_k <= 0:
        raise ValueError("top_k debe ser mayor que 0.")

    if min_score < -1 or min_score > 1:
        raise ValueError("min_score debe estar entre -1 y 1.")

    embedded_chunks = load_embeddings()
    query_embedding = generate_query_embedding(query)

    scored_chunks = []

    for item in embedded_chunks:
        embedding = item.get("embedding")

        if not embedding:
            continue
        
        metadata = item.get("metadata", {})

        score = cosine_similarity(
            query_embedding,
            embedding,
        )
        
        adjusted_score = score
        
        benefit_title = item.get("benefit_title") or metadata.get("benefit_title") or ""
        query_norm = normalize_search_text(query)
        title_norm = normalize_search_text(
            benefit_title
        )
        
        if benefit_title and title_norm in query_norm:
            adjusted_score += 0.08
            
        title_words = [
            word
            for word in re.findall(r"\w+", title_norm)
            if (
                len(word) >= 4
                and word
                not in {
                    "bono",
                    "beneficio",
                    "asignacion",
                    "permiso",
                }
            )
        ]
        
        query_words = set(re.findall(r"\w+", query_norm))
        
        matches_title_words = sum(1 for word in title_words if word in query_words)
        
        if matches_title_words > 0:
            adjusted_score += min(0.10, matches_title_words * 0.04)
            
        adjusted_score = round(
            adjusted_score,
            6,
        )

        if adjusted_score >= min_score:
            scored_chunks.append(
                {
                    "chunk_id": item.get("chunk_id"),
                    "score": round(adjusted_score, 4),
                    "semantic_score": round(score, 4),
                    "text": item.get("text", ""),
                    "benefit_title": item.get("benefit_title"),
                    "section": metadata.get("section"),
                    "page": metadata.get("page"),
                    "source": metadata.get("source")
                    or metadata.get("document_name"),
                    "metadata": metadata,
                }
            )

    def ranking_key(match: dict) -> tuple:
        text = match.get("text", "")
        benefit_title = match.get("benefit_title") or ""
        
        starts_with_title = (
            1 if benefit_title and text.lower().startswith(benefit_title.lower()) else 0
        )
        
        text_length_bonus = min(len(text) / 1200, 1)
        
        return (
            match["score"],
            starts_with_title,
            text_length_bonus,
        )
        
    scored_chunks.sort(
        key=ranking_key,
        reverse=True,
    )

    if not scored_chunks:
        matches = []
    else:
        best_score = scored_chunks[0]["score"]
        relative_threshold = best_score - MAX_SCORE_GAP
        
        matches = [
            match
            for match in scored_chunks
            if match["score"] >= relative_threshold
        ][:top_k]

    return {
        "query": query,
        "top_k": top_k,
        "min_score": min_score,
        "matches_count": len(matches),
        "matches": matches,
    }


def build_context_text(results: dict) -> str:
    """
    Construye un texto de contexto compacto para enviar al modelo generativo.
    """
    matches = results.get("matches", [])

    if not matches:
        return ""

    context_blocks = []

    for index, match in enumerate(matches, start=1):
        benefit_title = match.get("benefit_title") or "Sin título específico"
        section = match.get("section") or "Sin sección"
        page = match.get("page") or "Sin página"
        text = match.get("text", "")

        block = (
            f"[Contexto {index}]\n"
            f"Sección: {section}\n"
            f"Beneficio: {benefit_title}\n"
            f"Página: {page}\n"
            f"Texto: {text}"
        )

        context_blocks.append(block)

    return "\n\n".join(context_blocks)


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
        print("\n------------------------------")
        print(f"Resultado #{index}")
        print(f"Chunk ID: {match.get('chunk_id')}")
        print(f"Score: {match.get('score')}")
        print(f"Fuente: {match.get('source')}")
        print(f"Página: {match.get('page')}")
        print(f"Sección: {match.get('section')}")
        print(f"Beneficio: {match.get('benefit_title')}")
        print("------------------------------")
        print(match.get("text", "")[:1200])


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

    parser.add_argument(
        "--context",
        action="store_true",
        help="Imprime sólo el contexto armado para el modelo generativo.",
    )

    args = parser.parse_args()

    results = retrieve_context(
        query=args.query,
        top_k=args.top_k,
        min_score=args.min_score,
    )

    if args.context:
        print(build_context_text(results))
    elif args.json:
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