# =========================
# BASE TEXTS
# =========================

def welcome_text() -> str:
    return (
        "👋 <b>Вітаємо у сервісі пошуку майстрів</b>\n\n"
        "Створіть заявку і отримайте пропозиції від перевірених спеціалістів.\n\n"
        "👇 Оберіть дію в меню"
    )


def menu_text() -> str:
    return (
        "🏠 <b>Головне меню</b>\n\n"
        "Що хочете зробити?"
    )


def support_intro() -> str:
    return (
        "🆘 <b>Підтримка</b>\n\n"
        "Опишіть вашу проблему або питання.\n"
        "Ми відповімо якнайшвидше."
    )


def support_sent() -> str:
    return (
        "✅ <b>Повідомлення надіслано</b>\n\n"
        "Адміністратор відповість вам найближчим часом."
    )


# =========================
# CLIENT TIPS
# =========================

def tip_after_category() -> str:
    return (
        "💡 <b>Порада</b>\n\n"
        "Опишіть проблему максимально конкретно:\n"
        "• що саме не працює\n"
        "• коли це почалося\n"
        "• чи були спроби ремонту\n\n"
        "Чим детальніше опис — тим швидше майстри відгукнуться."
    )


def tip_before_submit() -> str:
    return (
        "💡 <b>Порада</b>\n\n"
        "Додайте фото або відео проблеми — це допоможе майстрам "
        "дати точнішу ціну одразу."
    )


def tip_choose_master() -> str:
    return (
        "💡 <b>Як обрати майстра</b>\n\n"
        "Зверніть увагу:\n"
        "• 🟢 онлайн — швидше відповість\n"
        "• ⭐ рейтинг і відгуки\n"
        "• ⏱ коли може приїхати\n\n"
        "Не обовʼязково обирати найдешевший варіант 😉"
    )


def tip_after_choose_master() -> str:
    return (
        "💡 <b>Що далі?</b>\n\n"
        "• Напишіть майстру або зателефонуйте\n"
        "• Уточніть деталі роботи\n"
        "• Домовтесь про час\n\n"
        "Контакти вже відкриті 👇"
    )


def tip_no_response() -> str:
    return (
        "💡 <b>Немає відповіді?</b>\n\n"
        "Спробуйте:\n"
        "• написати ще раз\n"
        "• зателефонувати\n"
        "• або обрати іншого майстра"
    )


# =========================
# MASTER TIPS
# =========================

def tip_master_offer() -> str:
    return (
        "💡 <b>Порада</b>\n\n"
        "Чим точніше пропозиція:\n"
        "• конкретна ціна\n"
        "• реальний час прибуття\n"
        "• короткий коментар\n\n"
        "тим вищий шанс, що вас оберуть."
    )


def tip_master_selected() -> str:
    return (
        "💡 <b>Важливо</b>\n\n"
        "Клієнт вже обрав вас 👇\n\n"
        "• швидко звʼяжіться\n"
        "• підтвердіть час\n"
        "• не затягуйте відповідь\n\n"
        "Це впливає на ваш рейтинг ⭐"
    )


# =========================
# CHAT TEXTS
# =========================

def chat_open_text(order_id: int, is_client: bool) -> str:
    if is_client:
        return (
            f"💬 <b>Чат по заявці #{order_id}</b>\n\n"
            "Напишіть повідомлення майстру.\n\n"
            "💡 Уточніть адресу, час і деталі проблеми."
        )
    return (
        f"💬 <b>Чат по заявці #{order_id}</b>\n\n"
        "Напишіть повідомлення клієнту.\n\n"
        "💡 Узгодьте деталі і час приїзду."
    )


def chat_text_message(order_id: int, role: str, text: str) -> str:
    prefix = "👤 Клієнт" if role == "client" else "👷 Майстер"
    return f"💬 <b>Заявка #{order_id}</b>\n{prefix}:\n{text}"


def chat_media_caption(order_id: int, role: str, caption: str, icon: str) -> str:
    prefix = "👤 Клієнт" if role == "client" else "👷 Майстер"
    base = f"{icon} <b>Заявка #{order_id}</b>\n{prefix}"
    return f"{base}\n{caption}" if caption else base


# =========================
# OFFERS
# =========================

def offer_card_text(offer) -> str:
    online = "🟢 Онлайн" if offer.get("availability") == "online" else "⚪ Офлайн"

    rating = offer.get("rating") or 0
    reviews = offer.get("reviews_count") or 0

    return (
        f"👷 <b>{offer.get('name', 'Майстер')}</b>\n"
        f"{online}\n"
        f"⭐ {round(rating, 1)} ({reviews})\n\n"
        f"💰 Ціна: {offer.get('price', '—')}\n"
        f"⏱ Час: {offer.get('eta', '—')}\n\n"
        f"💬 {offer.get('comment', 'Без коментаря')}"
    )


# =========================
# CONTACTS
# =========================

def client_master_selected_text(master_name, phone, rating, reviews_count, eta) -> str:
    return (
        f"✅ <b>Ви обрали майстра</b>\n\n"
        f"👷 {master_name}\n"
        f"📞 {phone}\n"
        f"⭐ {round(rating or 0, 1)} ({reviews_count or 0})\n"
        f"⏱ {eta}\n\n"
        f"{tip_after_choose_master()}"
    )


def master_selected_for_master_text(order_id: int) -> str:
    return (
        f"🎉 <b>Вас обрали по заявці #{order_id}</b>\n\n"
        f"{tip_master_selected()}"
    )


# =========================
# RATING
# =========================

def rating_intro(order_id: int) -> str:
    return (
        f"⭐ <b>Оцінка заявки #{order_id}</b>\n\n"
        "Будь ласка, оцініть майстра від 1 до 5."
    )


def rating_thanks() -> str:
    return (
        "✅ <b>Дякуємо за оцінку</b>\n\n"
        "Ваш відгук допомагає іншим користувачам."
    )
