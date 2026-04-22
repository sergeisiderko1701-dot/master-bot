from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from constants import (
    ADMIN_EXPIRABLE_ORDER_STATUSES,
    ADMIN_FINISHABLE_ORDER_STATUSES,
    ADMIN_RESETTABLE_ORDER_STATUSES,
    CANCELLABLE_STATUSES,
    CATEGORIES,
    CHAT_AVAILABLE_STATUSES,
    CLOSED_ORDER_STATUSES,
    VALID_CATEGORIES,
)


def back_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def main_menu_kb(is_admin_user: bool = False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👤 Клієнт"), KeyboardButton("🔧 Майстер"))
    kb.row(KeyboardButton("ℹ️ Як користуватись"), KeyboardButton("🆘 Допомога"))
    if is_admin_user:
        kb.row(KeyboardButton("👑 Адмін"))
    return kb


def categories_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for label, _value in CATEGORIES:
        kb.row(KeyboardButton(label))
    kb.row(KeyboardButton("🏠 У меню"))
    return kb


def client_actions_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📨 Створити заявку"))
    kb.row(KeyboardButton("📦 Мої заявки"), KeyboardButton("🔄 Змінити спеціальність"))
    kb.row(KeyboardButton("🏠 У меню"))
    return kb


def master_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📦 Нові заявки"), KeyboardButton("💬 Активні заявки"))
    kb.row(KeyboardButton("👤 Мій профіль"), KeyboardButton("✏️ Редагувати профіль"))
    kb.row(KeyboardButton("🏠 У меню"))
    return kb


def help_role_inline_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👤 Для клієнта", callback_data="help_client"))
    kb.add(InlineKeyboardButton("🔧 Для майстра", callback_data="help_master"))
    return kb


def offer_select_inline(offer_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Обрати цього майстра", callback_data=f"choose_offer_{offer_id}"))
    return kb


def client_order_actions_inline(order_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=1)

    if status == "offered":
        kb.add(InlineKeyboardButton("📬 Пропозиції майстрів", callback_data=f"client_offers_{order_id}"))

    if status in CHAT_AVAILABLE_STATUSES:
        kb.add(InlineKeyboardButton("💬 Написати майстру", callback_data=f"client_chat_{order_id}"))
        kb.add(InlineKeyboardButton("🔄 Майстер не відповідає", callback_data=f"reopen_order_{order_id}"))
        kb.add(InlineKeyboardButton("⚠️ Поскаржитись", callback_data=f"complain_master_{order_id}"))

    if status in CANCELLABLE_STATUSES:
        kb.add(InlineKeyboardButton("❌ Скасувати заявку", callback_data=f"client_cancel_{order_id}"))

    if status in CLOSED_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))

    return kb


def order_card_master_actions(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📨 Відгукнутись", callback_data=f"offer_start_{order_id}"))
    return kb


def selected_order_master_actions(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💬 Написати клієнту", callback_data=f"master_chat_open_{order_id}"))
    kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))
    kb.add(InlineKeyboardButton("🏁 Завершити заявку", callback_data=f"finish_order_{order_id}"))
    kb.add(InlineKeyboardButton("❌ Відмовитись", callback_data=f"refuse_order_{order_id}"))
    kb.add(InlineKeyboardButton("⚠️ Поскаржитись", callback_data=f"complain_client_{order_id}"))
    return kb


def exit_chat_inline():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("❌ Закрити", callback_data="exit_chat"))
    return kb


def chat_reply_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📜 Історія"))
    kb.row(KeyboardButton("❌ Закрити"))
    return kb


def rating_inline(order_id: int):
    kb = InlineKeyboardMarkup(row_width=5)
    kb.row(
        InlineKeyboardButton("1", callback_data=f"rate_{order_id}_1"),
        InlineKeyboardButton("2", callback_data=f"rate_{order_id}_2"),
        InlineKeyboardButton("3", callback_data=f"rate_{order_id}_3"),
        InlineKeyboardButton("4", callback_data=f"rate_{order_id}_4"),
        InlineKeyboardButton("5", callback_data=f"rate_{order_id}_5"),
    )
    return kb


def finish_reminder_inline(order_id: int):
    return rating_inline(order_id)


def edit_profile_inline_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👤 Ім’я", callback_data="edit_name"),
        InlineKeyboardButton("🔧 Категорії", callback_data="edit_category"),
    )
    kb.add(
        InlineKeyboardButton("📍 Район", callback_data="edit_district"),
        InlineKeyboardButton("📞 Телефон", callback_data="edit_phone"),
    )
    kb.add(
        InlineKeyboardButton("🧾 Про себе", callback_data="edit_description"),
        InlineKeyboardButton("🛠 Досвід", callback_data="edit_experience"),
    )
    kb.add(InlineKeyboardButton("📸 Фото", callback_data="edit_photo"))
    return kb


def master_categories_inline_kb(selected_values):
    selected = set(selected_values or [])
    kb = InlineKeyboardMarkup(row_width=2)

    for label, value in CATEGORIES:
        mark = "✅ " if value in selected else ""
        kb.insert(
            InlineKeyboardButton(
                f"{mark}{label}",
                callback_data=f"master_cat_toggle_{value}",
            )
        )

    kb.add(InlineKeyboardButton("✅ Готово", callback_data="master_cat_done"))
    return kb


def pagination_inline(prefix: str, page: int, has_prev: bool, has_next: bool):
    kb = InlineKeyboardMarkup(row_width=2)
    row = []

    if has_prev:
        row.append(InlineKeyboardButton("⬅️ Попередня", callback_data=f"{prefix}_{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton("Наступна ➡️", callback_data=f"{prefix}_{page+1}"))

    if row:
        kb.add(*row)
        return kb

    return None


def admin_order_actions_inline(order_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📄 Деталі заявки", callback_data=f"admin_order_detail_{order_id}"))
    kb.add(InlineKeyboardButton("🧾 Історія заявки", callback_data=f"admin_order_history_{order_id}"))
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


def support_reply_inline(user_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("↩️ Відповісти", callback_data=f"support_reply_{user_id}"))
    return kb
