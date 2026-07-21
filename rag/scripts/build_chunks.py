# # rag/scripts/build_chunks.py
# from pathlib import Path
# import json
# import re
# import fitz  # PyMuPDF


# # =========================
# # Configuración
# # =========================

# BASE_DIR = Path(__file__).resolve().parents[1]

# PDF_PATH = BASE_DIR / "raw" / "manual_beneficios_2025_2027.pdf"
# OUTPUT_PATH = BASE_DIR / "chunks" / "manual_beneficios_2025_2027_chunks.json"

# CHUNK_SIZE = 900
# CHUNK_OVERLAP = 150


# # =========================
# # Utilidades
# # =========================

# def clean_text(text: str) -> str:
#     """
#     Limpia texto extraído desde PDF.
#     """
#     text = text.replace("\n", " ")
#     text = re.sub(r"\s+", " ", text)
#     return text.strip()


# def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
#     """
#     Divide texto en chunks con solapamiento.
#     """
#     chunks = []

#     if not text:
#         return chunks

#     start = 0
#     text_length = len(text)

#     while start < text_length:
#         end = start + chunk_size
#         chunk = text[start:end].strip()

#         if chunk:
#             chunks.append(chunk)

#         start = end - overlap

#         if start < 0:
#             start = 0

#         if start >= text_length:
#             break

#     return chunks


# def extract_pdf_chunks() -> list[dict]:
#     """
#     Extrae texto del PDF y genera chunks por página.
#     """
#     if not PDF_PATH.exists():
#         raise FileNotFoundError(f"No se encontró el PDF en: {PDF_PATH}")

#     OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

#     doc = fitz.open(PDF_PATH)
#     all_chunks = []

#     chunk_counter = 1

#     for page_index, page in enumerate(doc, start=1):
#         raw_text = page.get_text("text")
#         cleaned_text = clean_text(raw_text)

#         page_chunks = split_text(
#             cleaned_text,
#             chunk_size=CHUNK_SIZE,
#             overlap=CHUNK_OVERLAP,
#         )

#         for chunk_text in page_chunks:
#             chunk = {
#                 "chunk_id": f"maf_{chunk_counter:04d}",
#                 "source": PDF_PATH.name,
#                 "page": page_index,
#                 "section": "General",
#                 "text": chunk_text,
#                 "metadata": {
#                     "source_type": "pdf",
#                     "document_name": PDF_PATH.name,
#                     "page": page_index,
#                     "chunk_size": CHUNK_SIZE,
#                     "chunk_overlap": CHUNK_OVERLAP,
#                 },
#             }

#             all_chunks.append(chunk)
#             chunk_counter += 1

#     doc.close()
#     return all_chunks


# def save_chunks(chunks: list[dict]) -> None:
#     """
#     Guarda los chunks en JSON.
#     """
#     with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
#         json.dump(chunks, f, ensure_ascii=False, indent=2)


# def main():
#     chunks = extract_pdf_chunks()
#     save_chunks(chunks)

#     print("Chunks generados correctamente")
#     print(f"PDF origen: {PDF_PATH}")
#     print(f"Total chunks: {len(chunks)}")
#     print(f"Archivo salida: {OUTPUT_PATH}")


# if __name__ == "__main__":
#     main()

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
CHUNK_OVERLAP = 120
MIN_TEXT_LENGTH = 80

DOCUMENT_METADATA = {
    "manual_name": "Manual de Beneficios Colaboradores de MAF Chile",
    "document_version": "1.3",
    "document_date": "2025-03-24",
    "valid_from": "2025-04-01",
    "valid_to": "2027-03-31",
    "organization": "MAF Chile",
    "source_type": "pdf",
}


SECTION_BY_PAGE = {
    1: "Portada",
    2: "Presentación y alcance",
    3: "Índice de beneficios",
    4: "Beneficios de Familia y Asignaciones",
    5: "Beneficios de Familia y Asignaciones",
    6: "Beneficios de Familia y Asignaciones",
    7: "Beneficios de Familia y Asignaciones",
    8: "Beneficios de Familia y Asignaciones",
    9: "Beneficios Bienestar y Calidad de Vida",
    10: "Beneficios Bienestar y Calidad de Vida",
    11: "Beneficios de Salud",
    12: "Beneficios de Salud",
    13: "Bonos y Asignaciones Laborales",
    14: "Bonos y Asignaciones Laborales",
    15: "Bonos y Asignaciones Laborales",
    16: "Control documental y aprobaciones",
}


