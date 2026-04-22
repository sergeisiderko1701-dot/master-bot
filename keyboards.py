from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from constants import (
    CATEGORIES,
    CLOSED_ORDER_STATUSES,
    CHAT_AVAILABLE_STATUSES,
    CANCELLABLE_STATUSES,
    ADMIN_RESETTABLE_ORDER_STATUSES,
    ADMIN_FINISHABLE_ORDER_STATUSES,
    ADMIN_EXPIRABLE_ORDER_STATUSES,
)


def _reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True)


def _inline_kb(row_width: int = 1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(row_width=row_width)


def main_menu_kb(is_admin_user: bool = False):
    kb = _reply_kb()
    kb.add(KeyboardButton("👤 Клієнт"), KeyboardButton("🔧 Майстер"))
    kb.add(KeyboardButton("ℹ️ Як користуватись"))
    kb.add(KeyboardButton("🆘 Допомога"))
    if is_admin_user:
        kb.add(KeyboardButton("👑 Адмін"))
    return kb


def back_menu_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def categories_kb():
    kb = _reply_kb()

    row = []
    for i, (label, _) in enumerate(CATEGORIES, start=1):
        row.append(KeyboardButton(label))
        if i % 2 == 0:
            kb.row(*row)
            row = []

    if row:
        kb.row(*row)

    kb.row(
        KeyboardButton("⬅️ Назад"),
        KeyboardButton("🏠 У меню"),
    )
    return kb


def client_actions_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📨 Створити заявку"))
    kb.add(KeyboardButton("📦 Мої заявки"))
    kb.add(KeyboardButton("🔄 Змінити спеціальність"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def master_menu_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("👤 Мій профіль"))
    kb.add(KeyboardButton("✏️ Редагувати профіль"))
    kb.add(KeyboardButton("📦 Нові заявки"))
    kb.add(KeyboardButton("💬 Активні заявки"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def admin_menu_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📝 Модерація майстрів"))
    kb.add(KeyboardButton("👷 Майстри"))
    kb.add(KeyboardButton("📦 Заявки"))
    kb.add(KeyboardButton("⚠️ Скарги"))
    kb.add(KeyboardButton("📊 Статистика"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def admin_orders_filter_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📋 Усі заявки"))
    kb.add(KeyboardButton("🆕 Нові"), KeyboardButton("📬 Є пропозиції"))
    kb.add(KeyboardButton("🤝 Обрано майстра"), KeyboardButton("🛠 В роботі"))
    kb.add(KeyboardButton("✅ Завершені"), KeyboardButton("❌ Скасовані"))
    kb.add(KeyboardButton("⌛ Прострочені"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def help_role_inline_kb():
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("👤 Для клієнта", callback_data="help_client"))
    kb.add(InlineKeyboardButton("🔧 Для майстра", callback_data="help_master"))
    return kb


def master_categories_inline_kb(selected_values=None, done_callback: str = "master_cat_done"):
    selected_values = set(selected_values or [])
    kb = _inline_kb(row_width=2)

    buttons = []
    for label, value in CATEGORIES:
        prefix = "✅ " if value in selected_values else ""
        buttons.append(
            InlineKeyboardButton(
                f"{prefix}{label}",
                callback_data=f"master_cat_toggle_{value}",
            )
        )

    for i in range(0, len(buttons), 2):
        kb.row(*buttons[i:i + 2])

    kb.add(InlineKeyboardButton("✅ Готово", callback_data=done_callback))
    return kb


def edit_profile_inline_kb():
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("👤 Ім'я", callback_data="edit_name"))
    kb.add(InlineKeyboardButton("🔧 Спеціальності", callback_data="edit_category"))
    kb.add(InlineKeyboardButton("📍 Район", callback_data="edit_district"))
    kb.add(InlineKeyboardButton("📞 Телефон", callback_data="edit_phone"))
    kb.add(InlineKeyboardButton("🧾 Опис", callback_data="edit_description"))
    kb.add(InlineKeyboardButton("🛠 Досвід", callback_data="edit_experience"))
    kb.add(InlineKeyboardButton("📸 Фото", callback_data="edit_photo"))
    return kb


def order_card_master_actions(order_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("📨 Відгукнутись", callback_data=f"offer_start_{order_id}"))
    return kb


def offer_select_inline(offer_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("✅ Обрати цього майстра", callback_data=f"choose_offer_{offer_id}"))
    return kb


def client_order_actions_inline(order_id: int, status: str):
    kb = _inline_kb(row_width=1)

    if status not in CLOSED_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("📬 Пропозиції майстрів", callback_data=f"client_offers_{order_id}"))

    if status in CHAT_AVAILABLE_STATUSES:
        kb.add(InlineKeyboardButton("✉️ Написати майстру", callback_data=f"client_chat_{order_id}"))
        kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))
        kb.add(InlineKeyboardButton("⚠️ Скарга на майстра", callback_data=f"complain_master_{order_id}"))

    if status in CANCELLABLE_STATUSES:
        kb.add(InlineKeyboardButton("❌ Скасувати заявку", callback_data=f"client_cancel_{order_id}"))

    return kb


def selected_order_master_actions(order_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("✉️ Написати клієнту", callback_data=f"master_chat_open_{order_id}"))
    kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))
    kb.add(InlineKeyboardButton("🏁 Завершити заявку", callback_data=f"finish_order_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Відмовитись", callback_data=f"refuse_order_{order_id}"))
    kb.add(InlineKeyboardButton("⚠️ Скарга на клієнта", callback_data=f"complain_client_{order_id}"))
    return kb


def finish_reminder_inline(order_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("✅ Так, завершено", callback_data=f"client_finish_yes_{order_id}"))
    kb.add(InlineKeyboardButton("⏳ Ще ні", callback_data=f"client_finish_no_{order_id}"))
    return kb


def admin_master_card_inline(master_id: int, status: str):
    kb = _inline_kb(row_width=1)

    if status == "approved":
        kb.add(InlineKeyboardButton("🚫 Заблокувати", callback_data=f"admin_block_master_{master_id}"))
    elif status == "blocked":
        kb.add(InlineKeyboardButton("✅ Розблокувати", callback_data=f"admin_unblock_master_{master_id}"))

    kb.add(InlineKeyboardButton("🗑 Видалити майстра", callback_data=f"admin_delete_master_{master_id}"))
    return kb


def admin_pending_master_inline(master_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("✅ Підтвердити", callback_data=f"admin_approve_master_{master_id}"))
    kb.add(InlineKeyboardButton("❌ Відхилити", callback_data=f"admin_reject_master_{master_id}"))
    return kb


def admin_order_actions_inline(order_id: int, status: str):
    kb = _inline_kb(row_width=1)

    kb.add(InlineKeyboardButton("📄 Деталі заявки", callback_data=f"admin_order_detail_{order_id}"))
    kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))

    if status in ADMIN_EXPIRABLE_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("❌ Закрити як неактуальну", callback_data=f"admin_expire_order_{order_id}"))

    if status == "matched":
        kb.add(InlineKeyboardButton("🛠 Позначити 'в роботі'", callback_data=f"admin_progress_order_{order_id}"))

    if status in ADMIN_FINISHABLE_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("🏁 Завершити", callback_data=f"admin_done_order_{order_id}"))

    if status in ADMIN_RESETTABLE_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("🔄 Повернути в нові", callback_data=f"admin_reset_order_{order_id}"))

    return kb


