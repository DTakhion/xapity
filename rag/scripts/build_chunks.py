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

EXCLUDED_PAGES = {
    1,   # Portada
    3,   # Índice
    16,  # Control documental y aprobaciones
}

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

def extract_page_text(page: fitz.Page) -> str:
    """
    Extrae los bloques de texto de una página y los ordena
    según su posición vertical y horizontal.
    """
    blocks = page.get_text("blocks")

    ordered_blocks = sorted(
        blocks,
        key=lambda block: (
            round(block[1], 1),  # coordenada superior Y
            round(block[0], 1),  # coordenada izquierda X
        ),
    )

    block_texts = []

    for block in ordered_blocks:
        text = block[4].strip()

        if text:
            block_texts.append(text)

    return "\n".join(block_texts)

def clean_text(text: str) -> str:
    """
    Limpia el texto extraído conservando estructura básica.

    - Normaliza saltos de línea.
    - Une palabras cortadas por guion entre líneas.
    - Normaliza espacios.
    - Evita múltiples líneas vacías consecutivas.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Une palabras cortadas por salto de línea:
    # "escola-\nridad" -> "escolaridad"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    cleaned_lines = []
    previous_empty = False

    for raw_line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        is_empty = not line

        if is_empty and previous_empty:
            continue

        cleaned_lines.append(line)
        previous_empty = is_empty

    return "\n".join(cleaned_lines).strip()


def normalize_title(text: str) -> str:
    """
    Normaliza variantes, errores tipográficos y espacios del título.
    """
    replacements = {
        "Indeminización": "Indemnización",
        "colaboradres": "colaboradores",
        "Antiguedad": "Antigüedad",
    }

    text = re.sub(r"\s+", " ", text).strip()

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

def canonicalize_benefit_title(text: str) -> str:
    """
    Retorna la versión canónica del título definida en BENEFIT_TITLES.
    """
    normalized_text = normalize_title(text).casefold()

    canonical_titles = {}

    for title in BENEFIT_TITLES:
        normalized_title = normalize_title(title)

        canonical_titles.setdefault(
            normalized_title.casefold(),
            normalized_title,
        )

    return canonical_titles.get(
        normalized_text,
        normalize_title(text),
    )


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

    sorted_titles = sorted(
        BENEFIT_TITLES,
        key=len,
        reverse=True,
    )
    
    title_pattern = "|".join(
        re.escape(title)
        for title in sorted_titles
    )
    
    matches = list(
        re.finditer(
            rf"(?<!\w)(?:{title_pattern})(?!\w)",
            text,
            flags=re.IGNORECASE,
        )
    )

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

        benefit_title = canonicalize_benefit_title(
            match.group(0)
        )
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

        next_start = max(0, end - overlap)
        
        if next_start > 0:
            boundary_positions = [
                position
                for position in (
                    text.find(" ", next_start),
                    text.find("\n", next_start),
                )
                if position != -1
            ]
            
            if boundary_positions:
                next_start = min(boundary_positions) + 1
                
        start = next_start
    
    return chunks


def is_page_relevant(page_number: int, text: str) -> bool:
    """
    Filtra páginas sin contenido útil o que no deben indexarse.
    """
    if page_number in EXCLUDED_PAGES:
        return False

    if not text:
        return False

    if len(text.strip()) < MIN_TEXT_LENGTH:
        return False

    return True


def extract_pdf_chunks() -> list[dict]:
    """
    Extrae texto del PDF y genera chunks semánticos por página/beneficio.
    """
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el PDF en: {PDF_PATH}"
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_chunks = []
    chunk_counter = 1

    with fitz.open(PDF_PATH) as doc:
        for page_index, page in enumerate(doc, start=1):
            raw_text = extract_page_text(page)
            cleaned_text = clean_text(raw_text)

            if not is_page_relevant(page_index, cleaned_text):
                print(
                    f"[skip] Página {page_index}: "
                    "sin texto relevante"
                )
                continue

            section = get_section_for_page(page_index)

            semantic_blocks = split_by_benefit_titles(
                cleaned_text
            )

            for block in semantic_blocks:
                benefit_title = block["benefit_title"]
                block_text = block["text"]

                page_chunks = split_long_text(
                    block_text,
                    chunk_size=CHUNK_SIZE,
                    overlap=CHUNK_OVERLAP,
                )

                for local_index, chunk_text in enumerate(
                    page_chunks,
                    start=1,
                ):
                    final_chunk_text = chunk_text.strip()

                    if benefit_title:
                        normalized_chunk_start = normalize_title(
                            final_chunk_text[
                                : len(benefit_title) + 20
                            ]
                        ).casefold()

                        normalized_benefit_title = (
                            normalize_title(
                                benefit_title
                            ).casefold()
                        )

                        if not normalized_chunk_start.startswith(
                            normalized_benefit_title
                        ):
                            final_chunk_text = (
                                f"{benefit_title}\n"
                                f"{final_chunk_text}"
                            )

                    embedding_text_parts = [
                        (
                            "Documento: "
                            f"{DOCUMENT_METADATA['manual_name']}"
                        ),
                        f"Sección: {section}",
                    ]

                    if benefit_title:
                        embedding_text_parts.append(
                            f"Beneficio: {benefit_title}"
                        )

                    embedding_text_parts.append(
                        final_chunk_text
                    )

                    embedding_text = "\n".join(
                        embedding_text_parts
                    )

                    chunk = {
                        "chunk_id": (
                            f"maf_{chunk_counter:04d}"
                        ),
                        "source": PDF_PATH.name,
                        "page": page_index,
                        "section": section,
                        "benefit_title": benefit_title,
                        "text": final_chunk_text,
                        "embedding_text": embedding_text,
                        "metadata": {
                            **DOCUMENT_METADATA,
                            "document_name": PDF_PATH.name,
                            "page": page_index,
                            "section": section,
                            "benefit_title": benefit_title,
                            "chunk_size": CHUNK_SIZE,
                            "chunk_overlap": CHUNK_OVERLAP,
                            "local_chunk_index": (
                                local_index
                            ),
                        },
                    }

                    all_chunks.append(chunk)
                    chunk_counter += 1

    return all_chunks

def print_diagnostics(chunks: list[dict]) -> None:
    """
    Imprime controles básicos de calidad sobre los chunks generados.
    """
    titled_chunks = [
        chunk
        for chunk in chunks
        if chunk.get("benefit_title")
    ]

    untitled_chunks = [
        chunk
        for chunk in chunks
        if not chunk.get("benefit_title")
    ]

    detected_titles = sorted(
        {
            chunk["benefit_title"]
            for chunk in titled_chunks
        }
    )

    escolaridad_chunks = [
        chunk
        for chunk in chunks
        if (
            "escolaridad"
            in chunk.get("text", "").casefold()
            or "escolaridad"
            in (chunk.get("benefit_title") or "").casefold()
        )
    ]

    print("\n=== DIAGNÓSTICO DE CHUNKS ===")
    print(f"Total chunks: {len(chunks)}")
    print(f"Chunks con beneficio: {len(titled_chunks)}")
    print(f"Chunks sin beneficio: {len(untitled_chunks)}")
    print(f"Títulos únicos detectados: {len(detected_titles)}")
    print(
        "Chunks relacionados con escolaridad: "
        f"{len(escolaridad_chunks)}"
    )

    print("\n=== TÍTULOS DETECTADOS ===")

    for title in detected_titles:
        print(f"[title] {title}")

    print("\n=== CHUNKS DE ESCOLARIDAD ===")

    for chunk in escolaridad_chunks:
        print("-" * 80)
        print(f"chunk_id: {chunk['chunk_id']}")
        print(f"page: {chunk['page']}")
        print(f"section: {chunk['section']}")
        print(f"benefit_title: {chunk['benefit_title']}")
        print(f"text:\n{chunk['text']}")

def save_chunks(chunks: list[dict]) -> None:
    """
    Guarda los chunks en JSON.
    """
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def main():
    chunks = extract_pdf_chunks()

    if not chunks:
        raise RuntimeError(
            "No se generaron chunks desde el documento."
        )

    save_chunks(chunks)
    print_diagnostics(chunks)

    print("\nChunks generados correctamente")
    print(f"PDF origen: {PDF_PATH}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Archivo salida: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()