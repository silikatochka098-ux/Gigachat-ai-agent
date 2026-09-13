"""
file_reader.py

Единая точка входа для чтения файлов чертежей.

Поддерживаем:
    PDF
    PNG / JPG / JPEG
    DXF
    CDW
    M3D

Модуль НЕ меняет существующий drawing_analyzer.py.
Он приводит разные источники к единому словарю, после чего analyzer может
использовать соответствующее поле:
- text
- image_path / image_bytes
- dxf
- kompas
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".dxf",
    ".cdw",
    ".m3d",
}


class FileReaderError(Exception):
    """Общая ошибка чтения файла."""


def read_drawing_file(
    path: str | Path,
    extract_kompas_resources: bool = True,
) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise FileReaderError(f"Файл не найден: {path}")

    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise FileReaderError(
            f"Формат {ext or '(без расширения)'} не поддерживается. "
            f"Доступны: {supported}"
        )

    if ext == ".dxf":
        from dxf_reader import read_dxf

        return {
            "source_type": "dxf",
            "path": str(path),
            "file_name": path.name,
            "dxf": read_dxf(path),
        }

    if ext in {".cdw", ".m3d"}:
        from kompas_reader import read_kompas

        return {
            "source_type": ext.lstrip("."),
            "path": str(path),
            "file_name": path.name,
            "kompas": read_kompas(
                path,
                extract_resources=extract_kompas_resources,
            ),
        }

    if ext == ".pdf":
        # PDF пока отдаём существующему анализатору.
        from drawing_analyzer import extract_pdf_text

        return {
            "source_type": "pdf",
            "path": str(path),
            "file_name": path.name,
            "text": extract_pdf_text(path),
        }

    # PNG/JPG/JPEG
    return {
        "source_type": "image",
        "path": str(path),
        "file_name": path.name,
        "image_path": str(path),
    }


def is_supported_file(path_or_name: str | Path) -> bool:
    return Path(path_or_name).suffix.lower() in SUPPORTED_EXTENSIONS
