from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from constants import (
    CATEGORIES,
    CATEGORY_LABEL_TO_VALUE,
    CLOSED_ORDER_STATUSES,
    CHAT_AVAILABLE_STATUSES,
    CANCELLABLE_STATUSES,
)


# =========================
# BASE HELPERS
# =========================

def _reply_kb(rows):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        kb.row(*[KeyboardButton(text) for text in row])
    return kb


def _inline_kb(rows):
    kb = InlineKeyboardMarkup()
    for row in rows:
        kb.row(*row)
    return kb


# =========================
# MAIN MENUS
# =========================

def main_menu_kb(is_admin_user: bool = False):
    rows = [
        ["📦 Створити заявку"],
        ["📋 Мої заявки"],
        ["👷 Я майстер"],
        ["🆘 Допомога"],
    ]

    if is_admin_user:
        rows.append(["🛠 Адмін-панель"])

    return _reply_kb(rows)


def back_menu_kb():
    return _reply_kb([
        ["⬅️ Назад"],
    ])


def categories_kb():
    rows = [[label] for label, _ in CATEGORIES]
    rows.append(["⬅️ Назад"])
    return _reply_kb(rows)


def client_actions_kb():
    return _reply_kb([
        ["📦 Створити заявку"],
        ["📋 Мої заявки"],
        ["⬅️ Назад"],
    ])


def master_menu_kb():
    return _reply_kb([
        ["🆕 Нові заявки"],
        ["📋 Активні заявки"],
        ["👤 Мій профіль"],
        ["⬅️ Назад"],
    ])


def admin_menu_kb():
    return _reply_kb([
        ["📊 Статистика"],
        ["📋 Всі заявки"],
        ["👷 Майстри"],
        ["⬅️ Назад"],
    ])


# =========================
# PROFILE
# =========================

def edit_profile_inline_kb():
    return _inline_kb([
        [InlineKeyboardButton("Імʼя", callback_data="edit_name")],
        [InlineKeyboardButton("Район", callback_data="edit_district")],
        [InlineKeyboardButton("Телефон", callback_data="edit_phone")],
        [InlineKeyboardButton("Опис", callback_data="edit_description")],
        [InlineKeyboardButton("Досвід", callback_data="edit_experience")],
        [InlineKeyboardButton("Фото", callback_data="edit_photo")],
    ])


# =========================
# ORDER CARDS (MASTER)
# =========================

def order_card_master_actions(order_id: int):
    return _inline_kb([
        [InlineKeyboardButton("📩 Відгукнутись", callback_data=f"offer_{order_id}")],
    ])


def selected_order_master_actions(order_id: int):
    return _inline_kb([
        [InlineKeyboardButton("💬 Написати клієнту", callback_data=f"master_chat_open_{order_id}")],
        [InlineKeyboardButton("✅ Завершити", callback_data=f"finish_order_{order_id}")],
        [InlineKeyboardButton("❌ Відмовитись", callback_data=f"refuse_order_{order_id}")],
    ])


# =========================
# ORDER CARDS (CLIENT)
# =========================

def client_order_actions_inline(order_id: int, status: str):
    buttons = []

    if status in CHAT_AVAILABLE_STATUSES:
        buttons.append([
            InlineKeyboardButton("💬 Написати майстру", callback_data=f"client_chat_{order_id}")
        ])

    if status not in CLOSED_ORDER_STATUSES:
        buttons.append([
            InlineKeyboardButton("📄 Пропозиції", callback_data=f"offers_{order_id}")
        ])

    if status in CANCELLABLE_STATUSES:
        buttons.append([
            InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel_order_{order_id}")
        ])

    return _inline_kb(buttons)


def offer_select_inline(order_id: int, offer_id: int):
    return _inline_kb([
        [InlineKeyboardButton("✅ Обрати майстра", callback_data=f"choose_offer_{offer_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"offers_{order_id}")],
    ])


# =========================
# CHAT
# =========================

def chat_reply_kb():
    return _reply_kb([
        ["📜 Історія"],
        ["❌ Закрити"],
    ])


def exit_chat_inline():
    return _inline_kb([
        [InlineKeyboardButton("❌ Вийти з діалогу", callback_data="exit_chat")],
    ])


def pagination_inline(prefix: str, page: int, has_prev: bool, has_next: bool):
    buttons = []

    if has_prev:
        buttons.append(InlineKeyboardButton("⬅️", callback_data=f"{prefix}_{page - 1}"))

    buttons.append(InlineKeyboardButton(f"{page + 1}", callback_data="noop"))

    if has_next:
        buttons.append(InlineKeyboardButton("➡️", callback_data=f"{prefix}_{page + 1}"))

    return _inline_kb([buttons])


# =========================
# SUPPORT
# =========================

def support_reply_inline(user_id: int):
    return _inline_kb([
        [InlineKeyboardButton("✉️ Відповісти", callback_data=f"support_reply_{user_id}")]
    ])


# =========================
# RATING
# =========================

def rating_inline(order_id: int):
    return _inline_kb([
        [
            InlineKeyboardButton("⭐1", callback_data=f"rate_{order_id}_1"),
            InlineKeyboardButton("⭐2", callback_data=f"rate_{order_id}_2"),
            InlineKeyboardButton("⭐3", callback_data=f"rate_{order_id}_3"),
            InlineKeyboardButton("⭐4", callback_data=f"rate_{order_id}_4"),
            InlineKeyboardButton("⭐5", callback_data=f"rate_{order_id}_5"),
        ]
    ])
