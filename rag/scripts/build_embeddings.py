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

    return data["embedding"]


def build_embeddings(chunks: list[dict]) -> list[dict]:
    """
    Genera embeddings para todos los chunks.
    """
    embedded_chunks = []

    total = len(chunks)

    for index, chunk in enumerate(chunks, start=1):

        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        
        if not text or not text.strip():
            print(f"Chunk vacío omitido: {chunk_id}")
            continue

        print(f"[{index}/{total}] Generando embedding: {chunk_id}")

        embedding = generate_embedding(text)

        embedded_chunk = {
            "chunk_id": chunk_id,
            "embedding": embedding,
            "text": text,
            "benefit_title": chunk.get("benefit_title"),
            "metadata": {
                **chunk.get("metadata", {}),
                "source": chunk.get("source"),
                "page": chunk.get("page"),
                "section": chunk.get("section"),
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

    print("Guardando embeddings...")
    save_embeddings(embedded_chunks)

    print("Embeddings generados correctamente")
    print(f"Archivo salida: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()