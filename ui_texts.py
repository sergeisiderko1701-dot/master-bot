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
        "🔧 <b>Одеса Майстер</b>\n\n"
        "Швидкий пошук майстра в Одесі.\n\n"
        "👤 Створіть заявку\n"
        "🔧 Отримайте пропозиції\n"
        "🤝 Оберіть майстра\n\n"
        "Оберіть, як хочете продовжити:"
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


def order_sent_to_review_text(order_id: int, reasons: list[str]) -> str:
    return (
        f"🛡 <b>Заявку #{order_id} прийнято</b>\n\n"
        "Ми швидко перевіримо її перед публікацією.\n"
        "Якщо все гаразд — майстри скоро її побачать."
    )


def suspicious_order_admin_text(order_row) -> str:
    return (
        "🕵️ <b>Підозріла заявка</b>\n\n"
        f"🆔 Заявка: <b>#{order_row['id']}</b>\n"
        f"👤 Клієнт: <code>{order_row['user_id']}</code>\n"
        f"🔧 Категорія: <b>{category_label(order_row['category'])}</b>\n"
        f"📍 Район: {order_row['district'] or '—'}\n"
        f"📞 Телефон: {order_row['client_phone'] or '—'}\n\n"
        f"📝 <b>Проблема:</b>\n{order_row['problem'] or '—'}\n\n"
        f"⚠️ <b>Причини:</b>\n{order_row['suspicion_reasons'] or '—'}\n"
        f"📊 <b>Score:</b> {order_row['suspicion_score'] or 0}"
    )


def choose_category_text() -> str:
    return (
        "🔧 <b>Оберіть спеціальність майстра</b>\n\n"
        "Це потрібно, щоб показати заявку потрібним спеціалістам.\n\n"
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
        "Опишіть проблему конкретно — так майстри швидше дадуть ціну."
    )


def tip_before_submit() -> str:
    return (
        "💡 <b>Порада</b>\n\n"
        "Додайте фото або відео проблеми — це допоможе майстрам дати точнішу ціну."
    )


def tip_choose_master() -> str:
    return (
        "💡 <b>Як обрати майстра</b>\n\n"
        "Зверніть увагу на рейтинг, відгуки, ціну та час приїзду.\n"
        "Не обовʼязково обирати найдешевший варіант 😉"
    )


def tip_after_choose_master() -> str:
    return (
        "💡 <b>Що далі?</b>\n\n"
        "Напишіть майстру або зателефонуйте, щоб узгодити час і деталі."
    )


def tip_no_response() -> str:
    return (
        "💡 <b>Немає відповіді?</b>\n\n"
        "Спробуйте написати ще раз, зателефонувати або обрати іншого майстра."
    )


def tip_reopen_order() -> str:
    return (
        "💡 <b>Майстер не виходить на зв'язок?</b>\n\n"
        "Можна повторно відкрити заявку й обрати іншого майстра."
    )


def tip_master_offer() -> str:
    return (
        "💡 <b>Порада</b>\n\n"
        "Вкажіть конкретну ціну, реальний час і короткий коментар — так вас частіше обирають."
    )


def tip_master_selected() -> str:
    return (
        "💡 <b>Важливо</b>\n\n"
        "Клієнт уже обрав вас. Напишіть або зателефонуйте якнайшвидше."
    )


def no_offers_yet_text(order_id: int) -> str:
    return (
        f"⏳ <b>По заявці #{order_id} поки немає пропозицій</b>\n\n"
        "🔎 Майстри вже дивляться вашу заявку.\n"
        "⏱ Зазвичай відповідають протягом <b>5–15 хв</b>.\n\n"
        "💡 Фото або точніший опис допоможуть отримати відповідь швидше."
    )


def offers_available_nudge_text(count: int | None = None) -> str:
    if count and int(count) > 0:
        return (
            f"📬 <b>Є пропозиції: {int(count)}</b>\n\n"
            "Відкрийте заявку й оберіть майстра, який підходить найкраще."
        )
    return (
        "📬 <b>Є пропозиції від майстрів</b>\n\n"
        "Відкрийте заявку й оберіть майстра, який підходить найкраще."
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
    rating_line = f"⭐ {_rating_text(rating)}" if rating is not None else ""
    reviews_line = f" ({reviews_count})" if reviews_count is not None else ""
    rating_block = f"{rating_line}{reviews_line}\n" if rating_line else ""
    eta_line = f"⏱ {eta}\n" if eta else ""

    return (
        "🎉 <b>Майстра обрано</b>\n\n"
        f"👷 <b>{master_name}</b>\n"
        f"📞 <b>{phone or '—'}</b>\n"
        f"{rating_block}"
        f"{eta_line}\n"
        "💬 Напишіть або зателефонуйте, щоб домовитись про деталі."
    )


def master_selected_for_master_text(order_id: int) -> str:
    return (
        f"🎉 <b>Вашу пропозицію обрано за заявкою #{order_id}</b>\n\n"
        "Контакти клієнта відкрито. Зв'яжіться з ним якнайшвидше."
    )


def order_reopened_text(order_id: int) -> str:
    return (
        f"🔄 <b>Заявку #{order_id} повторно відкрито</b>\n\n"
        "Попереднього майстра відключено. Тепер можна обрати іншого або дочекатися нових пропозицій."
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
