"""
kompas_reader.py

Чтение контейнеров КОМПАС-3D .cdw и .m3d на уровне, доступном без
установленного КОМПАС-3D.

Важно:
.cdw/.m3d являются проприетарными форматами. В предоставленных заказчиком
файлах они представлены ZIP-подобным контейнером с бинарным Contents и
метаданными XML/текстом.

Этот модуль:
1. проверяет формат;
2. извлекает FileInfo;
3. извлекает MetaInfo и MetaProductInfo;
4. ищет человекочитаемые значения свойств;
5. сохраняет встроенные ресурсы/preview во временную папку;
6. возвращает данные в едином формате.

Полный разбор геометрии CDW/M3D без КОМПАС-3D здесь намеренно не имитируется.
Если в окружении появится официальный/совместимый конвертер, его можно
подключить через convert_kompas_file().
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET


class KompasReaderError(Exception):
    """Ошибка чтения КОМПАС-файла."""


SUPPORTED = {".cdw", ".m3d"}


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-16", "utf-8", "cp1251", "latin-1"):
        try:
            text = data.decode(encoding)
            if "\x00" not in text[:500]:
                return text
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def _parse_file_info(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _extract_property_descriptions(root: ET.Element) -> dict[str, str]:
    descriptions = {}
    for node in root.iter():
        if node.tag.endswith("propertyDescription"):
            unique = node.attrib.get("unique_name")
            name = node.attrib.get("name")
            if unique:
                descriptions[unique] = name or unique
    return descriptions


def _parse_meta_product_info(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "properties": {},
        "property_descriptions": {},
        "raw_xml_available": bool(text.strip()),
    }

    try:
        root = ET.fromstring(text.lstrip("\ufeff"))
    except Exception:
        # XML может содержать нестандартные/повреждённые участки.
        # Сохраняем факт наличия метаданных, не выдумывая значения.
        return data

    data["property_descriptions"] = _extract_property_descriptions(root)

    # Универсально ищем элементы/атрибуты вида:
    # unique_name="material", value="..."
    # name="Материал", value="..."
    for node in root.iter():
        attrs = node.attrib
        key = attrs.get("unique_name") or attrs.get("name")
        value = attrs.get("value")

        if key and value is not None and value.strip():
            data["properties"][key] = value.strip()

    return data


def read_kompas(path: str | Path, extract_resources: bool = True) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise KompasReaderError(f"Файл не найден: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise KompasReaderError(
            f"Поддерживаются .cdw и .m3d, получен {path.suffix}"
        )

    if not zipfile.is_zipfile(path):
        raise KompasReaderError(
            "Файл имеет расширение КОМПАС, но не распознаётся как "
            "контейнер КОМПАС-3D."
        )

    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()

        result: dict[str, Any] = {
            "format": ext.lstrip(".").upper(),
            "file_name": path.name,
            "kompas": {},
            "metadata": {},
            "resources": [],
            "conversion": {
                "available": False,
                "method": None,
                "file": None,
            },
            "warnings": [],
        }

        # FileInfo
        if "FileInfo" in names:
            info_text = _decode_text(z.read("FileInfo"))
            result["kompas"] = _parse_file_info(info_text)
        else:
            result["warnings"].append("В контейнере отсутствует FileInfo.")

        # MetaInfo
        if "MetaInfo" in names:
            result["metadata"]["meta_info"] = _decode_text(z.read("MetaInfo"))

        # MetaProductInfo
        if "MetaProductInfo" in names:
            mpi_text = _decode_text(z.read("MetaProductInfo"))
            result["metadata"]["product_info"] = _parse_meta_product_info(
                mpi_text
            )

        # Список ресурсов. Бинарные Contents намеренно не выдаём как
        # "геометрию": это внутренний формат КОМПАС.
        for name in names:
            result["resources"].append({
                "name": name,
                "size": z.getinfo(name).file_size,
            })

        if "Contents" not in names:
            result["warnings"].append(
                "В контейнере отсутствует Contents — файл может быть неполным."
            )

        # Preview и дополнительные картинки сохраняем как бинарные ресурсы.
        # Это позволяет следующим этапом подключить визуальный анализ.
        if extract_resources:
            temp_dir = Path(tempfile.mkdtemp(prefix="kompas_"))

            preview_candidates = [
                n for n in names
                if n.lower().startswith("preview")
                or n.lower().startswith("images")
            ]

            for name in preview_candidates:
                try:
                    out = temp_dir / Path(name.replace("\\", "/")).name
                    out.write_bytes(z.read(name))
                    result["resources"][
                        next(
                            i for i, r in enumerate(result["resources"])
                            if r["name"] == name
                        )
                    ]["extracted_to"] = str(out)
                except Exception as exc:
                    result["warnings"].append(
                        f"Не удалось извлечь ресурс {name}: {exc}"
                    )

            result["resource_directory"] = str(temp_dir)

        # Очень полезные свойства пытаемся найти по текстовым XML-данным.
        props = result["metadata"].get("product_info", {}).get(
            "properties", {}
        )
        aliases = {
            "name": "name",
            "marking": "marking",
            "material": "material",
            "count": "count",
            "mass": "mass",
            "material.density": "material_density",
        }

        normalized = {}
        for key, value in props.items():
            normalized[aliases.get(key, key)] = value

        result["normalized"] = normalized

        # Явно обозначаем ограничение текущего режима.
        result["warnings"].append(
            "Полная геометрия .cdw/.m3d не извлекается этим адаптером. "
            "Для неё нужен КОМПАС-3D или совместимый CAD-конвертер. "
            "Метаданные и встроенные ресурсы читаются."
        )

        return result


def convert_kompas_file(
    path: str | Path,
    output_dir: str | Path | None = None,
) -> Path:
    """
    Точка подключения будущего внешнего конвертера КОМПАС.

    Сейчас намеренно не притворяется конвертером:
    в Linux/Codespaces нет гарантированно доступного КОМПАС-3D.

    Когда заказчик даст Windows-машину/сервер с КОМПАС-3D или другой
    совместимый CLI-конвертер, сюда можно подключить subprocess.
    """
    raise KompasReaderError(
        "Автоматическая конвертация .cdw/.m3d пока не настроена. "
        "Файлы уже читаются как контейнеры и их метаданные извлекаются, "
        "но для получения полной геометрии нужен CAD-конвертер."
    )
