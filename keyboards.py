from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from constants import CATEGORIES


CLOSED_ORDER_STATUSES = {"done", "cancelled", "expired"}
ACTIVE_CHAT_ORDER_STATUSES = {"matched", "in_progress"}
CANCELLABLE_ORDER_STATUSES = {"new", "offered", "matched"}


def _reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(resize_keyboard=True)


def _inline_kb(row_width: int = 1) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(row_width=row_width)


# =========================
# MAIN MENUS
# =========================

def main_menu_kb(is_admin_user: bool = False):
    kb = _reply_kb()
    kb.add(KeyboardButton("👤 Клієнт"), KeyboardButton("🔧 Майстер"))
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
    for label, _ in CATEGORIES:
        kb.add(KeyboardButton(label))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def client_actions_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📨 Створити заявку"))
    kb.add(KeyboardButton("👷 Переглянути майстрів"))
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


# =========================
# ADMIN
# =========================

def admin_menu_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("👷 База майстрів"))
    kb.add(KeyboardButton("📝 Заявки майстрів"))
    kb.add(KeyboardButton("📦 Заявки клієнтів"))
    kb.add(KeyboardButton("📊 Статистика"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


# =========================
# MASTER REGISTRATION
# =========================

def master_categories_inline_kb():
    kb = _inline_kb(row_width=1)
    for label, value in CATEGORIES:
        kb.add(InlineKeyboardButton(label, callback_data=f"master_cat_{value}"))
    return kb


def edit_profile_inline_kb():
    kb = _inline_kb(row_width=1)
    kb.add(
        InlineKeyboardButton("👤 Ім'я", callback_data="edit_name"),
        InlineKeyboardButton("📍 Район", callback_data="edit_district"),
        InlineKeyboardButton("📞 Телефон", callback_data="edit_phone"),
        InlineKeyboardButton("🧾 Опис", callback_data="edit_description"),
        InlineKeyboardButton("🛠 Досвід", callback_data="edit_experience"),
        InlineKeyboardButton("📸 Фото", callback_data="edit_photo"),
    )
    return kb


# =========================
# ORDERS
# =========================

def order_card_master_actions(order_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("📨 Відгукнутись", callback_data=f"offer_start_{order_id}"))
    return kb


def offer_select_inline(offer_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("✅ Обрати цього майстра", callback_data=f"choose_offer_{offer_id}"))
    return kb


# =========================
# CLIENT ORDER ACTIONS (НОВИЙ UX)
# =========================

def client_order_actions_inline(order_id: int, status: str):
    kb = _inline_kb(row_width=1)

    if status not in CLOSED_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("📬 Пропозиції майстрів", callback_data=f"client_offers_{order_id}"))

    if status in ACTIVE_CHAT_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("✉️ Написати майстру", callback_data=f"client_chat_{order_id}"))
        kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))
        kb.add(InlineKeyboardButton("⚠️ Скарга на майстра", callback_data=f"complain_master_{order_id}"))

    if status in CANCELLABLE_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("❌ Скасувати заявку", callback_data=f"client_cancel_{order_id}"))

    return kb


# =========================
# MASTER ACTIVE ORDER ACTIONS (НОВИЙ UX)
# =========================

def selected_order_master_actions(order_id: int):
    kb = _inline_kb(row_width=1)
    kb.add(
        InlineKeyboardButton("✉️ Написати клієнту", callback_data=f"master_chat_open_{order_id}"),
        InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"),
        InlineKeyboardButton("🏁 Завершити заявку", callback_data=f"finish_order_{order_id}"),
        InlineKeyboardButton("❌ Відмовитись", callback_data=f"refuse_order_{order_id}"),
        InlineKeyboardButton("⚠️ Скарга на клієнта", callback_data=f"complain_client_{order_id}"),
    )
    return kb


# =========================
# SUPPORT / CHAT
# =========================

def exit_chat_inline():
    kb = _inline_kb(row_width=1)
    kb.add(InlineKeyboardButton("❌ Закрити", callback_data="exit_chat"))
    return kb


def chat_reply_kb():
    kb = _reply_kb()
    kb.add(KeyboardButton("📜 Історія"), KeyboardButton("❌ Закрити"))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb
