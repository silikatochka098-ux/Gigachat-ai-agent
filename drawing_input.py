from __future__ import annotations

from typing import Any


def _fmt(value: Any, digits: int = 2) -> str:
    """Красивое представление числа."""

    if value is None:
        return "не указано"

    if isinstance(value, float):
        return f"{value:.{digits}f}"

    return str(value)


def dxf_to_ai_text(dxf: dict[str, Any]) -> str:
    """
    Преобразует данные DXF из dxf_reader.py
    в текстовый контекст для AI.
    """

    lines = []

    lines.append("Формат чертежа: DXF")

    version = dxf.get("version")
    if version:
        lines.append(f"Версия DXF: {version}")

    units = dxf.get("units")
    if units:
        lines.append(f"Единицы измерения: {units}")

    # ---------------------------------------------------------
    # Габариты
    # ---------------------------------------------------------

    dimensions = dxf.get("dimensions") or {}

    width = dimensions.get("width_mm")
    height = dimensions.get("height_mm")

    if width is not None or height is not None:
        lines.append(
            f"Габариты геометрии: "
            f"{_fmt(width)} × {_fmt(height)} мм"
        )

    # ---------------------------------------------------------
    # Статистика
    # ---------------------------------------------------------

    statistics = dxf.get("statistics") or {}

    line_count = statistics.get("line_count")
    circle_count = statistics.get("circle_count")
    arc_count = statistics.get("arc_count")
    text_count = statistics.get("text_count")

    if line_count is not None:
        lines.append(
            f"Количество линий: {line_count}"
        )

    if circle_count is not None:
        lines.append(
            f"Количество окружностей: {circle_count}"
        )

    if arc_count is not None:
        lines.append(
            f"Количество дуг: {arc_count}"
        )

    if text_count is not None:
        lines.append(
            f"Количество текстовых объектов: {text_count}"
        )

    # ---------------------------------------------------------
    # Длины
    # ---------------------------------------------------------

    total_line_length = statistics.get(
        "total_line_length"
    )

    if total_line_length is not None:
        lines.append(
            f"Общая длина прямых участков: "
            f"{_fmt(total_line_length)} мм"
        )

    total_arc_length = statistics.get(
        "total_arc_length"
    )

    if total_arc_length is not None:
        lines.append(
            f"Общая длина дуг: "
            f"{_fmt(total_arc_length)} мм"
        )

    # ---------------------------------------------------------
    # Диаметры
    # ---------------------------------------------------------

    circle_diameters = statistics.get(
        "circle_diameters"
    ) or []

    if circle_diameters:
        unique_diameters = sorted(
            set(
                round(float(d), 3)
                for d in circle_diameters
            )
        )

        diameter_text = ", ".join(
            f"Ø{_fmt(d, 3)} мм"
            for d in unique_diameters
        )

        lines.append(
            f"Диаметры окружностей: "
            f"{diameter_text}"
        )

    # ---------------------------------------------------------
    # Тексты
    # ---------------------------------------------------------

    texts = dxf.get("texts") or []

    if texts:
        lines.append("")
        lines.append(
            "Тексты, найденные на чертеже:"
        )

        for text in texts[:100]:

            if isinstance(text, dict):
                value = (
                    text.get("text")
                    or text.get("value")
                    or ""
                )
            else:
                value = str(text)

            value = str(value).strip()

            if value:
                lines.append(
                    f"- {value}"
                )

    # ---------------------------------------------------------
    # Предупреждения
    # ---------------------------------------------------------

    warnings = dxf.get("warnings") or []

    if warnings:
        lines.append("")
        lines.append(
            "Предупреждения:"
        )

        for warning in warnings:
            lines.append(
                f"- {warning}"
            )

    return "\n".join(lines)


