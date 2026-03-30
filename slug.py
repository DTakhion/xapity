import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normaliza el texto, eliminando los acentos y caracteres especiales.
    """
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    return text


def generate_slug(name: str) -> str:
    """
    Genera un slug a partir del nombre del servicio, reemplazando los espacios por guiones (-).
    Ejemplo:
    'Corte de cabello hombre' → 'corte-de-cabello-hombre'
    """

    # 1. Normalizar (quitar acentos)
    text = normalize_text(name)

    # 2. Pasar a minúsculas
    text = text.lower()

    # 3. Reemplazar todo lo que no sea letra o número por espacios
    text = re.sub(r"[^a-z0-9\s-]", "", text)

    # 4. Reemplazar espacios múltiples por uno solo
    text = re.sub(r"\s+", " ", text).strip()

    # 5. Reemplazar espacios por guiones
    slug = text.replace(" ", "-")

    return slug