import json
import os
import base64
import tempfile

from dotenv import load_dotenv
from pypdf import PdfReader
from gigachat import GigaChat
from gigachat.models import ChatCompletionRequest, ChatContentPart

load_dotenv()

api_key = os.getenv("GIGACHAT_API_KEY")
BASE_URL = "https://api.giga.chat/v1"
MODEL = "GigaChat-2-Max"


PROMPT = """
Ты — инженер-технолог, который анализирует машиностроительные технические чертежи.

Твоя задача — определить только те параметры изделия, которые явно указаны
в тексте/изображении чертежа или в описании пользователя.

НЕ ПРИДУМЫВАЙ значения. Если параметр нельзя определить надёжно — null.

Верни СТРОГО JSON:

{
    "название": null,
    "материал": null,
    "толщина_мм": null,
    "длина_мм": null,
    "ширина_мм": null,
    "количество": null,
    "операции": [],
    "время_операций": {},
    "длина_реза_мм": null,
    "количество_гибов": null,
    "отверстия": [],
    "резьба": [],
    "дополнительные_размеры": [],
    "масса_кг": null,
    "примечания": []
}

Правила:
1. Не путай габаритные размеры с другими размерами.
2. Толщину металла указывай отдельно.
3. Диаметр отверстия обозначается Ø.
4. Резьбовые отверстия указывай отдельно.
5. "N мест" означает количество соответствующих отверстий/элементов.
6. Указывай углы и радиусы, если они явно указаны.
7. Материал бери только из источника.
8. Не считай любое найденное число габаритным размером.
9. В "операции" указывай только явно указанные операции.
10. Время операции записывай в часах и только если оно явно указано.
11. НЕ вычисляй время лазерной резки по длине реза.
12. "длина_реза_мм" заполняй только если она явно указана.
13. "количество_гибов" заполняй только если оно явно указано или однозначно следует из чертежа.
14. Если время лазерной резки отсутствует, оставляй его пустым.
    В таком случае приложение должно спросить пользователя.
15. Для расчёта нужны:
    материал, толщина, длина, ширина, количество и операции.
16. Для лазерной резки дополнительно обязательно время резки.
17. Для сварки дополнительно обязательно время сварки.
18. Для токарной обработки дополнительно обязательно время обработки.
19. Для гибки достаточно количества гибов; калькулятор сам рассчитает время.
20. Для порошковой покраски время рассчитывается калькулятором.
21. Не добавляй текст за пределами JSON.
"""


def check_api_key():
    if not api_key or not api_key.strip():
        raise ValueError("GIGACHAT_API_KEY не найден в .env")


