import os
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from drawing_analyzer import (
    analyze_drawing,
    check_required_parameters,
    make_clarification_question,
    update_parameters_from_user_answer,
)

from calculator import calculate_from_ai_parameters


# ============================================================
# НАСТРОЙКИ
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

FRONTEND_DIR = BASE_DIR / "frontedik"

EXCEL_TEMPLATE = (
    BASE_DIR
    / "excel"
    / "calculator_template.xlsx"
)

OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(
    exist_ok=True
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Energon AI",
    version="1.0"
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "message": "Energon AI backend работает"
    }


@app.get("/api")
def api_root():
    return {
        "message": "Energon AI API работает"
    }


# ============================================================
# АНАЛИЗ ЧЕРТЕЖА
# ============================================================

@app.post("/api/analyze/drawing")
async def analyze_drawing_api(
    file: UploadFile = File(...),
    description: str = "",
):
    """
    Получает файл от frontend,
    передаёт его в drawing_analyzer.py
    и возвращает параметры + информацию
    о недостающих данных.
    """

    content = await file.read()

    if not content:
        return {
            "error": "EmptyFile",
            "message": "Файл пустой."
        }

    # Создаём объект, похожий на Streamlit UploadedFile.
    uploaded_file = SimpleNamespace(
        name=file.filename,
        type=file.content_type,
        size=len(content),
        getvalue=lambda: content,
    )

    try:

        # --------------------------------------------
        # Анализ чертежа
        # --------------------------------------------

        parameters = analyze_drawing(
            uploaded_file,
            description,
        )

        # Если сам анализатор вернул ошибку
        if isinstance(parameters, dict) and parameters.get("error"):
            return parameters

        # --------------------------------------------
        # Проверяем обязательные параметры
        # --------------------------------------------

        missing = check_required_parameters(
            parameters
        )

        # --------------------------------------------
        # Формируем первый вопрос
        # --------------------------------------------

        question = None

        if missing:
            question = make_clarification_question(
                missing
            )

        return {
            "parameters": parameters,
            "missing_parameters": missing,
            "question": question,
            "status": "needs_clarification"
            if missing
            else "complete",
        }

    except Exception as e:

        return {
            "error": type(e).__name__,
            "message": str(e),
        }


# ============================================================
# УТОЧНЕНИЕ ПАРАМЕТРОВ
# ============================================================

@app.post("/api/clarify")
async def clarify_api(data: dict):
    """
    Обрабатывает ответ пользователя
    на уточняющий вопрос.

    Чертёж повторно НЕ отправляется.

    Получаем:
        question
        answer
        parameters
    """

    question = data.get(
        "question",
        ""
    )

    answer = data.get(
        "answer",
        ""
    )

    parameters = (
        data.get("parameters")
        or {}
    )

    if not answer.strip():
        return {
            "error": "EmptyAnswer",
            "message": "Ответ пользователя пустой."
        }

    try:

        # --------------------------------------------
        # Отправляем в drawing_analyzer
        # --------------------------------------------

        result = update_parameters_from_user_answer(
            parameters,
            question,
            answer,
        )

        if not isinstance(result, dict):
            return {
                "error": "InvalidResponse",
                "message": (
                    "drawing_analyzer.py "
                    "вернул неожиданный формат."
                )
            }

        # --------------------------------------------
        # Получаем обновления
        # --------------------------------------------

        updates = result.get(
            "обновления",
            {}
        )

        confidence = result.get(
            "уверенность",
            "высокая"
        )

        clarification = result.get(
            "уточнение"
        )

        # --------------------------------------------
        # Обновляем текущие параметры
        # --------------------------------------------

        updated_parameters = dict(
            parameters
        )

        if isinstance(updates, dict):

            for key, value in updates.items():

                if value is not None:
                    updated_parameters[key] = value

        # --------------------------------------------
        # Если GigaChat считает ответ
        # неоднозначным
        # --------------------------------------------

        if (
            clarification
            and confidence == "низкая"
        ):

            return {
                "parameters": updated_parameters,
                "missing_parameters": (
                    check_required_parameters(
                        updated_parameters
                    )
                ),
                "question": clarification,
                "status": "needs_confirmation",
                "confidence": confidence,
            }

        # --------------------------------------------
        # Проверяем оставшиеся параметры
        # --------------------------------------------

        missing = check_required_parameters(
            updated_parameters
        )

        next_question = None

        if missing:

            next_question = (
                make_clarification_question(
                    missing
                )
            )

        return {
            "parameters": updated_parameters,
            "missing_parameters": missing,
            "question": next_question,
            "status": (
                "needs_clarification"
                if missing
                else "complete"
            ),
            "confidence": confidence,
        }

    except Exception as e:

        return {
            "error": type(e).__name__,
            "message": str(e),
        }


# ============================================================
# РАСЧЁТ В EXCEL
# ============================================================

@app.post("/api/calculator/quote")
async def calculator_quote(
    parameters: dict
):
    """
    Передаёт параметры AI
    в существующий Excel-калькулятор.

    Результатом является настоящий .xlsx файл.
    """

    # --------------------------------------------
    # Проверяем наличие шаблона
    # --------------------------------------------

    if not EXCEL_TEMPLATE.exists():

        return {
            "error": "TemplateNotFound",
            "message": (
                f"Не найден Excel-шаблон: "
                f"{EXCEL_TEMPLATE}"
            )
        }

    # --------------------------------------------
    # Проверяем обязательные параметры
    # --------------------------------------------

    missing = check_required_parameters(
        parameters
    )

    if missing:

        return {
            "error": "MissingParameters",
            "message": (
                "Для расчёта не хватает параметров."
            ),
            "missing_parameters": missing,
        }

    # --------------------------------------------
    # Уникальное имя файла
    # --------------------------------------------

    file_id = uuid.uuid4().hex[:10]

    output_path = (
        OUTPUT_DIR
        / f"КП_{file_id}.xlsx"
    )

    try:

        # --------------------------------------------
        # Запускаем существующий калькулятор
        # --------------------------------------------

        result_path = (
            calculate_from_ai_parameters(
                parameters=parameters,

                template_path=(
                    str(EXCEL_TEMPLATE)
                ),

                output_path=(
                    str(output_path)
                ),
            )
        )

        result_path = Path(
            result_path
        )

        if not result_path.exists():

            return {
                "error": "QuoteNotCreated",
                "message": (
                    "Калькулятор не создал "
                    "итоговый Excel-файл."
                )
            }

        return {
            "status": "complete",

            "filename": (
                result_path.name
            ),

            "download_url": (
                f"/api/calculator/download/"
                f"{result_path.name}"
            ),
        }

    except Exception as e:

        return {
            "error": type(e).__name__,
            "message": str(e),
        }


# ============================================================
# СКАЧИВАНИЕ ГОТОВОГО КП
# ============================================================

@app.get(
    "/api/calculator/download/{filename}"
)
def download_quote(filename: str):

    # Защита от попыток обратиться
    # к файлам за пределами outputs.
    safe_name = Path(filename).name

    file_path = (
        OUTPUT_DIR
        / safe_name
    )

    if not file_path.exists():

        return {
            "error": "FileNotFound",
            "message": "КП не найдено."
        }

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


# ============================================================
# FRONTEND
# ============================================================

# Очень важно:
# API-маршруты объявлены ДО этого mount.
#
# Поэтому:
#
# /api/... → FastAPI
#
# /        → frontedik/index.html
# /app.js  → frontedik/app.js
# /styles.css → frontedik/styles.css

app.mount(
    "/",
    StaticFiles(
        directory=str(FRONTEND_DIR),
        html=True,
    ),
    name="frontend",
)