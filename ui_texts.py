from config import settings
from constants import category_label, category_labels, master_status_label, status_label
from utils import now_ts


def _rating_text(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _master_presence_text(master_row) -> str:
    try:
        last_seen = int(master_row.get("last_seen") or 0)
    except Exception:
        try:
            last_seen = int(master_row["last_seen"] or 0)
        except Exception:
            last_seen = 0

    if last_seen <= 0:
        return "⚫ офлайн"

    diff = now_ts() - last_seen
    timeout = int(settings.online_timeout or 300)

    if diff <= timeout:
        return "🟢 онлайн"

    if diff <= 60 * 10:
        return "🕒 був нещодавно"

    if diff <= 60 * 60:
        minutes = max(1, diff // 60)
        return f"🕒 був {minutes} хв тому"

    hours = max(1, diff // 3600)
    return f"⚫ був {hours} год тому"


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


def master_profile_text(master_row) -> str:
    status_text = master_status_label(master_row["status"])
    presence = _master_presence_text(master_row)

    return (
        "👷 <b>Профіль майстра</b>\n\n"
        f"👤 <b>{master_row['name']}</b>\n"
        f"🔧 {category_labels(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Про себе</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {_rating_text(master_row['rating'])}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"✅ <b>Статус профілю:</b> {status_text}\n"
        f"🟢 <b>Доступність:</b> {presence}"
    )


def master_card_text(master_row, title: str = "👷 <b>Картка майстра</b>") -> str:
    status_text = master_status_label(master_row["status"])
    presence = _master_presence_text(master_row)

    return (
        f"{title}\n\n"
        f"👤 <b>{master_row['name']}</b>\n"
        f"🔧 {category_labels(master_row['category'])}\n"
        f"📍 {master_row['district'] or '—'}\n"
        f"📞 {master_row['phone'] or '—'}\n\n"
        f"🧾 <b>Опис</b>\n{master_row['description'] or '—'}\n\n"
        f"🛠 <b>Досвід</b>\n{master_row['experience'] or '—'}\n\n"
        f"⭐ <b>Рейтинг:</b> {_rating_text(master_row['rating'])}\n"
        f"💬 <b>Відгуків:</b> {master_row['reviews_count']}\n"
        f"✅ <b>Статус:</b> {status_text}\n"
        f"🟢 <b>Доступність:</b> {presence}"
    )


def order_card_text(order_row, title: str, master_name: str) -> str:
    return (
        f"{title}\n\n"
        f"🆔 <b>Заявка #{order_row['id']}</b>\n"
        f"🔧 <b>{category_label(order_row['category'])}</b>\n"
        f"📍 {order_row['district'] or '—'}\n\n"
        f"📝 <b>Проблема</b>\n{order_row['problem'] or '—'}\n\n"
        f"📌 <b>Статус:</b> {status_label(order_row['status'])}\n"
        f"👷 <b>Майстер:</b> {master_name or '—'}\n"
        f"⭐ <b>Оцінка:</b> {order_row['rating'] if order_row['rating'] is not None else '—'}"
    )


def offer_card_text(offer) -> str:
    presence = _master_presence_text(offer)

    return (
        "💼 <b>Пропозиція майстра</b>\n\n"
        f"👷 <b>{offer['name']}</b>\n"
        f"{presence}\n"
        f"⭐ Рейтинг: {_rating_text(offer['rating'])} ({offer['reviews_count']} відгуків)\n"
        f"💰 Ціна: <b>{offer['price']}</b>\n"
        f"⏱ Коли зможе: <b>{offer['eta']}</b>\n\n"
        f"📝 Коментар:\n{offer['comment'] or 'Без коментаря'}"
    )


def client_master_selected_text(
    master_name: str,
    phone: str,
    rating=None,
    reviews_count=None,
    eta: str = None,
) -> str:
    rating_line = f"⭐ <b>Рейтинг:</b> {_rating_text(rating)}\n" if rating is not None else ""
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
        f"🎉 <b>Вашу пропозицію обрано за заявкою #{order_id}</b>\n\n"
        "Контакти клієнта вже відкрито.\n\n"
        "Тепер ви можете:\n"
        "• зв'язатися з клієнтом напряму\n"
        "• написати через бот\n"
        "• після виконання натиснути <b>Завершити заявку</b>"
    )


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