def pagination_inline(prefix: str, page: int, has_prev: bool, has_next: bool):
    kb = _inline_kb(row_width=2)
    row = []

    if has_prev:
        row.append(InlineKeyboardButton("⬅️ Попередня", callback_data=f"{prefix}_{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton("Наступна ➡️", callback_data=f"{prefix}_{page+1}"))

    if row:
        kb.add(*row)
        return kb

    return None


def support_reply_inline(user_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("↩️ Відповісти", callback_data=f"support_reply_{user_id}"))
    return kb


def exit_chat_inline():
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("❌ Закрити", callback_data="exit_chat"))
    return kb


def chat_reply_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📜 Історія"), KeyboardButton("❌ Закрити"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def rating_inline(order_id: int):
    kb = _inline_kb(row_width=5)
    kb.add(
        InlineKeyboardButton("1⭐", callback_data=f"rate_{order_id}_1"),
        InlineKeyboardButton("2⭐", callback_data=f"rate_{order_id}_2"),
        InlineKeyboardButton("3⭐", callback_data=f"rate_{order_id}_3"),
        InlineKeyboardButton("4⭐", callback_data=f"rate_{order_id}_4"),
        InlineKeyboardButton("5⭐", callback_data=f"rate_{order_id}_5"),
    )
    return kb