BENEFIT_TITLES = [
    "Permiso Legal por Matrimonio",
    "Bono Natalidad",
    "Permiso legal por Nacimiento",
    "Permiso Padres Nacimiento Hijos",
    "Retorno Postnatal Paulatino",
    "Obligación legal de otorgamiento Sala Cuna",
    "Asignación Compensatoria Sala Cuna",
    "Asignación por Fallecimiento",
    "Indeminización por Fallecimiento o Invalidez total del colaborador",
    "Indemnización por Fallecimiento o Invalidez total del colaborador",
    "Permiso por Fallecimiento",
    "Bono Navidad hijo del colaborador",
    "Bono de Escolaridad",
    "Permiso Administrativo",
    "Día libre por cumpleaños de colaboradres",
    "Día libre por cumpleaños de colaboradores",
    "Medio día libre por cumpleaños de hijos",
    "Permiso sin goce de sueldo",
    "Asignación de Licencias médicas no superior a 10 días",
    "Asignación por Licencias Médicas",
    "Seguro Complementario de Salud",
    "Chequeo Médico",
    "Beneficio de Gimnasio",
    "Reajuste de Remuneraciones",
    "Aguinaldo de Fiestas Patrias",
    "Aguinaldo de Navidad",
    "Bono de Vacaciones",
    "Bono de Antiguedad",
    "Bono de Antigüedad",
]


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


def normalize_title(text: str) -> str:
    """
    Normaliza pequeñas variantes/typos del manual.
    """
    replacements = {
        "Indeminización": "Indemnización",
        "colaboradres": "colaboradores",
        "Antiguedad": "Antigüedad",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def get_section_for_page(page_number: int) -> str:
    """
    Retorna la sección documental según la página.
    """
    return SECTION_BY_PAGE.get(page_number, "General")


def split_by_benefit_titles(text: str) -> list[dict]:
    """
    Divide una página en bloques semánticos por beneficio cuando detecta títulos.
    """
    if not text:
        return []

    title_pattern = "|".join(re.escape(title) for title in BENEFIT_TITLES)

    matches = list(re.finditer(title_pattern, text, flags=re.IGNORECASE))

    if not matches:
        return [
            {
                "benefit_title": None,
                "text": text,
            }
        ]

    blocks = []

    first_match_start = matches[0].start()
    if first_match_start > 0:
        intro = text[:first_match_start].strip()
        if len(intro) >= MIN_TEXT_LENGTH:
            blocks.append(
                {
                    "benefit_title": None,
                    "text": intro,
                }
            )

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)

        benefit_title = normalize_title(match.group(0)).strip()
        block_text = text[start:end].strip()

        if len(block_text) >= MIN_TEXT_LENGTH:
            blocks.append(
                {
                    "benefit_title": benefit_title,
                    "text": block_text,
                }
            )

    return blocks


def split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Divide sólo si el bloque es demasiado largo.
    Intenta cortar en puntos, no en mitad de una frase.
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text.strip()]

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        hard_end = min(start + chunk_size, text_length)
        candidate = text[start:hard_end]

        if hard_end < text_length:
            sentence_end = max(
                candidate.rfind(". "),
                candidate.rfind("; "),
                candidate.rfind(": "),
            )

            if sentence_end > int(chunk_size * 0.55):
                end = start + sentence_end + 1
            else:
                end = hard_end
        else:
            end = hard_end

        chunk = text[start:end].strip()

        if len(chunk) >= MIN_TEXT_LENGTH:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = max(0, end - overlap)

    return chunks


def is_page_relevant(page_number: int, text: str) -> bool:
    """
    Filtra páginas vacías o casi sin contenido útil.
    Mantiene portada, índice y control documental si tienen texto suficiente.
    """
    if not text:
        return False

    if len(text) < MIN_TEXT_LENGTH:
        return False

    return True


def extract_pdf_chunks() -> list[dict]:
    """
    Extrae texto del PDF y genera chunks semánticos por página/beneficio.
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

        if not is_page_relevant(page_index, cleaned_text):
            print(f"[skip] Página {page_index}: sin texto relevante")
            continue

        section = get_section_for_page(page_index)

        semantic_blocks = split_by_benefit_titles(cleaned_text)

        for block in semantic_blocks:
            benefit_title = block["benefit_title"]
            block_text = block["text"]

            page_chunks = split_long_text(
                block_text,
                chunk_size=CHUNK_SIZE,
                overlap=CHUNK_OVERLAP,
            )

            for local_index, chunk_text in enumerate(page_chunks, start=1):
                chunk = {
                    "chunk_id": f"maf_{chunk_counter:04d}",
                    "source": PDF_PATH.name,
                    "page": page_index,
                    "section": section,
                    "benefit_title": benefit_title,
                    "text": chunk_text,
                    "metadata": {
                        **DOCUMENT_METADATA,
                        "document_name": PDF_PATH.name,
                        "page": page_index,
                        "section": section,
                        "benefit_title": benefit_title,
                        "chunk_size": CHUNK_SIZE,
                        "chunk_overlap": CHUNK_OVERLAP,
                        "local_chunk_index": local_index,
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