def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def image_to_base64(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")


def parse_json_response(answer):
    answer = answer.strip()

    if answer.startswith("```"):
        answer = answer.replace("```json", "")
        answer = answer.replace("```", "").strip()

    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        start = answer.find("{")
        end = answer.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(answer[start:end + 1])
            except json.JSONDecodeError:
                return {
                    "error": "GigaChat вернул невалидный JSON",
                    "raw_response": answer
                }
        else:
            return {
                "error": "GigaChat вернул невалидный JSON",
                "raw_response": answer
            }

    if not isinstance(data, dict):
        return {
            "error": "GigaChat вернул JSON не в виде объекта",
            "raw_response": answer
        }

    defaults = {
        "название": None,
        "материал": None,
        "толщина_мм": None,
        "длина_мм": None,
        "ширина_мм": None,
        "количество": None,
        "операции": [],
        "время_операций": {},
        "длина_реза_мм": None,
        "количество_гибов": None,
        "отверстия": [],
        "резьба": [],
        "дополнительные_размеры": [],
        "масса_кг": None,
        "примечания": []
    }

    for key, value in defaults.items():
        data.setdefault(key, value)

    return data


def analyze_text_with_gigachat(pdf_text, description=""):
    check_api_key()

    full_prompt = (
        PROMPT
        + "\n\nТЕКСТ ЧЕРТЕЖА:\n"
        + pdf_text
        + "\n\nТЕКСТОВОЕ ОПИСАНИЕ ЗАЯВКИ:\n"
        + description
    )

    with GigaChat(
        credentials=api_key,
        model=MODEL,
        base_url=BASE_URL,
        verify_ssl_certs=False
    ) as client:
        response = client.chat.create(full_prompt)
        answer = response.messages[0].content[0].text

    return parse_json_response(answer)


def analyze_image_with_gigachat(uploaded_file, description=""):
    check_api_key()

    image_base64 = image_to_base64(uploaded_file)
    image_type = uploaded_file.type or "image/png"

    prompt = (
        PROMPT
        + "\n\nТЕКСТОВОЕ ОПИСАНИЕ ЗАЯВКИ:\n"
        + description
        + "\n\nПроанализируй изображение технического чертежа. "
        + "Особенно внимательно проверь размеры, материал, толщину, "
        + "отверстия, резьбы, операции, количество гибов, время операций "
        + "и длину реза, но ничего не придумывай."
    )

    request = ChatCompletionRequest(
        messages=[
            {
                "role": "user",
                "content": [
                    ChatContentPart(type="text", text=prompt),
                    ChatContentPart(
                        type="image_url",
                        image_url={
                            "url": f"data:{image_type};base64,{image_base64}"
                        }
                    )
                ]
            }
        ]
    )

    with GigaChat(
        credentials=api_key,
        model=MODEL,
        base_url=BASE_URL,
        verify_ssl_certs=False
    ) as client:
        response = client.chat.create(request)
        answer = response.messages[0].content[0].text

    return parse_json_response(answer)


def analyze_dks(uploaded_file, description=""):
    raise ValueError(
        "Файл .dks получен, но его внутренний формат пока не поддерживается автоматически."
    )


def _norm(value):
    return str(value).lower().replace("ё", "е").strip()


def check_required_parameters(parameters):
    missing = []

    if parameters.get("error"):
        return ["корректный JSON от ИИ"]

    if not parameters.get("материал"):
        missing.append("материал")

    if parameters.get("толщина_мм") is None:
        missing.append("толщина_мм")

    if parameters.get("длина_мм") is None:
        missing.append("длина_мм")

    if parameters.get("ширина_мм") is None:
        missing.append("ширина_мм")

    if parameters.get("количество") is None:
        missing.append("количество")

    operations = parameters.get("операции") or []
    if isinstance(operations, str):
        operations = [operations]

    if not operations:
        missing.append("операции")
        return missing

    hours = parameters.get("время_операций") or {}
    normalized_hours = {_norm(k): v for k, v in hours.items()}

    for operation in operations:
        op = _norm(operation)

        if op == "лазерная резка":
            if normalized_hours.get("лазерная резка") is None:
                missing.append("время лазерной резки")

        elif op == "сварка":
            if normalized_hours.get("сварка") is None:
                missing.append("время сварки")

        elif op in {"токарка", "токарная обработка"}:
            if (
                normalized_hours.get("токарка") is None
                and normalized_hours.get("токарная обработка") is None
            ):
                missing.append("время токарной обработки")

        elif op == "гибка":
            if (
                parameters.get("количество_гибов") is None
                and normalized_hours.get("гибка") is None
            ):
                missing.append("количество гибов или время гибки")

    return missing


def make_clarification_question(missing):
    questions = {
        "материал": "Укажите материал изделия.",
        "толщина_мм": "Укажите толщину металла в миллиметрах.",
        "длина_мм": "Укажите длину изделия в миллиметрах.",
        "ширина_мм": "Укажите ширину изделия в миллиметрах.",
        "количество": "Укажите количество изделий.",
        "операции": (
            "Укажите требуемые операции обработки "
            "(например: лазерная резка, гибка, сварка, покраска)."
        ),
        "время лазерной резки": (
            "Укажите время лазерной резки для одной детали "
            "в минутах или часах. Например: 30 минут или 0,5 часа."
        ),
        "время сварки": (
            "Укажите время сварки для одной детали в минутах или часах."
        ),
        "время токарной обработки": (
            "Укажите время токарной обработки для одной детали "
            "в минутах или часах."
        ),
        "количество гибов или время гибки": (
            "Укажите количество гибов для одной детали "
            "или время гибки."
        )
    }

    for parameter in missing:
        if parameter in questions:
            return questions[parameter]

    return "Уточните недостающие параметры изделия."


def update_parameters_from_user_answer(parameters, question, user_answer):
    check_api_key()

    current_parameters = json.dumps(
        parameters,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
Ты — инженер-технолог и AI-агент.

Ранее был проанализирован технический чертёж.
Сейчас пользователь отвечает на уточняющий вопрос.

Чертёж в этом запросе НЕ виден.
Работай только с текущими параметрами, вопросом и ответом.

ТЕКУЩИЕ ПАРАМЕТРЫ:
{current_parameters}

ВОПРОС:
{question}

ОТВЕТ:
{user_answer}

Верни СТРОГО JSON:

{{
    "обновления": {{}},
    "уверенность": "высокая",
    "уточнение": null
}}

Правила:
1. Извлекай только то, что пользователь реально сообщил.
2. Не придумывай значения.
3. Можно обновить несколько параметров сразу.
4. Время всегда переводи в часы:
   30 минут = 0.5;
   15 минут = 0.25;
   1 час 30 минут = 1.5.
5. Если пользователь отвечает на вопрос о лазерной резке,
   запиши время так:
   "время_операций": {{"лазерная резка": <часы>}}
6. Для сварки:
   "время_операций": {{"сварка": <часы>}}
7. Для токарной обработки:
   "время_операций": {{"токарная обработка": <часы>}}
8. Для гибки "4 гиба" означает:
   "количество_гибов": 4
9. Не превращай длину реза во время.
10. Если пользователь дал длину реза, но вопрос был о времени,
    попроси именно время.
11. Если ответ неоднозначный — не подтверждай значение молча,
    а задай уточняющий вопрос.
12. Не изменяй ранее известные параметры без причины.

Пример:
Ответ: "30 минут"

{{
    "обновления": {{
        "время_операций": {{
            "лазерная резка": 0.5
        }}
    }},
    "уверенность": "высокая",
    "уточнение": null
}}

Пример:
Ответ: "4 гиба"

{{
    "обновления": {{
        "количество_гибов": 4
    }},
    "уверенность": "высокая",
    "уточнение": null
}}

Не добавляй текст за пределами JSON.
"""

    with GigaChat(
        credentials=api_key,
        model=MODEL,
        base_url=BASE_URL,
        verify_ssl_certs=False
    ) as client:
        response = client.chat.create(prompt)
        answer = response.messages[0].content[0].text

    return parse_json_response(answer)


def analyze_cad_with_gigachat(drawing_data, description=""):
    """
    Анализ DXF/CDW/M3D через единый CAD-контекст.

    file_reader.py читает файл,
    drawing_input.py превращает результат чтения
    в понятный для AI текстовый контекст.
    """
    check_api_key()

    try:
        from drawing_input import prepare_for_analyzer, build_ai_context
    except ImportError as e:
        raise ImportError(
            "Не удалось импортировать drawing_input.py. "
            "Проверьте, что drawing_input.py находится рядом с drawing_analyzer.py."
        ) from e

    prepared = prepare_for_analyzer(drawing_data)
    ai_context = build_ai_context(prepared)

    if not ai_context.strip():
        raise ValueError(
            "Не удалось подготовить данные CAD-файла для анализа."
        )

    return analyze_text_with_gigachat(
        ai_context,
        description
    )


def analyze_drawing(uploaded_file, description=""):
    """
    Главная точка входа для анализа чертежа.

    Поддерживаем:
    - PDF
    - PNG/JPG/WEBP
    - DXF
    - CDW
    - M3D
    - DKS (пока с понятным сообщением, что формат не реализован)
    """
    check_api_key()

    filename = uploaded_file.name.lower()

    # -----------------------------
    # PDF
    # -----------------------------
    if filename.endswith(".pdf"):
        pdf_text = extract_pdf_text(uploaded_file)

        if not pdf_text.strip():
            raise ValueError("Не удалось извлечь текст из PDF.")

        return analyze_text_with_gigachat(
            pdf_text,
            description
        )

    # -----------------------------
    # Изображения
    # -----------------------------
    if filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return analyze_image_with_gigachat(
            uploaded_file,
            description
        )

    # -----------------------------
    # DXF / CDW / M3D
    # -----------------------------
    if filename.endswith((".dxf", ".cdw", ".m3d")):

        # CAD-reader работает с путём к файлу,
        # а Streamlit UploadedFile хранит файл в памяти.
        suffix = os.path.splitext(filename)[1]

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix,
                delete=False
            ) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_path = temp_file.name

            from file_reader import read_drawing_file

            drawing_data = read_drawing_file(
                temp_path,
                extract_kompas_resources=True
            )

            # Сохраняем исходное имя файла для AI-контекста.
            drawing_data["file_name"] = uploaded_file.name

            return analyze_cad_with_gigachat(
                drawing_data,
                description
            )

        finally:
            # Временный файл больше не нужен после подготовки контекста.
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    # -----------------------------
    # DKS
    # -----------------------------
    if filename.endswith(".dks"):
        return analyze_dks(
            uploaded_file,
            description
        )

    raise ValueError(
        "Неподдерживаемый формат файла. "
        "Поддерживаются: PDF, PNG, JPG, WEBP, DXF, CDW, M3D."
    )


if __name__ == "__main__":
    print("drawing_analyzer.py загружен.")


    print("Тестируем текстовый запрос GigaChat...")

    test_parameters = {
        "название": "Верхняя панель",
        "материал": "Ст3пс",
        "толщина_мм": None,
        "длина_мм": 420,
        "ширина_мм": 400,
        "количество": None,
        "операции": []
    }

    test_question = "Укажите толщину металла в миллиметрах."

    test_answer = "Лист 1,5 мм"

    try:

        result = update_parameters_from_user_answer(
            test_parameters,
            test_question,
            test_answer
        )

        print("\nОтвет GigaChat:")
        print(json.dumps(
            result,
            ensure_ascii=False,
            indent=4
        ))

    except Exception as e:

        print("\nОШИБКА:")
        print(type(e).__name__)
        print(e)