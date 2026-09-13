from pathlib import Path

from file_reader import read_drawing_file
from drawing_input import prepare_for_analyzer, build_ai_context


TEST_DIR = Path("test_files")


for file_path in TEST_DIR.iterdir():

    if not file_path.is_file():
        continue

    print("\n" + "=" * 70)
    print(f"Файл: {file_path.name}")
    print("=" * 70)

    try:
        drawing = read_drawing_file(file_path)

        print(
            f"Формат: "
            f"{drawing.get('source_type', drawing.get('format'))}"
        )

        prepared = prepare_for_analyzer(drawing)

        print("\n--- AI CONTEXT ---")
        print(build_ai_context(prepared))

        print("\n✅ Файл успешно обработан")

    except Exception as e:
        print("\n❌ Ошибка:")
        print(type(e).__name__)
        print(e)
