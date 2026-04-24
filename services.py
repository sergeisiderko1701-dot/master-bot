import json
import logging
from aiogram import Bot

from constants import category_label, status_label
from keyboards import admin_order_actions_inline, order_card_master_actions
from repositories import create_notification_job, execute, get_chat_for_order, get_master_name
from utils import now_ts, safe_str
from ui_texts import master_card_text


logger = logging.getLogger(__name__)


def safe_val(row, key, default=None):
    try:
        value = row[key]
        return default if value is None else value
    except Exception:
        return default


def h(value, default="—") -> str:
    return safe_str(value, default)


async def clear_broken_order_media(order_id: int):
    if not order_id:
        return

    try:
        await execute(
            """
            UPDATE orders
            SET media_type=NULL,
                media_file_id=NULL,
                updated_at=$2
            WHERE id=$1
            """,
            order_id,
            now_ts(),
        )
        logger.warning("Broken media cleared for order %s", order_id)
    except Exception as e:
        logger.exception("Failed to clear broken media for order %s: %s", order_id, e)


def is_invalid_file_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "wrong file identifier",
        "wrong file_id",
        "wrong remote file identifier",
        "failed to get http url content",
        "bad request: wrong file identifier",
        "invalid file http url specified",
        "wrong type of the web page content",
    ]
    return any(marker in text for marker in markers)


async def send_master_card(
    bot: Bot,
    chat_id: int,
    master_row,
    title: str = "👷 <b>Картка майстра</b>",
    reply_markup=None,
):
    text = master_card_text(master_row, title)
    photo = safe_val(master_row, "photo")

    if photo:
        try:
            await bot.send_photo(
                chat_id,
                photo,
                caption=text,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            logger.warning("Не вдалося надіслати фото майстра в чат %s: %s", chat_id, e)

    await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def send_order_card(
    bot: Bot,
    chat_id: int,
    order_row,
    title: str = "📄 Ваша заявка",
    reply_markup=None,
):
    order_id = safe_val(order_row, "id")
    category = safe_val(order_row, "category", "-")
    district = h(safe_val(order_row, "district", "-"), "-")
    problem = h(safe_val(order_row, "problem", "-"), "-")
    status = status_label(safe_val(order_row, "status", "-"))

    text = (
        f"{title}\n\n"
        f"🛠 Категорія: {category_label(category) if category != '-' else '-'}\n"
        f"📍 Район: {district}\n"
        f"📝 Опис: {problem}\n"
        f"📌 Статус: {status}"
    )

    media_file_id = safe_val(order_row, "media_file_id")
    media_type = safe_val(order_row, "media_type")

    if media_file_id:
        try:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id,
                    media_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                )
                return

            if media_type == "video":
                await bot.send_video(
                    chat_id,
                    media_file_id,
                    caption=text,
                    reply_markup=reply_markup,
                )
                return

            logger.warning(
                "Невідомий media_type '%s' для заявки %s",
                media_type,
                order_id or "?",
            )
        except Exception as e:
            logger.warning(
                "Не вдалося надіслати медіа за заявкою %s в чат %s: %s",
                order_id or "?",
                chat_id,
                e,
            )

            if is_invalid_file_error(e):
                await clear_broken_order_media(order_id)

    await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def send_admin_order_detail(bot: Bot, chat_id: int, order, offers):
    order_id = safe_val(order, "id")
    chat = await get_chat_for_order(order_id)
    chat_info = "є" if chat and safe_val(chat, "status") in ["active", "closed"] else "немає"
    media_info = "є" if safe_val(order, "media_file_id") else "немає"
    selected_master_name = h(await get_master_name(safe_val(order, "selected_master_id")))

    offers_text = "немає"
    if offers:
        parts = []
        for offer in offers:
            offer_name = h(safe_val(offer, "name", "-"), "-")
            offer_price = h(safe_val(offer, "price", "-"), "-")
            offer_eta = h(safe_val(offer, "eta", "-"), "-")
            offer_comment = h(safe_val(offer, "comment", "-"), "-")
            parts.append(
                f"• <b>{offer_name}</b> · {offer_price} · {offer_eta}\n"
                f"  {offer_comment}"
            )
        offers_text = "\n".join(parts)

    detail_text = (
        f"🧾 <b>Деталі заявки #{order_id}</b>\n\n"
        f"👤 <b>Клієнт ID:</b> {h(safe_val(order, 'user_id', '-'), '-')}\n"
        f"🛠 <b>Категорія:</b> {category_label(safe_val(order, 'category', '-')) if safe_val(order, 'category') else '-'}\n"
        f"📍 <b>Район / адреса:</b> {h(safe_val(order, 'district', '—'))}\n"
        f"📝 <b>Опис:</b> {h(safe_val(order, 'problem', '—'))}\n"
        f"📌 <b>Статус:</b> {status_label(safe_val(order, 'status', '-'))}\n"
        f"💬 <b>Чат:</b> {chat_info}\n"
        f"📷 <b>Медіа:</b> {media_info}\n"
        f"👷 <b>Обраний майстер:</b> {selected_master_name}\n"
        f"⭐ <b>Оцінка:</b> {h(safe_val(order, 'rating', '—'))}\n"
        f"🗒 <b>Відгук:</b> {h(safe_val(order, 'review_text', '—'))}\n\n"
        f"📬 <b>Пропозиції майстрів</b>\n{offers_text}"
    )

    media_file_id = safe_val(order, "media_file_id")
    media_type = safe_val(order, "media_type")

    if media_file_id:
        try:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id,
                    media_file_id,
                    caption=detail_text,
                    reply_markup=admin_order_actions_inline(order_id, safe_val(order, "status")),
                )
                return

            if media_type == "video":
                await bot.send_video(
                    chat_id,
                    media_file_id,
                    caption=detail_text,
                    reply_markup=admin_order_actions_inline(order_id, safe_val(order, "status")),
                )
                return
        except Exception as e:
            logger.warning("Не вдалося надіслати деталі заявки %s з медіа: %s", order_id, e)

            if is_invalid_file_error(e):
                await clear_broken_order_media(order_id)

    await bot.send_message(
        chat_id,
        detail_text,
        reply_markup=admin_order_actions_inline(order_id, safe_val(order, "status")),
    )


