import re
import sys  # NUEVO: para poder probar desde terminal
import unicodedata


# STOPWORDS:
# Palabras que se consideran poco informativas para generar tags.
# La idea es dejar principalmente palabras clave del servicio.
# Se pueden seguir ajustando a medida que aparezcan nuevos casos reales.
STOPWORDS = {
    "de", "la", "el", "los", "las",
    "y", "o", "para", "con",
    "un", "una", "servicio", "basico"
}


def normalize_text(text: str) -> str:
    """
    Normaliza el texto eliminando acentos y convirtiéndolo
    a una representación ASCII simple.
    """

    # NUEVO: manejo defensivo por si llega None
    if text is None:
        return ""

    # NUEVO: asegurar compatibilidad si llega otro tipo
    text = str(text)

    # Lógica base (correcta de Felipe )
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")

    # La versión original ya retornaba lower()
    return text.lower()


def extract_words(text: str) -> list[str]:
    """
    Extrae palabras limpias desde un texto normalizado.
    """

    text = normalize_text(text)

    # Conservamos solo letras, números y espacios
    # Ajuste de comentario: aquí no se reemplaza por espacios,
    # se eliminan caracteres no permitidos
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # split() ya maneja espacios múltiples
    words = text.split()

    return words


def generate_tags(name: str, description: str = "") -> list[str]:
    """
    Genera tags relevantes a partir de:
    - name
    - description

    Ejemplo:
        name="Corte de cabello hombre"
        description="Servicio basico con tijera"

        -> ["corte", "cabello", "hombre", "tijera"]
    """

    # NUEVO: manejo defensivo por si name o description llegan como None
    if name is None:
        name = ""
    if description is None:
        description = ""

    # Lógica original: combinar palabras desde nombre + descripción
    words = extract_words(name) + extract_words(description)

    # Eliminar stopwords y palabras demasiado cortas
    filtered = [
        word for word in words
        if word not in STOPWORDS and len(word) > 2
    ]

    # Eliminar duplicados manteniendo orden (correcto en la versión original)
    seen = set()
    tags = []

    for word in filtered:
        if word not in seen:
            seen.add(word)
            tags.append(word)

    return tags


# =========================
# MAIN DE PRUEBA (NUEVO)
# =========================
def main() -> None:
    """
    Permite probar el generador de tags desde terminal.

    Uso:
        python3 -m utils.tags "Corte de cabello hombre" "Servicio basico con tijera"
    """

    if len(sys.argv) < 2:
        print('Uso: python -m utils.tags "Nombre del servicio" "Descripción opcional"')
        return

    name = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else ""

    tags = generate_tags(name, description)

    print("\n=== RESULTADO TAGS ===")
    print(f"Name:        {name}")
    print(f"Description: {description}")
    print(f"Tags:        {tags}")


# NUEVO: punto de entrada ejecutable
if __name__ == "__main__":
    main()