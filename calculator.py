from __future__ import annotations

import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import openpyxl


VAT = 0.22
WORKBOOK_SHEET = "Расчёт"
METAL_SHEET = "Цены на металл"
QUOTE_SHEET = "КП с ндс"

# Блоки в готовом Excel-калькуляторе. Каждый блок = один вид изделия.
BLOCKS = [
    {"index": 1, "start": 3, "total": 8},
    {"index": 2, "start": 12, "total": 17},
    {"index": 3, "start": 21, "total": 26},
    {"index": 4, "start": 30, "total": 35},
    {"index": 5, "start": 39, "total": 44},
    {"index": 6, "start": 48, "total": 53},
    {"index": 7, "start": 57, "total": 62},
    {"index": 8, "start": 66, "total": 71},
    {"index": 9, "start": 75, "total": 80},
    {"index": 10, "start": 84, "total": 89},
]

# Строки операций внутри каждого блока.
OP_ROWS = {
    "лазерная резка": 0,
    "гибка": 1,
    "токарная обработка": 2,
    "токарка": 2,
    "сварка": 3,
    "порошковая покраска": 4,
    "порошковая окраска": 4,
}


@dataclass
class ProductInput:
    """Данные одного изделия после AI-разбора чертежа."""

    name: str = "Изделие"
    material: str | None = None
    thickness_mm: float | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    quantity: int = 1
    operations: list[str] = field(default_factory=list)

    # Неизбежные технологические данные, которых нет в исходном Excel.
    # Если они не заданы, агент не придумывает их.
    operation_hours: dict[str, float] = field(default_factory=dict)
    profit_per_hour: dict[str, float] = field(default_factory=dict)

    # Геометрия, если извлечена из чертежа.
    cut_length_mm: float | None = None
    bends: int | None = None


@dataclass
class MaterialRecord:
    name: str
    price_per_ton: float | None
    sheet_area_m2: float | None
    sheet_weight_t: float | None
    sheet_price: float | None
    cut_sheet_price: float | None
    price_per_m2: float | None


class CalculatorError(ValueError):
    pass


def _norm(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).lower().replace("ё", "е")
    text = text.replace(",", ".")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


