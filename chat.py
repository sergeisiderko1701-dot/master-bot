"""
chat.py

Цей модуль навмисно відключений.

Актуальна логіка чату тепер знаходиться в offers.py:
- client_chat_{order_id}
- master_chat_open_{order_id}
- chat_history_{order_id}
- ChatFlow.message
- create_chat_message(...)
- get_chat_for_order(...)

Файл залишено як безпечну заглушку, щоб:
1) не було конфлікту старого й нового чату;
2) не падали імпорти, якщо десь ще лишилося import chat;
3) можна було спокійно видалити модуль пізніше.
"""


def register(dp):
    # Старий chat-модуль відключений.
    # Нічого не реєструємо навмисно.
    return
