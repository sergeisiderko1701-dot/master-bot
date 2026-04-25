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
    DISTRICT_ALL_ODESSA,
    ODESSA_DISTRICTS,
)


def back_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def skip_photo_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➡️ Пропустити фото"))
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def skip_comment_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➡️ Пропустити коментар"))
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def skip_review_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➡️ Пропустити відгук"))
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def skip_verification_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➡️ Пропустити перевірку"))
    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def main_menu_kb(is_admin_user: bool = False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👤 Знайти майстра"), KeyboardButton("🔧 Я майстер"))
    kb.row(KeyboardButton("ℹ️ Як це працює"), KeyboardButton("🆘 Підтримка"))
    if is_admin_user:
        kb.row(KeyboardButton("👑 Адмін"))
    return kb


def categories_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # 2 стовпчики × 3 рядки.
    # Важливо: ці назви мають збігатися з labels у constants.CATEGORIES.
    category_labels = [
        "🔧 Сантехнік",
        "⚡ Електрик",
        "🔨 Майстер на годину",
        "❄️ Кондиціонери",
        "🔌 Ремонт техніки",
        "🪟 Вікна / двері",
    ]

    available_labels = {label for label, _value in CATEGORIES}
    visible_labels = [label for label in category_labels if label in available_labels]

    for i in range(0, len(visible_labels), 2):
        row = visible_labels[i:i + 2]
        kb.row(*(KeyboardButton(label) for label in row))

    kb.row(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def client_actions_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📝 Створити заявку"))
    kb.row(KeyboardButton("👷 Майстри поруч"), KeyboardButton("📦 Мої заявки"))
    kb.row(KeyboardButton("🔧 Змінити послугу"), KeyboardButton("🏠 У меню"))
    return kb


def master_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🔔 Нові заявки"), KeyboardButton("📌 Мої роботи"))
    kb.row(KeyboardButton("👤 Профіль"), KeyboardButton("✏️ Редагувати"))
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
    kb.add(InlineKeyboardButton("👁 Профіль майстра", callback_data=f"offer_master_profile_{offer_id}"))
    return kb


def master_profile_from_offer_inline(offer_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Обрати цього майстра", callback_data=f"choose_offer_{offer_id}"))
    kb.add(InlineKeyboardButton("⬅️ До пропозиції", callback_data=f"offer_back_{offer_id}"))
    return kb


def nearby_master_actions_inline(master_user_id: int, category: str):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👁 Профіль", callback_data=f"nearby_master_profile_{master_user_id}"))
    kb.add(InlineKeyboardButton("📝 Створити заявку", callback_data=f"nearby_create_order_{category}"))
    return kb


def nearby_master_profile_inline(category: str):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📝 Створити заявку", callback_data=f"nearby_create_order_{category}"))
    kb.add(InlineKeyboardButton("⬅️ До списку майстрів", callback_data=f"nearby_masters_{category}"))
    return kb


def client_order_actions_inline(order_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=1)

    if status == "offered":
        kb.add(InlineKeyboardButton("🔥 Переглянути пропозиції", callback_data=f"client_offers_{order_id}"))

    if status in CHAT_AVAILABLE_STATUSES:
        kb.add(InlineKeyboardButton("💬 Написати майстру", callback_data=f"client_chat_{order_id}"))
        kb.add(InlineKeyboardButton("🔄 Обрати іншого", callback_data=f"reopen_order_{order_id}"))
        kb.add(InlineKeyboardButton("⚠️ Поскаржитись", callback_data=f"complain_master_{order_id}"))

    if status in CANCELLABLE_STATUSES:
        kb.add(InlineKeyboardButton("❌ Скасувати заявку", callback_data=f"client_cancel_{order_id}"))

    if status in CLOSED_ORDER_STATUSES:
        kb.add(InlineKeyboardButton("📜 Історія", callback_data=f"chat_history_{order_id}"))

    return kb


def order_card_master_actions(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📨 Відгукнутись", callback_data=f"offer_start_{order_id}"))
    return kb


def selected_order_master_actions(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💬 Написати клієнту", callback_data=f"master_chat_open_{order_id}"))
    kb.add(InlineKeyboardButton("📜 Історія", callback_data=f"chat_history_{order_id}"))
    kb.add(InlineKeyboardButton("🏁 Роботу виконано", callback_data=f"finish_order_{order_id}"))
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
        InlineKeyboardButton("📍 Райони", callback_data="edit_district"),
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


def master_districts_inline_kb(selected_values):
    selected = set(selected_values or [])
    kb = InlineKeyboardMarkup(row_width=2)

    for district in ODESSA_DISTRICTS:
        mark = "✅ " if district in selected else ""
        kb.insert(
            InlineKeyboardButton(
                f"{mark}{district}",
                callback_data=f"master_dist_toggle_{district}",
            )
        )

    kb.add(InlineKeyboardButton("✅ Готово", callback_data="master_dist_done"))
    return kb



def client_districts_inline_kb():
    kb = InlineKeyboardMarkup(row_width=2)

    for district in ODESSA_DISTRICTS:
        kb.insert(
            InlineKeyboardButton(
                district,
                callback_data=f"client_district_{district}",
            )
        )

    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="client_district_back"))
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
    kb.add(InlineKeyboardButton("📜 Історія", callback_data=f"chat_history_{order_id}"))

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


def confirm_choose_offer_inline(offer_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Так, обрати майстра", callback_data=f"choose_offer_confirm_{offer_id}"))
    kb.add(InlineKeyboardButton("⬅️ Повернутись до пропозицій", callback_data="confirm_action_cancel"))
    return kb


def confirm_client_cancel_inline(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Так, скасувати заявку", callback_data=f"client_cancel_confirm_{order_id}"))
    kb.add(InlineKeyboardButton("⬅️ Не скасовувати", callback_data="confirm_action_cancel"))
    return kb


def confirm_finish_order_inline(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Так, завершити заявку", callback_data=f"finish_order_confirm_{order_id}"))
    kb.add(InlineKeyboardButton("⬅️ Не завершувати", callback_data="confirm_action_cancel"))
    return kb


def confirm_refuse_order_inline(order_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Так, відмовитись", callback_data=f"refuse_order_confirm_{order_id}"))
    kb.add(InlineKeyboardButton("⬅️ Не відмовлятись", callback_data="confirm_action_cancel"))
    return kb


def confirm_order_submit_inline():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Відправити заявку", callback_data="client_order_submit_confirm"))
    kb.add(InlineKeyboardButton("✏️ Заповнити заново", callback_data="client_order_submit_edit"))
    kb.add(InlineKeyboardButton("❌ Скасувати", callback_data="client_order_submit_cancel"))
    return kb