class ExcelCalculator:
    """
    Адаптер к исходному Excel-калькулятору.

    Важный принцип: ставки и коэффициенты не захардкожены заново.
    Они берутся из листа «Расчёт» и таблицы «Цены на металл».
    Поэтому изменение Excel автоматически меняет будущие расчёты.
    """

    def __init__(self, template_path: str | Path):
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(self.template_path)

    def load(self, data_only: bool = False):
        return openpyxl.load_workbook(
            self.template_path,
            data_only=data_only,
        )

    def materials(self) -> list[MaterialRecord]:
        wb = self.load(data_only=True)
        ws = wb[METAL_SHEET]
        result: list[MaterialRecord] = []

        for row in range(3, 31):
            name = ws.cell(row, 1).value
            if not name or _norm(name).startswith("другой материал"):
                continue
            result.append(
                MaterialRecord(
                    name=str(name),
                    price_per_ton=_num(ws.cell(row, 2).value),
                    sheet_area_m2=_num(ws.cell(row, 3).value),
                    sheet_weight_t=_num(ws.cell(row, 5).value),
                    sheet_price=_num(ws.cell(row, 7).value),
                    cut_sheet_price=_num(ws.cell(row, 6).value),
                    price_per_m2=_num(ws.cell(row, 8).value),
                )
            )
        return result

    def rates(self) -> dict[str, float]:
        """Считывает текущие почасовые ставки из Excel."""
        wb = self.load(data_only=True)
        ws = wb[WORKBOOK_SHEET]
        return {
            "лазерная резка": _num(ws["G3"].value) or 0,
            "гибка": _num(ws["G4"].value) or 0,
            "токарка": _num(ws["G5"].value) or 0,
            "сварка": _num(ws["G6"].value) or 0,
            "порошковая покраска": _num(ws["G7"].value) or 0,
            "скорость_гибки_шт_в_час": 84.0,
            "скорость_покраски_м2_в_час": 5.53,
            "расход_порошка_кг_на_м2": 0.3,
        }

    def find_material(
        self,
        material: str,
        thickness_mm: float,
    ) -> MaterialRecord:
        """
        Ищет точную строку материала по марке + толщине.
        Не выбирает ближайшую толщину молча.
        """
        m = _norm(material)
        t = round(float(thickness_mm), 3)

        aliases = {
            "ст3": ["ст3"],
            "ст 3": ["ст3"],
            "ст3пс": ["ст3"],
            "ст3сп": ["ст3"],
            "хк": ["х.к. сталь", "х.к.сталь"],
            "холоднокатаная сталь": ["х.к. сталь"],
            "оц": ["оц. сталь"],
            "оцинкованная сталь": ["оц. сталь"],
            "нж": ["нж"],
            "нержавейка": ["нж"],
            "aisi 304": ["aisi 304"],
        }

        candidates = []
        for rec in self.materials():
            n = _norm(rec.name)
            thick_match = re.search(r"(\d+(?:\.\d+)?)\s*мм", n)
            if not thick_match:
                continue
            rec_t = float(thick_match.group(1))
            if abs(rec_t - t) > 1e-6:
                continue
            candidates.append(rec)

        if not candidates:
            raise CalculatorError(
                f"В Excel не найдена строка материала для толщины {t:g} мм: {material!r}."
            )

        # Сначала прямое совпадение марки.
        for rec in candidates:
            n = _norm(rec.name)
            if m and m in n:
                return rec

        # Затем алиасы.
        for key, keys in aliases.items():
            if key in m:
                for rec in candidates:
                    n = _norm(rec.name)
                    if any(k in n for k in keys):
                        return rec

        if len(candidates) == 1:
            return candidates[0]

        raise CalculatorError(
            "Материал неоднозначен. Подтвердите марку: "
            + ", ".join(x.name for x in candidates)
        )

    @staticmethod
    def flat_area_m2(length_mm: float, width_mm: float) -> float:
        return abs(length_mm * width_mm) / 1_000_000.0

    @staticmethod
    def coating_area_m2(
        length_mm: float,
        width_mm: float,
        thickness_mm: float,
        quantity: int = 1,
        both_sides: bool = True,
    ) -> float:
        """
        Площадь окраски прямоугольной детали.
        Для листовой детали по умолчанию учитываются обе стороны и кромки.
        """
        l = length_mm / 1000
        w = width_mm / 1000
        t = thickness_mm / 1000
        area = 2 * (l * w + l * t + w * t)
        if not both_sides:
            area = l * w + 2 * (l * t + w * t)
        return area * quantity

    @staticmethod
    def sheets_required(
        part_length_mm: float,
        part_width_mm: float,
        quantity: int,
        sheet_length_mm: float,
        sheet_width_mm: float,
    ) -> int:
        """
        Безопасная верхняя оценка количества листов по прямоугольному nesting.
        Реальный CAM-nesting может уменьшить расход; код не скрывает это отличие.
        """
        if min(part_length_mm, part_width_mm, quantity) <= 0:
            raise CalculatorError("Размеры и количество должны быть положительными.")

        a = math.floor(sheet_length_mm / part_length_mm) * math.floor(
            sheet_width_mm / part_width_mm
        )
        b = math.floor(sheet_length_mm / part_width_mm) * math.floor(
            sheet_width_mm / part_length_mm
        )
        parts_per_sheet = max(a, b)
        if parts_per_sheet <= 0:
            raise CalculatorError("Деталь не помещается на выбранный лист.")
        return math.ceil(quantity / parts_per_sheet)

    def validate_product(self, p: ProductInput) -> list[str]:
        missing = []
        if not p.material:
            missing.append("материал")
        if p.thickness_mm is None:
            missing.append("толщина_мм")
        if p.length_mm is None:
            missing.append("длина_мм")
        if p.width_mm is None:
            missing.append("ширина_мм")
        if not p.quantity or p.quantity <= 0:
            missing.append("количество")
        if not p.operations:
            missing.append("операции")

        # В исходном Excel нет коэффициента скорости лазерной резки.
        # Поэтому длина реза сама по себе недостаточна для расчёта:
        # калькулятору нужно фактическое время резки (например, из CAM).
        for op in p.operations:
            key = _norm(op)

            if key == "лазерная резка":
                if p.operation_hours.get(key) is None:
                    missing.append("время лазерной резки")

            elif key in {"сварка", "токарка", "токарная обработка"}:
                if p.operation_hours.get(key) is None:
                    missing.append(f"время операции «{op}»")
        return missing

    def _operation_row(self, block_start: int, op: str) -> int:
        key = _norm(op)
        if key not in OP_ROWS:
            raise CalculatorError(f"Операция пока не сопоставлена с Excel: {op}")
        return block_start + OP_ROWS[key]

    def populate_product(
        self,
        ws,
        block: dict[str, int],
        p: ProductInput,
    ) -> dict[str, Any]:
        """Заполняет один блок исходного Excel."""
        material = self.find_material(p.material, p.thickness_mm)
        start = block["start"]

        # Металл и количество листов.
        # Размеры листа извлекаются из названия строки Excel.
        dims = re.search(
            r"\((\d+)\s*[xх×]\s*(\d+)\)",
            material.name,
            flags=re.I,
        )
        if not dims:
            raise CalculatorError(f"Не удалось определить размер листа: {material.name}")
        sheet_l, sheet_w = float(dims.group(1)), float(dims.group(2))

        sheets = self.sheets_required(
            p.length_mm,
            p.width_mm,
            p.quantity,
            sheet_l,
            sheet_w,
        )

        ws.cell(start, 1).value = p.name
        ws.cell(start, 3).value = material.name
        ws.cell(start, 5).value = sheets

        used_rows = []
        for op in p.operations:
            row = self._operation_row(start, op)
            used_rows.append(row)

            key = _norm(op)
            if key == "лазерная резка":
                hours = p.operation_hours.get(key)
                if hours is None:
                    raise CalculatorError(
                        "Для лазерной резки не указано время. "
                        "Укажите время резки/CAM-время в часах."
                    )
            elif key == "гибка":
                hours = p.operation_hours.get(key)
                if hours is None and p.bends is not None:
                    hours = p.bends / self.rates()["скорость_гибки_шт_в_час"]
                if hours is None:
                    raise CalculatorError("Для гибки не указано количество гибов или время.")
            elif key == "порошковая покраска":
                area = self.coating_area_m2(
                    p.length_mm,
                    p.width_mm,
                    p.thickness_mm,
                    p.quantity,
                )
                ws.cell(row, 5).value = area
                hours = area / self.rates()["скорость_покраски_м2_в_час"]
            else:
                hours = p.operation_hours.get(key)
                if hours is None:
                    raise CalculatorError(f"Не задано время операции: {op}")

            ws.cell(row, 8).value = float(hours)

            if key in p.profit_per_hour:
                ws.cell(row, 10).value = float(p.profit_per_hour[key])

        # Для операций, где материал не задаётся отдельно, формулы Excel
        # сами оставляют материальную составляющую пустой/нулевой.
        return {
            "material_excel_name": material.name,
            "sheets_required": sheets,
            "operation_rows": used_rows,
        }

    def build_quote(
        self,
        products: Iterable[ProductInput],
        output_path: str | Path,
        customer: str | None = None,
        recalc: bool = True,
    ) -> Path:
        products = list(products)
        if not products:
            raise CalculatorError("Нет изделий для расчёта.")
        if len(products) > len(BLOCKS):
            raise CalculatorError("Исходный Excel поддерживает максимум 10 позиций.")

        for p in products:
            errors = self.validate_product(p)
            if errors:
                raise CalculatorError(
                    f"Недостаточно данных для «{p.name}»: {', '.join(errors)}"
                )

        wb = self.load(data_only=False)
        ws = wb[WORKBOOK_SHEET]
        quote = wb[QUOTE_SHEET]

        # Очищаем 10 блоков от предыдущего расчёта, но сохраняем формулы шаблона.
        for block in BLOCKS:
            start = block["start"]
            for r in range(start, start + 5):
                for c in [2, 3, 5, 8, 10]:
                    # Стираем только вводимые поля.
                    if c in {3, 5, 8, 10}:
                        ws.cell(r, c).value = None
            ws.cell(start, 1).value = f"Изделие {block['index']}"

        # Заполняем расчёт.
        for idx, p in enumerate(products):
            block = BLOCKS[idx]
            self.populate_product(ws, block, p)

        # КП: строки 15..24 уже связаны формулами с блоками.
        for i in range(10):
            row = 15 + i
            if i < len(products):
                quote.cell(row, 1).value = i + 1
                quote.cell(row, 3).value = products[i].quantity
            else:
                quote.cell(row, 1).value = None
                quote.cell(row, 3).value = None
                quote.cell(row, 4).value = None
                quote.cell(row, 5).value = None

        if customer:
            quote["A6"].value = f"Заказчик: {customer}"

        # Excel/LibreOffice пересчитает формулы при открытии.
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Сохраняем исходную книгу с формулами.
        wb.save(output_path)

        # Сначала обязательно пересчитываем книгу через LibreOffice.
        # После этого в файле появляются кэшированные результаты формул.
        if recalc:
            self.recalculate_with_libreoffice(output_path)

        # Открываем пересчитанный файл ДВА раза:
        #
        # 1. wb_formula — обычная книга с формулами и оформлением.
        # 2. wb_values — книга только для чтения рассчитанных значений.
        wb_formula = openpyxl.load_workbook(
            output_path,
            data_only=False,
        )
        wb_values = openpyxl.load_workbook(
            output_path,
            data_only=True,
        )

        quote_ws = wb_formula[QUOTE_SHEET]
        quote_values_ws = wb_values[QUOTE_SHEET]

        # Заменяем каждую формулу на её рассчитанное значение.
        # Это делается ДО удаления листа "Расчёт", потому что
        # формулы КП могут ссылаться на него.
        replaced_formulas = 0

        for row in quote_ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cell.value = quote_values_ws[cell.coordinate].value
                    replaced_formulas += 1

        # После замены формул лист "КП с ндс" больше ни от чего
        # не зависит, поэтому можно удалить внутренние листы.
        for sheet_name in list(wb_formula.sheetnames):
            if sheet_name != QUOTE_SHEET:
                del wb_formula[sheet_name]

        # Сохраняем чистое КП.
        wb_formula.save(output_path)

        print(
            f"✅ Готовое КП создано. "
            f"Формул заменено на значения: {replaced_formulas}"
        )

        return output_path

    @staticmethod
    def recalculate_with_libreoffice(file_path: Path):
        """Пересчитывает формулы в Excel через LibreOffice."""
        if not shutil.which("libreoffice"):
            raise CalculatorError(
                "LibreOffice не найден в PATH. Установите его для пересчёта формул."
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            # LibreOffice создаёт временный файл с результатами.
            subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--calc",
                    "--convert-to",
                    "xlsx",
                    "--outdir",
                    str(tmpdir_path),
                    str(file_path),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Перемещаем пересчитанный файл обратно.
            converted_file = tmpdir_path / file_path.name
            if not converted_file.exists():
                raise CalculatorError(
                    "LibreOffice не создал пересчитанный файл. "
                    "Проверьте установку LibreOffice."
                )
            shutil.move(str(converted_file), str(file_path))


def product_from_parameters(parameters: dict[str, Any]) -> ProductInput:
    """Преобразует JSON от AI в строго типизированный объект калькулятора."""
    ops = parameters.get("операции") or []
    if isinstance(ops, str):
        ops = [ops]

    return ProductInput(
        name=parameters.get("название") or "Изделие",
        material=parameters.get("материал"),
        thickness_mm=_num(parameters.get("толщина_мм")),
        length_mm=_num(parameters.get("длина_мм")),
        width_mm=_num(parameters.get("ширина_мм")),
        quantity=int(parameters["количество"])
        if parameters.get("количество") is not None
        else 0,
        operations=list(ops),
        operation_hours={
            _norm(k): float(v)
            for k, v in (parameters.get("время_операций") or {}).items()
            if v is not None
        },
        profit_per_hour={
            _norm(k): float(v)
            for k, v in (parameters.get("прибыль_с_часа") or {}).items()
            if v is not None
        },
        cut_length_mm=_num(parameters.get("длина_реза_мм")),
        bends=int(parameters["количество_гибов"])
        if parameters.get("количество_гибов") is not None
        else None,
    )
def calculate_from_ai_parameters(
    parameters: dict[str, Any],
    template_path: str | Path,
    output_path: str | Path,
    customer: str | None = None,
) -> Path:
    """
    Получает JSON-параметры от ИИ,
    преобразует их в ProductInput
    и запускает Excel-калькулятор.
    """

    product = product_from_parameters(parameters)

    calculator = ExcelCalculator(template_path)

    return calculator.build_quote(
        products=[product],
        output_path=output_path,
        customer=customer,
    )