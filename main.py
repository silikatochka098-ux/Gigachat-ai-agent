import os
from dotenv import load_dotenv
from gigachat import GigaChat

load_dotenv()

api_key = os.getenv("GIGACHAT_API_KEY")

if not api_key or not api_key.strip():
    print("❌ Ошибка: GIGACHAT_API_KEY не найден в .env")
    exit(1)

print("🚀 GigaChat AI-помощник запущен!")
print("Введите 'exit' для завершения.\n")

try:
    with GigaChat(
        credentials=api_key,
        model="GigaChat-2-Max",
        base_url="https://api.giga.chat/v1",
        verify_ssl_certs=False
    ) as client:

        while True:
            user_message = input("Вы: ")

            if user_message.lower() == "exit":
                print("👋 До свидания!")
                break

            if not user_message.strip():
                continue

            print("🤖 Думаю...")

            response = client.chat.create(user_message)

            print("GigaChat:", response.messages[0].content[0].text)
            print()

except Exception as e:
    print("\n❌ Ошибка GigaChat:")
    print(type(e).__name__)
    print(e)
    