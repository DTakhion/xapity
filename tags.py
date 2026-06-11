import re
import unicodedata

#STOPWORD, son palabras que estan designadas para ser eliminadas, dejando
#unicamente las palabras clave de cada frase, estas se iran designando a medida
#que aparezcan otras palabras.

    
STOPWORDS = {
    "de", "la", "el", "los", "las",
    "y", "o", "para", "con",
    "un", "una", "servicio", "basico"
}


def normalize_text(text: str) -> str:
    """
    Normaliza el texto, eliminando los acentos y caracteres especiales.
    """
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    return text.lower()


def extract_words(text: str) -> list:
    """
    Extrae las palabras limpias desde un texto.
    """
    text = normalize_text(text)
    text = re.sub(r"[^a-z0-9\s]", "", text)

    words = text.split()
    return words


def generate_tags(name: str, description: str = "") -> list:
    """
    Genera tags relevantes desde name + description.
    """

    words = extract_words(name) + extract_words(description)

    # eliminar stopwords
    filtered = [
        word for word in words
        if word not in STOPWORDS and len(word) > 2
    ]

    # eliminar duplicados manteniendo orden
    seen = set()
    tags = []

    for word in filtered:
        if word not in seen:
            seen.add(word)
            tags.append(word)

    return tags