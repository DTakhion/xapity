# rag/scripts/build_chunks.py
from pathlib import Path
import json
import re
import fitz  # PyMuPDF


# =========================
# Configuración
# =========================

BASE_DIR = Path(__file__).resolve().parents[1]

PDF_PATH = BASE_DIR / "raw" / "manual_beneficios_2025_2027.pdf"
OUTPUT_PATH = BASE_DIR / "chunks" / "manual_beneficios_2025_2027_chunks.json"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


# =========================
# Utilidades
# =========================

def clean_text(text: str) -> str:
    """
    Limpia texto extraído desde PDF.
    """
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Divide texto en chunks con solapamiento.
    """
    chunks = []

    if not text:
        return chunks

    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

        if start < 0:
            start = 0

        if start >= text_length:
            break

    return chunks


def extract_pdf_chunks() -> list[dict]:
    """
    Extrae texto del PDF y genera chunks por página.
    """
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"No se encontró el PDF en: {PDF_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(PDF_PATH)
    all_chunks = []

    chunk_counter = 1

    for page_index, page in enumerate(doc, start=1):
        raw_text = page.get_text("text")
        cleaned_text = clean_text(raw_text)

        page_chunks = split_text(
            cleaned_text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )

        for chunk_text in page_chunks:
            chunk = {
                "chunk_id": f"maf_{chunk_counter:04d}",
                "source": PDF_PATH.name,
                "page": page_index,
                "section": "General",
                "text": chunk_text,
                "metadata": {
                    "source_type": "pdf",
                    "document_name": PDF_PATH.name,
                    "page": page_index,
                    "chunk_size": CHUNK_SIZE,
                    "chunk_overlap": CHUNK_OVERLAP,
                },
            }

            all_chunks.append(chunk)
            chunk_counter += 1

    doc.close()
    return all_chunks


def save_chunks(chunks: list[dict]) -> None:
    """
    Guarda los chunks en JSON.
    """
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def main():
    chunks = extract_pdf_chunks()
    save_chunks(chunks)

    print("Chunks generados correctamente")
    print(f"PDF origen: {PDF_PATH}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Archivo salida: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()