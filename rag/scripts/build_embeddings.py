# rag/scripts/build_embeddings.py
from pathlib import Path
import json
import requests
import time


# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

CHUNKS_PATH = (
    BASE_DIR
    / "chunks"
    / "manual_beneficios_2025_2027_chunks.json"
)

OUTPUT_PATH = (
    BASE_DIR
    / "embeddings"
    / "manual_beneficios_2025_2027_embeddings.json"
)

OLLAMA_URL = "http://localhost:11434/api/embeddings"
MODEL_NAME = "nomic-embed-text"


# =========================
# Utilidades
# =========================

def load_chunks() -> list[dict]:
    """
    Carga chunks desde JSON.
    """
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró archivo chunks: {CHUNKS_PATH}"
        )

    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_embedding(text: str) -> list[float]:
    """
    Genera embedding usando Ollama.
    """
    payload = {
        "model": MODEL_NAME,
        "prompt": text,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()
    
    embedding = data.get("embedding")
    
    if not embedding:
        raise RuntimeError(
            "Ollama no retornó un embedding válido. "
            f"Respuesta: {data}"
        )
    
    if not isinstance(embedding, list):
        raise TypeError(
            "El embedding retornado por Ollama no es una lista."
        )
    
    return embedding


def build_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Genera embeddings para todos los chunks.
    """
    embedded_chunks = []

    total = len(chunks)
    
    expected_embedding_dimension = None

    for index, chunk in enumerate(chunks, start=1):

        chunk_id = chunk["chunk_id"]
        
        text = chunk.get("text", "").strip()
        
        embedding_text = chunk.get(
            "embedding_text",
            text,
        ).strip()
        
        if not text:
            print(f"[skip] Chunk sin texto: {chunk_id}")
            continue
        
        if not embedding_text:
            print(f"[skip] Chunk sin texto para embedding: {chunk_id}")
            continue

        print(f"[{index}/{total}] Generando embedding: {chunk_id}")

        try:
            document_embedding_text = (
                f"search_document: {embedding_text}"
            )
            
            embedding = generate_embedding(
                document_embedding_text
            )
            
        except requests.RequestException as exc:
            raise RuntimeError(
                f"Error solicitando embedding para {chunk_id}"
            ) from exc
            
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            raise RuntimeError(
                f"Respuesta inválida al generar embedding para "
                f"{chunk_id}: {exc}"
            ) from exc
        
        embedding_dimension = len(embedding)
        
        if expected_embedding_dimension is None:
            expected_embedding_dimension = embedding_dimension
        
        elif embedding_dimension != expected_embedding_dimension:
            raise RuntimeError(
                "Dimensión de embedding inconsistente para "
                f"{chunk_id}: esperada "
                f"{expected_embedding_dimension}, recibida "
                f"{embedding_dimension}"
            )

        embedded_chunk = {
            "chunk_id": chunk_id,
            "embedding": embedding,
            "text": text,
            "embedding_text": embedding_text,
            "document_embedding_text": document_embedding_text,
            "benefit_title": chunk.get("benefit_title"),
            "metadata": {
                **chunk.get("metadata", {}),
                "source": chunk.get("source"),
                "page": chunk.get("page"),
                "section": chunk.get("section"),
                "embedding_model": MODEL_NAME,
                "embedding_dimension": embedding_dimension,
            },
        }

        embedded_chunks.append(embedded_chunk)

        time.sleep(0.05)

    return embedded_chunks


def save_embeddings(embedded_chunks: list[dict]) -> None:
    """
    Guarda embeddings en JSON.
    """
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            embedded_chunks,
            f,
            ensure_ascii=False,
            indent=2,
        )


def main():

    print("Cargando chunks...")
    chunks = load_chunks()

    print(f"Total chunks encontrados: {len(chunks)}")

    print("Generando embeddings...")
    embedded_chunks = build_embeddings(chunks)
    
    if not embedded_chunks:
        raise RuntimeError(
            "No se generó ningún embedding."
        )
    
    if len(embedded_chunks) != len(chunks):
        print(
            "[warning] La cantidad de embeddings no coincide "
            "con la cantidad de chunks."
        )

    print("Guardando embeddings...")
    save_embeddings(embedded_chunks)

    print("Embeddings generados correctamente")
    print(f"Archivo salida: {OUTPUT_PATH}")
    
    embedding_dimension = len(
        embedded_chunks[0]["embedding"]
    )
    
    print(f"Total embeddings: {len(embedded_chunks)}")
    print(f"Dimensión embeddings: {embedding_dimension}")
    print(f"Modelo embeddings: {MODEL_NAME}")

if __name__ == "__main__":
    main()