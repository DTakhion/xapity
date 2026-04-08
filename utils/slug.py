import re
import sys  # NUEVO: para poder ejecutar desde terminal (main)
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normaliza el texto eliminando acentos y convirtiéndolo
    a una representación ASCII simple.
    """

    # NUEVO: manejo defensivo por si llega None
    if text is None:
        return ""

    # NUEVO: asegurar que siempre sea string
    text = str(text)

    # Lógica original (correcta de Felipe)
    text = unicodedata.normalize("NFD", text)
    text = text.encode("ascii", "ignore").decode("utf-8")
    return text


def generate_slug(name: str) -> str:
    """
    Genera un slug a partir del nombre de un servicio.

    Ejemplo:
        "Corte de cabello hombre" -> "corte-de-cabello-hombre"
    """

    # NUEVO: manejo defensivo
    if name is None:
        return ""

    # 1. Normalizar (quitar acentos)
    text = normalize_text(name)

    # 2. Pasar a minúsculas
    text = text.lower()

    # 3. Eliminar caracteres no permitidos
    # OBS: el comentario original decía "reemplazar por espacios",
    # pero en realidad se deben eliminar
    text = re.sub(r"[^a-z0-9\s-]", "", text)

    # 4. Normalizar espacios múltiples
    text = re.sub(r"\s+", " ", text).strip()

    # 5. Reemplazar espacios por guiones
    slug = text.replace(" ", "-")

    # NUEVO: evitar múltiples guiones consecutivos (edge case)
    # Ej: "corte---hombre" -> "corte-hombre"
    slug = re.sub(r"-+", "-", slug)

    # NUEVO: eliminar guiones al inicio o final
    slug = slug.strip("-")

    return slug


# =========================
# MAIN DE PRUEBA (NUEVO)
# =========================
def main() -> None:
    """
    Permite probar el generador de slug desde terminal.

    Uso:
        python -m utils.slug "Corte de cabello hombre"
    """

    # NUEVO: validación básica de input
    if len(sys.argv) < 2:
        print('Uso: python3 -m utils.slug "Nombre del servicio"')
        return

    # Permite strings con espacios sin necesidad de comillas estrictas
    name = " ".join(sys.argv[1:])
    slug = generate_slug(name)

    print("\n=== RESULTADO SLUG ===")
    print(f"Input: {name}")
    print(f"Slug:  {slug}")


# NUEVO: punto de entrada ejecutable
if __name__ == "__main__":
    main()