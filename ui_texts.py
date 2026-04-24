from config import settings
from constants import category_label, category_labels, master_status_label, status_label
from utils import now_ts, safe_str, safe_user_text


def _rating_text(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _get(row, key, default=None):
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        try:
            value = row.get(key, default)
            return default if value is None else value
        except Exception:
            return default


def _master_presence_text(master_row) -> str:
    try:
        last_seen = int(_get(master_row, "last_seen", 0) or 0)
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


def _verification_badge(row) -> str:
    status = _get(row, "verification_status")

    if status == "verified":
        return "✅ Досвід підтверджено"
    if status == "pending":
        return "🛡 Досвід на перевірці"
    return "⚠️ Досвід не підтверджено"


def welcome_text() -> str:
    return (
        "🔧 <b>Одеса Майстер</b>\n\n"
        "Знайдіть майстра або отримуйте заявки.\n\n"
        "👇 Оберіть дію"
    )


def menu_text() -> str:
    return (
        "🏠 <b>Головне меню</b>\n\n"
        "Оберіть дію 👇"
    )


def support_intro() -> str:
    return (
        "🆘 <b>Підтримка</b>\n\n"
        "Напишіть, що сталося — допоможемо."
    )


def support_sent() -> str:
    return (
        "✅ <b>Повідомлення надіслано</b>\n\n"
        "Адміністратор відповість найближчим часом."
    )


def order_created_text() -> str:
    return (
        "🚀 <b>Заявку створено</b>\n\n"
        "Ми вже показали її майстрам.\n"
        "Перші відповіді зазвичай приходять за кілька хвилин."
    )


def order_sent_to_review_text(order_id: int, reasons: list[str]) -> str:
    return (
        f"🛡 <b>Заявку #{order_id} прийнято</b>\n\n"
        "Ми швидко перевіримо її перед публікацією.\n"
        "Після цього майстри зможуть відгукнутись."
    )


def suspicious_order_admin_text(order_row) -> str:
    return (
        "🕵️ <b>Підозріла заявка</b>\n\n"
        f"🆔 Заявка: <b>#{_get(order_row, 'id')}</b>\n"
        f"👤 Клієнт: <code>{safe_str(_get(order_row, 'user_id'))}</code>\n"
        f"🔧 Категорія: <b>{category_label(_get(order_row, 'category'))}</b>\n"
        f"📍 Район: {safe_user_text(_get(order_row, 'district'))}\n"
        f"📞 Телефон: {safe_user_text(_get(order_row, 'client_phone'))}\n\n"
        f"📝 <b>Проблема:</b>\n{safe_user_text(_get(order_row, 'problem'))}\n\n"
        f"⚠️ <b>Причини:</b>\n{safe_user_text(_get(order_row, 'suspicion_reasons'))}\n"
        f"📊 <b>Score:</b> {safe_str(_get(order_row, 'suspicion_score', 0))}"
    )


def choose_category_text() -> str:
    return (
        "🔧 <b>Що потрібно зробити?</b>\n\n"
        "Оберіть послугу — ми покажемо заявку відповідним майстрам."
    )


def client_actions_text(category: str) -> str:
    return (
        f"📌 <b>Обрано:</b> {category_label(category)}\n\n"
        "Створіть заявку — майстри запропонують ціну та час."
    )


def ask_district_text() -> str:
    return (
        "📍 <b>Де потрібна допомога?</b>\n\n"
        "Напишіть район або адресу."
    )


def ask_problem_text() -> str:
    return (
        "📝 <b>Що сталося?</b>\n\n"
        "Опишіть коротко:\n"
        "• що не працює\n"
        "• де саме\n"
        "• наскільки терміново"
    )


def ask_media_text() -> str:
    return (
        "📷 <b>Додайте фото</b>\n\n"
        "Фото допоможе майстру швидше назвати ціну.\n\n"
        "Або напишіть <b>пропустити</b>."
    )


def tip_after_category() -> str:
    return "💡 <b>Порада</b>\n\nОпишіть проблему конкретно — так майстри швидше дадуть ціну."


def tip_before_submit() -> str:
    return "💡 <b>Порада</b>\n\nДодайте фото — це допоможе майстру точніше оцінити роботу."


def tip_choose_master() -> str:
    return "🔥 <b>Є пропозиції</b>\n\nПорівняйте ціну, час і рейтинг — оберіть найкращий варіант 👇"


def tip_after_choose_master() -> str:
    return "💬 <b>Що далі?</b>\n\nНапишіть або зателефонуйте майстру, щоб домовитись про деталі."


def tip_no_response() -> str:
    return "💡 <b>Немає відповіді?</b>\n\nНапишіть ще раз або оберіть іншого майстра."


def tip_reopen_order() -> str:
    return "🔄 <b>Заявку знову відкрито</b>\n\nМожете обрати іншого майстра або дочекатись нових пропозицій."


def tip_master_offer() -> str:
    return "💡 <b>Порада</b>\n\nЧітка ціна, реальний час і короткий коментар підвищують шанс, що вас оберуть."


def tip_master_selected() -> str:
    return "🚀 <b>Вас обрали!</b>\n\nЗв’яжіться з клієнтом якнайшвидше."


def no_offers_yet_text(order_id: int) -> str:
    return (
        f"🔎 <b>Майстри дивляться заявку #{order_id}</b>\n\n"
        "Поки немає пропозицій.\n"
        "Зазвичай відповідають за <b>5–15 хв</b>.\n\n"
        "💡 Фото або точніший опис допоможуть швидше отримати відповідь."
    )


def offers_available_nudge_text(order_id_or_count: int | None = None, count: int | None = None) -> str:
    actual_count = count if count is not None else order_id_or_count

    if actual_count:
        return (
            f"🔥 <b>Є пропозиції: {actual_count}</b>\n\n"
            "Оберіть майстра, який підходить найкраще 👇"
        )
    return "🔥 <b>Є пропозиції</b>\n\nОберіть майстра, який підходить найкраще 👇"


def master_profile_text(master_row) -> str:
    status_text = master_status_label(_get(master_row, "status"))
    presence = _master_presence_text(master_row)

    return (
        "👷 <b>Ваш профіль</b>\n\n"
        f"👤 <b>{safe_user_text(_get(master_row, 'name'))}</b>\n"
        f"🔧 {category_labels(_get(master_row, 'category'))}\n"
        f"📍 {safe_user_text(_get(master_row, 'district'))}\n"
        f"📞 {safe_user_text(_get(master_row, 'phone'))}\n"
        f"{presence}\n\n"
        f"⭐ <b>{_rating_text(_get(master_row, 'rating'))}</b> · відгуків: <b>{safe_str(_get(master_row, 'reviews_count', 0))}</b>\n"
        f"✅ <b>Статус:</b> {status_text}\n"
        f"{_verification_badge(master_row)}\n\n"
        f"🧾 <b>Про себе</b>\n{safe_user_text(_get(master_row, 'description'))}\n\n"
        f"🛠 <b>Досвід</b>\n{safe_user_text(_get(master_row, 'experience'))}"
    )


def master_card_text(master_row, title: str = "👷 <b>Картка майстра</b>") -> str:
    status_text = master_status_label(_get(master_row, "status"))
    presence = _master_presence_text(master_row)

    return (
        f"{title}\n\n"
        f"👤 <b>{safe_user_text(_get(master_row, 'name'))}</b>\n"
        f"🔧 {category_labels(_get(master_row, 'category'))}\n"
        f"📍 {safe_user_text(_get(master_row, 'district'))}\n"
        f"{presence}\n\n"
        f"⭐ <b>{_rating_text(_get(master_row, 'rating'))}</b> · відгуків: <b>{safe_str(_get(master_row, 'reviews_count', 0))}</b>\n"
        f"✅ <b>Статус:</b> {status_text}\n"
        f"{_verification_badge(master_row)}\n\n"
        f"🧾 {safe_user_text(_get(master_row, 'description'))}\n\n"
        f"📞 {safe_user_text(_get(master_row, 'phone'))}"
    )


def order_card_text(order_row, title: str, master_name: str) -> str:
    return (
        f"{title}\n\n"
        f"🆔 <b>Заявка #{safe_str(_get(order_row, 'id'))}</b>\n"
        f"🔧 <b>{category_label(_get(order_row, 'category'))}</b>\n"
        f"📍 {safe_user_text(_get(order_row, 'district'))}\n\n"
        f"📝 {safe_user_text(_get(order_row, 'problem'))}\n\n"
        f"📌 <b>Статус:</b> {status_label(_get(order_row, 'status'))}\n"
        f"👷 <b>Майстер:</b> {safe_user_text(master_name)}\n"
        f"⭐ <b>Оцінка:</b> {safe_str(_get(order_row, 'rating'))}"
    )


def offer_card_text(offer) -> str:
    presence = _master_presence_text(offer)

    return (
        "💼 <b>Пропозиція</b>\n\n"
        f"👷 <b>{safe_user_text(_get(offer, 'name'))}</b>\n"
        f"{presence}\n"
        f"⭐ {_rating_text(_get(offer, 'rating'))} · відгуків: {safe_str(_get(offer, 'reviews_count', 0))}\n\n"
        f"💰 <b>{safe_user_text(_get(offer, 'price'))}</b>\n"
        f"⏱ <b>{safe_user_text(_get(offer, 'eta'))}</b>\n\n"
        f"📝 {safe_user_text(_get(offer, 'comment', 'Без коментаря'))}"
    )


def client_master_selected_text(master_name: str, phone: str, rating=None, reviews_count=None, eta: str = None) -> str:
    rating_line = f"⭐ {_rating_text(rating)}" if rating is not None else ""
    reviews_line = f" · {safe_str(reviews_count)} відгуків" if reviews_count is not None else ""
    eta_line = f"\n⏱ {safe_user_text(eta)}" if eta else ""
    rating_block = f"{rating_line}{reviews_line}\n" if rating_line or reviews_line else ""

    return (
        "🎉 <b>Майстра обрано</b>\n\n"
        f"👷 <b>{safe_user_text(master_name)}</b>\n"
        f"📞 <b>{safe_user_text(phone)}</b>\n"
        f"{rating_block}"
        f"{eta_line}\n\n"
        "💬 Напишіть або зателефонуйте, щоб домовитись про деталі."
    )


def master_selected_for_master_text(order_id: int) -> str:
    return (
        f"🚀 <b>Вас обрали за заявкою #{order_id}</b>\n\n"
        "Клієнт відкрив контакти.\n"
        "Зв’яжіться з ним якнайшвидше."
    )


def order_reopened_text(order_id: int) -> str:
    return (
        f"🔄 <b>Заявку #{order_id} повторно відкрито</b>\n\n"
        "Попереднього майстра відключено.\n"
        "Можете обрати іншого або чекати нові пропозиції."
    )


def chat_open_text(order_id: int, is_client: bool) -> str:
    if is_client:
        return f"💬 <b>Чат по заявці #{order_id}</b>\n\nНапишіть майстру повідомлення."
    return f"💬 <b>Чат по заявці #{order_id}</b>\n\nНапишіть клієнту повідомлення."


def chat_text_message(order_id: int, role: str, text: str) -> str:
    prefix = "👤 Клієнт" if role == "client" else "👷 Майстер"
    return f"💬 <b>Заявка #{order_id}</b>\n{prefix}:\n{safe_user_text(text)}"


def chat_media_caption(order_id: int, role: str, caption: str, icon: str) -> str:
    prefix = "👤 Клієнт" if role == "client" else "👷 Майстер"
    base = f"{icon} <b>Заявка #{order_id}</b>\n{prefix}"
    return f"{base}\n{safe_user_text(caption)}" if caption else base


def rating_intro(order_id: int) -> str:
    return f"⭐ <b>Оцініть майстра</b>\n\nЗаявка #{order_id}. Як пройшла робота?"


def rating_thanks() -> str:
    return "✅ <b>Дякуємо!</b>\n\nВаш відгук допоможе іншим клієнтам."


def nearby_masters_intro_text(category: str, count: int) -> str:
    return (
        f"👷 <b>Майстри поруч: {category_label(category)}</b>\n\n"
        f"Показуємо підтверджених майстрів у цій категорії: <b>{count}</b>.\n"
        "Контакти відкриваються тільки після створення заявки та вибору майстра."
    )


def no_nearby_masters_text(category: str) -> str:
    return (
        f"😕 <b>Поки немає майстрів: {category_label(category)}</b>\n\n"
        "Створіть заявку — адміністратор допоможе знайти спеціаліста, "
        "щойно він буде доступний."
    )


def public_master_card_text(master_row) -> str:
    presence = _master_presence_text(master_row)
    name = _get(master_row, "name", "Майстер")
    category = _get(master_row, "category", "")
    district = _get(master_row, "district", "—")
    rating = _rating_text(_get(master_row, "rating", 0))
    reviews_count = int(_get(master_row, "reviews_count", 0) or 0)
    description = _get(master_row, "description", "—")

    return (
        f"👷 <b>{safe_user_text(name)}</b>\n"
        f"{presence}\n"
        f"⭐ {rating} · відгуків: {reviews_count}\n"
        f"🔧 {category_labels(category)}\n"
        f"📍 {safe_user_text(district)}\n\n"
        f"🧾 {safe_user_text(description)}"
    )


def public_master_profile_text(master_row, reviews=None) -> str:
    reviews = reviews or []
    presence = _master_presence_text(master_row)
    name = _get(master_row, "name", "Майстер")
    category = _get(master_row, "category", "")
    district = _get(master_row, "district", "—")
    rating = _rating_text(_get(master_row, "rating", 0))
    reviews_count = int(_get(master_row, "reviews_count", 0) or 0)
    description = _get(master_row, "description", "—")
    experience = _get(master_row, "experience", "—")

    review_lines = []
    for item in reviews[:5]:
        review_rating = _get(item, "rating", "—")
        review_text = _get(item, "review_text", "")
        if review_text:
            review_lines.append(f"⭐ {safe_str(review_rating)} — {safe_user_text(review_text)}")
        else:
            review_lines.append(f"⭐ {safe_str(review_rating)} — без текстового відгуку")

    reviews_block = "\n".join(review_lines) if review_lines else "Поки немає текстових відгуків."

    return (
        f"👷 <b>{safe_user_text(name)}</b>\n\n"
        f"🔧 {category_labels(category)}\n"
        f"📍 {safe_user_text(district)}\n"
        f"{presence}\n\n"
        f"⭐ <b>{rating}</b> · відгуків: <b>{reviews_count}</b>\n\n"
        f"🧾 <b>Про майстра</b>\n{safe_user_text(description)}\n\n"
        f"🛠 <b>Досвід</b>\n{safe_user_text(experience)}\n\n"
        f"📜 <b>Останні відгуки</b>\n{reviews_block}"
    )


def master_public_profile_text(master_row, reviews=None) -> str:
    return public_master_profile_text(master_row, reviews)
