import json

from calculator import calculate_from_ai_parameters


# Это JSON, который в будущем будет приходить от ИИ
ai_json = """
{
    "название": "Тестовое изделие",
    "материал": "Ст3",
    "толщина_мм": 1.5,
    "длина_мм": 420,
    "ширина_мм": 400,
    "количество": 3,
    "операции": ["гибка"],
    "количество_гибов": 4
}
"""

parameters = json.loads(ai_json)

output = calculate_from_ai_parameters(
    parameters=parameters,
    template_path="excel/calculator_template.xlsx",
    output_path="КП_из_JSON.xlsx"
)

print("✅ ИИ → JSON → Excel")
print(f"📄 КП создано: {output}")