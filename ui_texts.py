from constants import category_label, status_label


def welcome_text() -> str:
    return (
        "🔧 <b>Сервіс майстрів</b>\n\n"
        "Швидко створіть заявку або увійдіть як майстер.\n\n"
        "Оберіть роль нижче 👇"
    )


def menu_text() -> str:
    return "🏠 <b>Головне меню</b>\n\nОберіть потрібний розділ 👇"


def support_intro() -> str:
    return (
        "🆘 <b>Підтримка</b>\n\n"
        "Напишіть повідомлення одним текстом — ми передамо його адміністратору."
    )


def support_sent() -> str:
    return "✅ <b>Повідомлення надіслано</b>\n\nАдміністратор отримає його найближчим часом."


def order_created_text() -> str:
    return "✅ <b>Заявку створено</b>\n\nМайстри вже отримали сповіщення 🔔"


def choose_category_text() -> str:
    return "🔧 <b>Оберіть спеціальність</b>\n\nПокажемо майстрів і заявки саме в цій категорії."


def client_actions_text(category: str) -> str:
    return f"📌 <b>Категорія:</b> {category_label(category)}\n\nЩо хочете зробити далі?"


def ask_district_text() -> str:
    return "📍 <b>Район або адреса</b>\n\nНапишіть, де потрібна допомога."


def ask_problem_text() -> str:
    return (
        "📝 <b>Опишіть проблему</b>\n\n"
        "1–2 речення буде достатньо.\n"
        "Наприклад: протікає труба під раковиною."
    )


def ask_media_text() -> str:
    return (
        "📷 <b>Фото або відео</b>\n\n"
        "Надішліть фото/відео проблеми або напишіть <b>пропустити</b>."
    )


def master_profile_text(master_row) -> str:
    availability = "онлайн" if master_row["availability"] == "online" else "офлайн"
    return (
        "👷 <b>Профіль майстра</b>\n\n"
        f"👤 <b>{master_row['name'] or '—'}</b>\n"
        f"🔧 {category_label(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Про себе</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {float(master_row['rating']):.2f}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"📌 <b>Статус:</b> {status_label(master_row['status'])}\n"
        f"🟢 <b>Доступність:</b> {availability}"
    )


def order_card_text(order_row, title: str, master_name: str) -> str:
    return (
        f"{title}\n\n"
        f"🔧 <b>{category_label(order_row['category'])}</b>\n"
        f"📍 {order_row['district'] or '—'}\n\n"
        f"📝 <b>Проблема</b>\n{order_row['problem'] or '—'}\n\n"
        f"📌 <b>Статус:</b> {status_label(order_row['status'])}\n"
        f"👷 <b>Майстер:</b> {master_name or '—'}\n"
        f"⭐ <b>Оцінка:</b> {order_row['rating'] if order_row['rating'] is not None else '—'}"
    )


def master_card_text(master_row, title: str) -> str:
    availability = "онлайн" if master_row["availability"] == "online" else "офлайн"
    return (
        f"{title}\n\n"
        f"👤 <b>{master_row['name'] or '—'}</b>\n"
        f"🔧 {category_label(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Опис</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {float(master_row['rating']):.2f}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"📌 <b>Статус:</b> {status_label(master_row['status'])}\n"
        f"🟢 <b>Доступність:</b> {availability}"
    )


def offer_card_text(offer) -> str:
    return (
        f"💼 <b>Пропозиція майстра</b>\n\n"
        f"👤 <b>{offer['name'] or '—'}</b>\n"
        f"⭐ {float(offer['rating']):.2f} · {offer['reviews_count']} відгуків\n"
        f"💰 <b>Ціна:</b> {offer['price'] or '—'}\n"
        f"⏱ <b>Коли зможе:</b> {offer['eta'] or '—'}\n"
        f"📝 <b>Коментар:</b> {offer['comment'] or '—'}"
    )


def chat_open_text(order_id: int, is_client: bool) -> str:
    other = "майстром 👷" if is_client else "клієнтом 👤"
    return (
        f"💬 <b>Чат по заявці #{order_id}</b>\n\n"
        f"Ви спілкуєтесь з {other}.\n\n"
        f"Напишіть повідомлення або надішліть фото / відео 👇"
    )


def chat_text_message(order_id: int, sender_role: str, text: str) -> str:
    sender = "👤 <b>Клієнт</b>" if sender_role == "client" else "👷 <b>Майстер</b>"
    return f"💬 <b>Заявка #{order_id}</b>\n\n{sender}:\n{text or 'Без тексту'}"


def chat_media_caption(order_id: int, sender_role: str, caption: str, icon: str) -> str:
    sender = "👤 <b>Клієнт</b>" if sender_role == "client" else "👷 <b>Майстер</b>"
    return f"{icon} <b>Заявка #{order_id}</b>\n\n{sender}:\n{caption or 'Без підпису'}"
