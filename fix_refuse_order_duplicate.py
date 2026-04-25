#!/usr/bin/env python3
"""
fix_refuse_order_duplicate.py

Безпечна точкова правка для Telegram-бота:
- відкриває offers.py у поточній папці;
- робить backup offers.py.bak_refuse_duplicate;
- видаляє тільки дублюючий handler:
  @dp.callback_query_handler(lambda c: c.data.startswith("refuse_order_confirm_"), state="*")
  async def refuse_order_confirm_handler(...)
- НЕ чіпає preview-handler refuse_order_;
- НЕ чіпає order_reopen_notify_fix.py.

Запуск:
    python fix_refuse_order_duplicate.py
"""

from pathlib import Path


OFFERS_FILE = Path("offers.py")
BACKUP_FILE = Path("offers.py.bak_refuse_duplicate")

START_MARKER = '@dp.callback_query_handler(lambda c: c.data.startswith("refuse_order_confirm_"), state="*")'
END_MARKER = '    @dp.callback_query_handler(lambda c: c.data.startswith("complain_master_"), state="*")'


def main() -> None:
    if not OFFERS_FILE.exists():
        raise SystemExit("❌ offers.py не знайдено. Запусти скрипт у папці з ботом.")

    text = OFFERS_FILE.read_text(encoding="utf-8")

    start = text.find(START_MARKER)
    if start == -1:
        print("✅ Дублюючий refuse_order_confirm_ handler не знайдено. Можливо, файл уже виправлений.")
        return

    end = text.find(END_MARKER, start)
    if end == -1:
        raise SystemExit(
            "❌ Не знайшов наступний handler complain_master_. "
            "Файл має іншу структуру, автоматично різати небезпечно."
        )

    block = text[start:end]

    if "async def refuse_order_confirm_handler" not in block:
        raise SystemExit(
            "❌ Знайшов START_MARKER, але не знайшов async def refuse_order_confirm_handler. "
            "Автоматично різати небезпечно."
        )

    if "await refuse_order(order_id)" not in block:
        raise SystemExit(
            "❌ Це не схоже на старий handler відмови майстра. "
            "Автоматично різати небезпечно."
        )

    if not BACKUP_FILE.exists():
        BACKUP_FILE.write_text(text, encoding="utf-8")

    new_text = text[:start].rstrip() + "\n\n" + text[end:]

    # Захист: preview-handler має залишитися.
    if 'c.data.startswith("refuse_order_") and not c.data.startswith("refuse_order_confirm_")' not in new_text:
        raise SystemExit("❌ Preview-handler refuse_order_ зник. Зміни не записані.")

    # Захист: дубль confirm-handler має зникнути.
    if "async def refuse_order_confirm_handler" in new_text:
        raise SystemExit("❌ Старий confirm-handler все ще є у файлі. Зміни не записані.")

    OFFERS_FILE.write_text(new_text, encoding="utf-8")

    print("✅ Готово: дублюючий refuse_order_confirm_ handler видалено з offers.py")
    print(f"🧷 Backup створено: {BACKUP_FILE}")


if __name__ == "__main__":
    main()
