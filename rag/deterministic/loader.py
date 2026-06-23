# rag/deterministic/loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STRUCTURED_DIR = Path(__file__).resolve().parents[1] / "structured"


def load_json_file(file_path: Path) -> dict[str, Any]:
    """
    Carga un archivo JSON estructurado de beneficio MAF.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_structured_benefits(
    structured_dir: Path | str = DEFAULT_STRUCTURED_DIR,
) -> list[dict[str, Any]]:
    """
    Carga todos los beneficios estructurados desde rag/structured/*.json.
    """
    structured_path = Path(structured_dir)

    if not structured_path.exists():
        raise FileNotFoundError(f"No existe el directorio structured: {structured_path}")

    benefits: list[dict[str, Any]] = []

    for file_path in sorted(structured_path.glob("*.json")):
        benefit = load_json_file(file_path)
        benefit["_sourceFile"] = file_path.name
        benefits.append(benefit)

    return benefits


def load_structured_benefits_by_id(
    structured_dir: Path | str = DEFAULT_STRUCTURED_DIR,
) -> dict[str, dict[str, Any]]:
    """
    Carga los beneficios estructurados y los indexa por benefitId.
    """
    benefits = load_structured_benefits(structured_dir)

    benefits_by_id: dict[str, dict[str, Any]] = {}

    for benefit in benefits:
        benefit_id = benefit.get("benefitId")

        if not benefit_id:
            continue

        benefits_by_id[benefit_id] = benefit

    return benefits_by_id


if __name__ == "__main__":
    benefits = load_structured_benefits()

    print(f"Beneficios cargados: {len(benefits)}")

    for benefit in benefits:
        print(
            f"- {benefit.get('benefitId')} | "
            f"{benefit.get('title')} | "
            f"{benefit.get('_sourceFile')}"
        )