def kompas_to_ai_text(
    kompas: dict[str, Any]
) -> str:
    """
    Преобразует данные CDW/M3D из kompas_reader.py
    в текстовый контекст для AI.
    """

    lines = []

    file_format = str(
        kompas.get("format", "KOMPAS")
    ).upper()

    lines.append(
        f"Формат чертежа: {file_format}"
    )

    # ---------------------------------------------------------
    # Информация о KOMPAS
    # ---------------------------------------------------------

    kompas_info = kompas.get("kompas") or {}

    if isinstance(kompas_info, dict):

        app_name = kompas_info.get(
            "AppName"
        )

        app_version = kompas_info.get(
            "AppVersion"
        )

        file_type_name = kompas_info.get(
            "FileTypeName"
        )

        if app_name:
            lines.append(
                f"Программа: {app_name}"
            )

        if app_version:
            lines.append(
                f"Версия программы: {app_version}"
            )

        if file_type_name:
            lines.append(
                f"Тип файла KOMPAS: "
                f"{file_type_name}"
            )

    # ---------------------------------------------------------
    # Метаданные
    # ---------------------------------------------------------

    metadata = kompas.get(
        "metadata"
    ) or {}

    if isinstance(metadata, dict):

        product_info = metadata.get(
            "product_info"
        ) or {}

        if isinstance(product_info, dict):

            properties = product_info.get(
                "properties"
            ) or {}

            if properties:
                lines.append("")
                lines.append(
                    "Параметры изделия:"
                )

                for key, value in properties.items():

                    if value is not None:
                        value = str(value).strip()

                        if value:
                            lines.append(
                                f"- {key}: {value}"
                            )

            descriptions = product_info.get(
                "property_descriptions"
            ) or {}

            if descriptions:
                lines.append("")
                lines.append(
                    "Доступные свойства KOMPAS:"
                )

                for key, description in descriptions.items():

                    lines.append(
                        f"- {key}: {description}"
                    )

    # ---------------------------------------------------------
    # Ресурсы
    # ---------------------------------------------------------

    resources = kompas.get(
        "resources"
    ) or []

    if resources:

        lines.append("")
        lines.append(
            f"Извлечено ресурсов: "
            f"{len(resources)}"
        )

        for resource in resources:

            if not isinstance(resource, dict):
                continue

            name = resource.get(
                "name"
            )

            if name:
                lines.append(
                    f"- {name}"
                )

    # ---------------------------------------------------------
    # Конвертация
    # ---------------------------------------------------------

    conversion = kompas.get(
        "conversion"
    ) or {}

    if not conversion.get("available"):
        lines.append("")
        lines.append(
            "Примечание: полная геометрия "
            "CDW/M3D пока не извлекается. "
            "Доступны метаданные и встроенные ресурсы."
        )

    # ---------------------------------------------------------
    # Предупреждения
    # ---------------------------------------------------------

    warnings = kompas.get(
        "warnings"
    ) or []

    for warning in warnings:

        if warning not in lines:
            lines.append(
                f"Предупреждение: {warning}"
            )

    return "\n".join(lines)


def prepare_for_analyzer(
    drawing: dict[str, Any]
) -> dict[str, Any]:
    """
    Приводит результат file_reader.py
    к единому формату для AI-анализатора.

    Реальная структура file_reader:

    {
        "source_type": "dxf",
        "path": "...",
        "file_name": "...",
        "dxf": {...}
    }

    или:

    {
        "source_type": "m3d",
        "path": "...",
        "file_name": "...",
        "kompas": {...}
    }
    """

    if not isinstance(drawing, dict):
        raise TypeError(
            "drawing должен быть словарём"
        )

    source_type = str(
        drawing.get("source_type", "")
    ).lower()

    file_name = drawing.get(
        "file_name"
    )

    path = drawing.get(
        "path"
    )

    # ---------------------------------------------------------
    # DXF
    # ---------------------------------------------------------

    if source_type == "dxf":

        dxf_data = drawing.get(
            "dxf"
        ) or {}

        text = dxf_to_ai_text(
            dxf_data
        )

        return {
            "source_type": "dxf",
            "file_name": file_name,
            "path": path,
            "text": text,
            "structured": dxf_data,
            "image_path": None,
        }

    # ---------------------------------------------------------
    # CDW / M3D
    # ---------------------------------------------------------

    if source_type in {
        "cdw",
        "m3d",
    }:

        kompas_data = drawing.get(
            "kompas"
        ) or {}

        text = kompas_to_ai_text(
            kompas_data
        )

        image_path = None

        resources = kompas_data.get(
            "resources"
        ) or []

        for resource in resources:

            if not isinstance(resource, dict):
                continue

            name = str(
                resource.get("name", "")
            ).lower()

            resource_path = resource.get(
                "extracted_to"
            )

            if (
                resource_path
                and "preview" in name
            ):
                image_path = resource_path
                break

        return {
            "source_type": source_type,
            "file_name": file_name,
            "path": path,
            "text": text,
            "structured": kompas_data,
            "image_path": image_path,
        }

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    if source_type == "pdf":

        return {
            "source_type": "pdf",
            "file_name": file_name,
            "path": path,
            "text": drawing.get(
                "text",
                ""
            ),
            "structured": drawing,
            "image_path": None,
        }

    # ---------------------------------------------------------
    # Изображения
    # ---------------------------------------------------------

    if source_type in {
        "png",
        "jpg",
        "jpeg",
    }:

        return {
            "source_type": source_type,
            "file_name": file_name,
            "path": path,
            "text": drawing.get(
                "text",
                ""
            ),
            "structured": drawing,
            "image_path": drawing.get(
                "image_path"
            ) or path,
        }

    raise ValueError(
        f"Неподдерживаемый формат: "
        f"{source_type or 'не указан'}"
    )


def build_ai_context(
    drawing: dict[str, Any],
    description: str = ""
) -> str:
    """
    Формирует единый текстовый контекст
    для передачи в GigaChat.
    """

    if not isinstance(drawing, dict):
        raise TypeError(
            "drawing должен быть словарём"
        )

    parts = []

    source_type = drawing.get(
        "source_type"
    )

    file_name = drawing.get(
        "file_name"
    )

    if source_type:
        parts.append(
            f"Источник: {source_type}"
        )

    if file_name:
        parts.append(
            f"Файл: {file_name}"
        )

    text = drawing.get(
        "text"
    )

    if text:
        parts.append("")
        parts.append(
            "Информация, извлечённая "
            "из файла:"
        )
        parts.append(
            str(text)
        )

    if description:
        parts.append("")
        parts.append(
            "Дополнительное описание "
            "пользователя:"
        )
        parts.append(
            description.strip()
        )

    return "\n".join(parts)