async def notify_masters_about_order(bot: Bot, order_row, masters):
    """
    Queues notifications for masters instead of sending everything at once.
    """
    order_id = safe_val(order_row, "id")
    queued_count = 0

    payload = json.dumps(
        {
            "order_id": order_id,
            "title": "🔔 <b>Нова заявка</b>",
            "text_after_card": "Натисніть <b>📨 Відгукнутись</b>, якщо хочете взяти цю заявку в роботу.",
        },
        ensure_ascii=False,
    )

    for master in masters:
        master_user_id = safe_val(master, "user_id")
        if not master_user_id:
            continue

        try:
            job_id = await create_notification_job(
                user_id=int(master_user_id),
                order_id=int(order_id),
                notification_type="new_order",
                payload=payload,
            )
            if job_id:
                queued_count += 1
        except Exception as e:
            logger.warning("Помилка створення notification job для майстра %s: %s", master_user_id, e)

    logger.info(
        "Розсилка за заявкою %s поставлена в чергу. Jobs queued: %s",
        order_id,
        queued_count,
    )


async def notify_admin_about_order(bot: Bot, admin_id: int, order_row):
    try:
        await send_order_card(
            bot,
            admin_id,
            order_row,
            title="📦 <b>Нова заявка клієнта</b>",
        )
    except Exception as e:
        logger.warning("Помилка повідомлення адміну: %s", e)


async def send_chat_history(bot: Bot, chat_id: int, order_id: int, messages):
    if not messages:
        await bot.send_message(
            chat_id,
            f"📜 <b>Історія чату за заявкою #{order_id}</b>\n\nПовідомлень поки немає.",
        )
        return

    lines = [
        f"📜 <b>Історія чату за заявкою #{order_id}</b>\n\nПоказано повідомлень: {len(messages)}",
        "",
    ]

    for msg in reversed(messages):
        sender = "👤 <b>Клієнт</b>" if safe_val(msg, "sender_role") == "client" else "👷 <b>Майстер</b>"
        message_type = safe_val(msg, "message_type", "text")
        msg_text = h(safe_val(msg, "text", ""), "")

        if message_type == "text":
            body = msg_text or "Без тексту"
        elif message_type == "photo":
            body = f"📷 {msg_text or 'Фото без підпису'}"
        elif message_type == "video":
            body = f"📹 {msg_text or 'Відео без підпису'}"
        else:
            body = f"[{h(message_type, '')}] {msg_text}".strip()

        lines.append(f"{sender}:\n{body}\n")

    text = "\n".join(lines)

    for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
        await bot.send_message(chat_id, chunk)
