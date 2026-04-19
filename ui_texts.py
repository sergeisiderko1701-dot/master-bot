from constants import category_label, status_label


def welcome_text() -> str:
    return (
        "🔧 <b>Майстер Одеса</b>\n\n"
        "Швидкий пошук майстра по вашій проблемі.\n\n"
        "👤 <b>Клієнт</b> — створює заявку\n"
        "👷 <b>Майстер</b> — отримує заявки і надсилає пропозиції\n\n"
        "Оберіть роль нижче 👇"
    )


def menu_text() -> str:
    return (
        "🏠 <b>Головне меню</b>\n\n"
        "Оберіть потрібний розділ 👇"
    )


def support_intro() -> str:
    return (
        "🆘 <b>Підтримка</b>\n\n"
        "Напишіть повідомлення одним текстом.\n"
        "Ми передамо його адміністратору і відповімо найближчим часом."
    )


def support_sent() -> str:
    return (
        "✅ <b>Повідомлення надіслано</b>\n\n"
        "Дякуємо. Адміністратор отримає його найближчим часом."
    )


def order_created_text() -> str:
    return (
        "✅ <b>Заявку створено</b>\n\n"
        "Ми вже показуємо її майстрам у вашій категорії.\n"
        "Щойно хтось відгукнеться — ви побачите пропозицію тут у боті."
    )


def choose_category_text() -> str:
    return (
        "🔧 <b>Оберіть спеціальність майстра</b>\n\n"
        "Це потрібно, щоб:\n"
        "• показати вам відповідних майстрів\n"
        "• надіслати заявку тільки в потрібну категорію\n\n"
        "Оберіть спеціальність нижче 👇"
    )


def client_actions_text(category: str) -> str:
    return (
        f"📌 <b>Обрана спеціальність:</b> {category_label(category)}\n\n"
        "Що хочете зробити далі?"
    )


def ask_district_text() -> str:
    return (
        "📍 <b>Район або адреса</b>\n\n"
        "Напишіть, де саме потрібна допомога."
    )


def ask_problem_text() -> str:
    return (
        "📝 <b>Опишіть проблему</b>\n\n"
        "1–3 речення буде достатньо.\n"
        "Наприклад:\n"
        "• протікає труба під раковиною\n"
        "• не працює розетка на кухні"
    )


def ask_media_text() -> str:
    return (
        "📷 <b>Фото або відео</b>\n\n"
        "Надішліть фото/відео проблеми або напишіть <b>пропустити</b>."
    )


def master_profile_text(master_row) -> str:
    availability = "онлайн" if master_row["availability"] == "online" else "офлайн"
    status_text = "підтверджений" if master_row["status"] == "approved" else master_row["status"]

    return (
        "👷 <b>Профіль майстра</b>\n\n"
        f"👤 <b>{master_row['name']}</b>\n"
        f"🔧 {category_label(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Про себе</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {float(master_row['rating']):.2f}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"✅ <b>Статус профілю:</b> {status_text}\n"
        f"🟢 <b>Доступність:</b> {availability}"
    )


def order_card_text(order_row, title: str, master_name: str) -> str:
    return (
        f"{title}\n\n"
        f"🆔 <b>Заявка #{order_row['id']}</b>\n"
        f"🔧 <b>{category_label(order_row['category'])}</b>\n"
        f"📍 {order_row['district'] or '—'}\n\n"
        f"📝 <b>Проблема</b>\n{order_row['problem']}\n\n"
        f"📌 <b>Статус:</b> {status_label(order_row['status'])}\n"
        f"👷 <b>Майстер:</b> {master_name or '—'}\n"
        f"⭐ <b>Оцінка:</b> {order_row['rating'] if order_row['rating'] is not None else '—'}"
    )


def master_card_text(master_row, title: str) -> str:
    availability = "онлайн" if master_row["availability"] == "online" else "офлайн"
    approved_badge = "✅ Перевірений майстер" if master_row["status"] == "approved" else master_row["status"]

    return (
        f"{title}\n\n"
        f"👤 <b>{master_row['name']}</b>\n"
        f"🔧 {category_label(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Опис</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {float(master_row['rating']):.2f}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"✅ <b>Статус:</b> {approved_badge}\n"
        f"🟢 <b>Доступність:</b> {availability}"
    )


def offer_card_text(offer) -> str:
    return (
        "💼 <b>Пропозиція майстра</b>\n\n"
        f"👷 <b>{offer['name']}</b>\n"
        f"⭐ Рейтинг: {float(offer['rating']):.2f} ({offer['reviews_count']} відгуків)\n"
        f"💰 Ціна: <b>{offer['price']}</b>\n"
        f"⏱ Коли зможе: <b>{offer['eta']}</b>\n\n"
        f"📝 Коментар:\n{offer['comment'] or 'Без коментаря'}"
    )


def client_master_selected_text(master_name: str, phone: str, rating=None, reviews_count=None, eta: str = None) -> str:
    rating_line = f"⭐ <b>Рейтинг:</b> {float(rating):.2f}\n" if rating is not None else ""
    reviews_line = f"💬 <b>Відгуків:</b> {reviews_count}\n" if reviews_count is not None else ""
    eta_line = f"⏱ <b>Коли зможе:</b> {eta}\n" if eta else ""

    return (
        "🎉 <b>Ви обрали майстра</b>\n\n"
        "Ми відкрили контакти для зв'язку.\n\n"
        f"👷 <b>Майстер:</b> {master_name}\n"
        f"📞 <b>Телефон:</b> {phone or '—'}\n"
        f"{rating_line}"
        f"{reviews_line}"
        f"{eta_line}\n"
        "Тепер ви можете:\n"
        "• домовитись про час і деталі\n"
        "• написати майстру через бот\n"
        "• зателефонувати напряму\n\n"
        "Якщо все пройде добре — після виконання роботи завершіть заявку та залиште оцінку.\n"
        "Якщо виникне проблема — скористайтесь кнопкою скарги."
    )


def master_selected_for_master_text(order_id: int) -> str:
    return (
        f"🎉 <b>Вашу пропозицію обрано по заявці #{order_id}</b>\n\n"
        "Контакти клієнта вже відкрито.\n\n"
        "Тепер ви можете:\n"
        "• зв'язатися з клієнтом напряму\n"
        "• написати через бот\n"
        "• після виконання натиснути <b>Завершити заявку</b>"
    )


def chat_open_text(order_id: int, is_client: bool) -> str:
    other = "майстру 👷" if is_client else "клієнту 👤"
    return (
        f"✉️ <b>Повідомлення по заявці #{order_id}</b>\n\n"
        f"Напишіть одне повідомлення {other}.\n"
        "Можна надіслати текст, фото або відео.\n\n"
        "Після відправки режим автоматично закриється."
    )


def chat_text_message(order_id: int, sender_role: str, text: str) -> str:
    sender = "👤 <b>Клієнт</b>" if sender_role == "client" else "👷 <b>Майстер</b>"
    return (
        f"✉️ <b>Повідомлення по заявці #{order_id}</b>\n\n"
        f"{sender}:\n{text}"
    )


def chat_media_caption(order_id: int, sender_role: str, caption: str, icon: str) -> str:
    sender = "👤 <b>Клієнт</b>" if sender_role == "client" else "👷 <b>Майстер</b>"
    return (
        f"{icon} <b>Повідомлення по заявці #{order_id}</b>\n\n"
        f"{sender}:\n{caption or 'Без підпису'}"
    )
