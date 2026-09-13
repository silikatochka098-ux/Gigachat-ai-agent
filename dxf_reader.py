"""
dxf_reader.py
Чтение DXF-файлов без преобразования в изображение.

Зависимость:
    pip install ezdxf

Что извлекаем:
- LINE: длина и координаты;
- CIRCLE: радиус, диаметр, центр;
- ARC: радиус, диаметр, длина дуги, углы;
- TEXT/MTEXT: если присутствуют;
- EXTMIN/EXTMAX из HEADER;
- габарит геометрии;
- суммарную длину линий и дуг;
- количество окружностей и их диаметры.

Важно:
DXF может содержать геометрию без размеров/текстовых подписей. Поэтому
этот модуль не "угадывает" размеры изделия: он возвращает фактические
геометрические данные, которые затем может интерпретировать AI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import math


class DXFReaderError(Exception):
    """Ошибка чтения DXF."""


def _point(p) -> dict[str, float]:
    return {
        "x": round(float(p[0]), 6),
        "y": round(float(p[1]), 6),
        "z": round(float(p[2]), 6) if len(p) > 2 else 0.0,
    }


def _arc_length(radius: float, start_deg: float, end_deg: float) -> float:
    angle = (end_deg - start_deg) % 360.0
    return 2.0 * math.pi * radius * angle / 360.0


def read_dxf(path: str | Path, max_entities: int = 5000) -> dict[str, Any]:
    """
    Читает DXF и возвращает нормализованную структуру.

    max_entities защищает приложение от случайно огромных DXF.
    """
    try:
        import ezdxf
    except ImportError as exc:
        raise DXFReaderError(
            "Не установлен ezdxf. Выполните: pip install ezdxf"
        ) from exc

    path = Path(path)
    if not path.exists():
        raise DXFReaderError(f"Файл не найден: {path}")

    if path.suffix.lower() != ".dxf":
        raise DXFReaderError(f"Ожидался .dxf, получен: {path.suffix}")

    try:
        doc = ezdxf.readfile(path)
    except Exception as exc:
        raise DXFReaderError(f"Не удалось открыть DXF: {exc}") from exc

    msp = doc.modelspace()

    result: dict[str, Any] = {
        "format": "DXF",
        "version": doc.dxfversion,
        "file_name": path.name,
        "units": None,
        "bounds": None,
        "dimensions": {
            "width_mm": None,
            "height_mm": None,
        },
        "geometry": {
            "lines": [],
            "circles": [],
            "arcs": [],
        },
        "texts": [],
        "statistics": {
            "line_count": 0,
            "circle_count": 0,
            "arc_count": 0,
            "text_count": 0,
            "total_line_length": 0.0,
            "total_arc_length": 0.0,
            "circle_diameters": [],
        },
        "warnings": [],
    }

    # $INSUNITS: 4 = mm, 5 = cm, 6 = m, 1 = inch, 2 = foot.
    units_map = {
        0: None,
        1: "inch",
        2: "foot",
        3: "mile",
        4: "mm",
        5: "cm",
        6: "m",
        7: "km",
        8: "microinch",
        9: "mil",
        10: "yard",
        11: "angstrom",
        12: "nanometer",
        13: "micron",
    }

    try:
        unit_code = int(doc.header.get("$INSUNITS", 0))
        result["units"] = units_map.get(unit_code)
    except Exception:
        result["units"] = None

    if result["units"] not in (None, "mm"):
        result["warnings"].append(
            f"Единицы DXF: {result['units']}. Для калькулятора "
            "нужна проверка перевода в миллиметры."
        )

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    def add_point(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    entity_count = 0

    for entity in msp:
        entity_count += 1
        if entity_count > max_entities:
            result["warnings"].append(
                f"Чтение ограничено первыми {max_entities} объектами."
            )
            break

        typ = entity.dxftype()

        try:
            if typ == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                length = math.dist(
                    (float(start[0]), float(start[1])),
                    (float(end[0]), float(end[1])),
                )

                result["geometry"]["lines"].append({
                    "start": _point(start),
                    "end": _point(end),
                    "length": round(length, 6),
                })
                result["statistics"]["line_count"] += 1
                result["statistics"]["total_line_length"] += length
                add_point(float(start[0]), float(start[1]))
                add_point(float(end[0]), float(end[1]))

            elif typ == "CIRCLE":
                center = entity.dxf.center
                radius = float(entity.dxf.radius)
                diameter = radius * 2.0

                result["geometry"]["circles"].append({
                    "center": _point(center),
                    "radius": round(radius, 6),
                    "diameter": round(diameter, 6),
                })
                result["statistics"]["circle_count"] += 1
                result["statistics"]["circle_diameters"].append(
                    round(diameter, 6)
                )

                add_point(float(center[0]) - radius, float(center[1]) - radius)
                add_point(float(center[0]) + radius, float(center[1]) + radius)

            elif typ == "ARC":
                center = entity.dxf.center
                radius = float(entity.dxf.radius)
                start_deg = float(entity.dxf.start_angle)
                end_deg = float(entity.dxf.end_angle)
                length = _arc_length(radius, start_deg, end_deg)

                result["geometry"]["arcs"].append({
                    "center": _point(center),
                    "radius": round(radius, 6),
                    "start_angle_deg": round(start_deg, 6),
                    "end_angle_deg": round(end_deg, 6),
                    "length": round(length, 6),
                })
                result["statistics"]["arc_count"] += 1
                result["statistics"]["total_arc_length"] += length

                # Для габарита учитываем центр + радиус как безопасную
                # геометрическую оценку охвата дуги.
                add_point(float(center[0]) - radius, float(center[1]) - radius)
                add_point(float(center[0]) + radius, float(center[1]) + radius)

            elif typ == "TEXT":
                text = str(entity.dxf.text or "").strip()
                if text:
                    result["texts"].append({
                        "type": "TEXT",
                        "text": text,
                        "position": _point(entity.dxf.insert),
                        "height": float(entity.dxf.height),
                    })
                    result["statistics"]["text_count"] += 1

            elif typ == "MTEXT":
                text = str(entity.plain_mtext() or "").strip()
                if text:
                    result["texts"].append({
                        "type": "MTEXT",
                        "text": text,
                        "position": _point(entity.dxf.insert),
                        "height": float(entity.dxf.char_height),
                    })
                    result["statistics"]["text_count"] += 1

        except Exception as exc:
            result["warnings"].append(
                f"Не удалось обработать объект {typ}: {exc}"
            )

    if min_x != float("inf"):
        width = max_x - min_x
        height = max_y - min_y
        result["bounds"] = {
            "min_x": round(min_x, 6),
            "min_y": round(min_y, 6),
            "max_x": round(max_x, 6),
            "max_y": round(max_y, 6),
        }
        if result["units"] == "mm":
            result["dimensions"]["width_mm"] = round(width, 6)
            result["dimensions"]["height_mm"] = round(height, 6)
        else:
            result["dimensions"]["width"] = round(width, 6)
            result["dimensions"]["height"] = round(height, 6)
    else:
        result["warnings"].append("В DXF не найдена геометрия.")

    result["statistics"]["total_line_length"] = round(
        result["statistics"]["total_line_length"], 6
    )
    result["statistics"]["total_arc_length"] = round(
        result["statistics"]["total_arc_length"], 6
    )

    return result
