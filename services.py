import logging
from aiogram import Bot
from keyboards import admin_order_actions_inline, order_card_master_actions
from repositories import get_master_name, get_chat_for_order
from ui_texts import master_card_text


async def send_master_card(bot: Bot, chat_id: int, master_row, title="👷 <b>Картка майстра</b>", reply_markup=None):
    text = master_card_text(master_row, title)
    if master_row.get("photo"):
        try:
            await bot.send_photo(chat_id, master_row["photo"], caption=text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def send_order_card(bot, chat_id: int, order_row, title: str = "📄 Ваша заявка", reply_markup=None):
    text = (
        f"{title}\n\n"
        f"🛠 Категорія: {order_row['category']}\n"
        f"📍 Район: {order_row['district']}\n"
        f"📝 Опис: {order_row['problem']}\n"
        f"📌 Статус: {order_row['status']}"
    )

    media_file_id = order_row.get("media_file_id")
    media_type = order_row.get("media_type")

    if media_file_id:
        try:
            if media_type == "photo":
                await bot.send_photo(chat_id, media_file_id, caption=text, reply_markup=reply_markup)
                return
            elif media_type == "video":
                await bot.send_video(chat_id, media_file_id, caption=text, reply_markup=reply_markup)
                return
            else:
                await bot.send_photo(chat_id, media_file_id, caption=text, reply_markup=reply_markup)
                return
        except Exception:
            pass

    await bot.send_message(chat_id, text, reply_markup=reply_markup)


async def send_admin_order_detail(bot: Bot, chat_id: int, order, offers):
    chat = await get_chat_for_order(order["id"])
    chat_info = "є" if chat and chat["status"] in ["active", "closed"] else "немає"
    media_info = "є" if order["media_file_id"] else "немає"
    selected_master_name = await get_master_name(order["selected_master_id"])

    offers_text = "немає"
    if offers:
        parts = []
        for offer in offers:
            parts.append(f"• <b>{offer['name'] or '-'}</b> · {offer['price']} · {offer['eta']}\n  {offer['comment']}")
        offers_text = "\n".join(parts)

    detail_text = (
        f"🧾 <b>Деталі заявки #{order['id']}</b>\n\n"
        f"👤 <b>Клієнт ID:</b> {order['user_id']}\n"
        f"📍 <b>Район / адреса:</b> {order['district'] or '—'}\n"
        f"💬 <b>Чат:</b> {chat_info}\n"
        f"📷 <b>Медіа:</b> {media_info}\n"
        f"👷 <b>Обраний майстер:</b> {selected_master_name}\n"
        f"⭐ <b>Оцінка:</b> {order['rating'] if order['rating'] is not None else '—'}\n"
        f"🗒 <b>Відгук:</b> {order['review_text'] or '—'}\n\n"
        f"📬 <b>Пропозиції майстрів</b>\n{offers_text}"
    )

    media_file_id = order.get("media_file_id")
    media_type = order.get("media_type")

    if media_file_id:
        try:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id,
                    media_file_id,
                    caption=detail_text,
                    reply_markup=admin_order_actions_inline(order["id"], order["status"])
                )
                return
            elif media_type == "video":
                await bot.send_video(
                    chat_id,
                    media_file_id,
                    caption=detail_text,
                    reply_markup=admin_order_actions_inline(order["id"], order["status"])
                )
                return
        except Exception:
            pass

    await bot.send_message(
        chat_id,
        detail_text,
        reply_markup=admin_order_actions_inline(order["id"], order["status"])
    )


async def notify_masters_about_order(bot: Bot, order_row, masters):
    for master in masters:
        try:
            await send_order_card(
                bot,
                master["user_id"],
                order_row,
                title="🔔 <b>Нова заявка</b>",
                reply_markup=order_card_master_actions(order_row["id"])
            )
            await bot.send_message(
                master["user_id"],
                "Натисніть <b>📨 Відгукнутись</b>, якщо хочете взяти цю заявку в роботу."
            )
        except Exception as e:
            logging.warning("Помилка повідомлення майстру %s: %s", master["user_id"], e)


async def notify_admin_about_order(bot: Bot, admin_id: int, order_row):
    try:
        await send_order_card(bot, admin_id, order_row, title="📦 <b>Нова заявка клієнта</b>")
    except Exception as e:
        logging.warning("Помилка повідомлення адміну: %s", e)


async def send_chat_history(bot: Bot, chat_id: int, order_id: int, messages):
    if not messages:
        await bot.send_message(chat_id, f"📜 <b>Історія чату по заявці #{order_id}</b>\n\nПовідомлень поки немає.")
        return

    lines = [f"📜 <b>Історія чату по заявці #{order_id}</b>\n\nПоказано повідомлень: {len(messages)}", ""]

    for msg in reversed(messages):
        sender = "👤 <b>Клієнт</b>" if msg["sender_role"] == "client" else "👷 <b>Майстер</b>"

        if msg["message_type"] == "text":
            body = msg["text"] or "Без тексту"
        elif msg["message_type"] == "photo":
            body = f"📷 {msg['text'] or 'Фото без підпису'}"
        elif msg["message_type"] == "video":
            body = f"📹 {msg['text'] or 'Відео без підпису'}"
        else:
            body = f"[{msg['message_type']}] {msg['text'] or ''}".strip()

        lines.append(f"{sender}:\n{body}\n")

    text = "\n".join(lines)

    for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
        await bot.send_message(chat_id, chunk)
