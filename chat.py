import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from keyboards import back_menu_kb, main_menu_kb, master_menu_kb
from repositories import (
    approved_master_row,
    close_chat,
    create_chat_message,
    get_chat_for_order,
    get_chat_history,
    get_order_row,
)
from utils import is_admin


class ChatDialog(StatesGroup):
    active = State()


def register(dp):
    async def _resolve_chat_context(user_id: int, order_id: int):
        order = await get_order_row(order_id)
        if not order:
            return None

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active":
            return None

        client_user_id = int(chat["client_user_id"])
        master_user_id = int(chat["master_user_id"])

        if user_id == client_user_id:
            role = "client"
            peer_user_id = master_user_id
        elif user_id == master_user_id:
            role = "master"
            peer_user_id = client_user_id
        else:
            return None

        return {
            "order": order,
            "chat": chat,
            "role": role,
            "peer_user_id": peer_user_id,
        }

    async def _relay_chat_message(
        bot,
        target_user_id: int,
        message_type: str,
        text: str = None,
        file_id: str = None,
    ):
        try:
            if message_type == "text":
                await bot.send_message(target_user_id, text or " ")
                return True

            if message_type == "photo" and file_id:
                try:
                    await bot.send_photo(target_user_id, file_id, caption=text or None)
                    return True
                except Exception:
                    fallback = f"📷 Фото недоступне.\n\n{text}" if text else "📷 Фото недоступне."
                    await bot.send_message(target_user_id, fallback)
                    return True

            if message_type == "video" and file_id:
                try:
                    await bot.send_video(target_user_id, file_id, caption=text or None)
                    return True
                except Exception:
                    fallback = f"📹 Відео недоступне.\n\n{text}" if text else "📹 Відео недоступне."
                    await bot.send_message(target_user_id, fallback)
                    return True

            if message_type == "document" and file_id:
                try:
                    await bot.send_document(target_user_id, file_id, caption=text or None)
                    return True
                except Exception:
                    fallback = f"📎 Файл недоступний.\n\n{text}" if text else "📎 Файл недоступний."
                    await bot.send_message(target_user_id, fallback)
                    return True

            await bot.send_message(target_user_id, text or "Отримано повідомлення.")
            return True

        except Exception as e:
            logging.warning("Помилка пересилки повідомлення користувачу %s: %s", target_user_id, e)
            return False

    async def _save_and_forward(dp, sender_message: types.Message, state: FSMContext):
        data = await state.get_data()

        order_id = int(data["order_id"])
        chat_id = int(data["chat_id"])
        sender_role = data["role"]
        peer_user_id = int(data["peer_user_id"])

        message_type = "text"
        text = sender_message.text or sender_message.caption or None
        file_id = None

        if sender_message.photo:
            message_type = "photo"
            file_id = sender_message.photo[-1].file_id
        elif sender_message.video:
            message_type = "video"
            file_id = sender_message.video.file_id
        elif sender_message.document:
            message_type = "document"
            file_id = sender_message.document.file_id
        elif sender_message.text:
            message_type = "text"
        else:
            await sender_message.answer(
                "Підтримуються текст, фото, відео та документи.",
                reply_markup=back_menu_kb(),
            )
            return

        await create_chat_message(
            chat_id=chat_id,
            order_id=order_id,
            sender_user_id=sender_message.from_user.id,
            sender_role=sender_role,
            message_type=message_type,
            text=text,
            file_id=file_id,
        )

        ok = await _relay_chat_message(
            dp.bot,
            target_user_id=peer_user_id,
            message_type=message_type,
            text=text,
            file_id=file_id,
        )

        if ok:
            await sender_message.answer("✅ Повідомлення надіслано.", reply_markup=back_menu_kb())
        else:
            await sender_message.answer("⚠️ Повідомлення збережено, але не вдалося доставити співрозмовнику.", reply_markup=back_menu_kb())

    @dp.callback_query_handler(
        lambda c: c.data.startswith("chat_open_")
        or c.data.startswith("open_chat_")
        or c.data.startswith("start_chat_")
        or c.data.startswith("order_chat_")
        or c.data.startswith("dialog_"),
        state="*",
    )
    async def open_chat(call: types.CallbackQuery, state: FSMContext):
        raw = call.data

        prefixes = [
            "chat_open_",
            "open_chat_",
            "start_chat_",
            "order_chat_",
            "dialog_",
        ]

        order_id = None
        for prefix in prefixes:
            if raw.startswith(prefix):
                value = raw.replace(prefix, "", 1)
                if value.isdigit():
                    order_id = int(value)
                break

        if not order_id:
            await call.answer("Не вдалося відкрити чат", show_alert=True)
            return

        ctx = await _resolve_chat_context(call.from_user.id, order_id)
        if not ctx:
            await call.answer("Чат недоступний", show_alert=True)
            return

        await state.update_data(
            order_id=order_id,
            chat_id=int(ctx["chat"]["id"]),
            role=ctx["role"],
            peer_user_id=int(ctx["peer_user_id"]),
        )
        await ChatDialog.active.set()

        history = await get_chat_history(order_id, limit=20)

        if history:
            lines = [f"📜 <b>Історія чату по заявці #{order_id}</b>", ""]
            for msg in reversed(history):
                sender = "👤 Клієнт" if msg["sender_role"] == "client" else "👷 Майстер"
                if msg["message_type"] == "text":
                    body = msg["text"] or "Без тексту"
                elif msg["message_type"] == "photo":
                    body = f"📷 {msg['text'] or 'Фото'}"
                elif msg["message_type"] == "video":
                    body = f"📹 {msg['text'] or 'Відео'}"
                elif msg["message_type"] == "document":
                    body = f"📎 {msg['text'] or 'Документ'}"
                else:
                    body = f"[{msg['message_type']}] {msg['text'] or ''}".strip()

                lines.append(f"{sender}:\n{body}\n")

            text = "\n".join(lines)
            for chunk in [text[i:i + 3500] for i in range(0, len(text), 3500)]:
                await call.message.answer(chunk, reply_markup=back_menu_kb())

        await call.message.answer(
            f"💬 <b>Чат по заявці #{order_id}</b>\n\n"
            f"Надішліть повідомлення, фото, відео або документ.\n"
            f"Щоб вийти, натисніть «⬅️ Назад».",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(
        content_types=[
            types.ContentType.TEXT,
            types.ContentType.PHOTO,
            types.ContentType.VIDEO,
            types.ContentType.DOCUMENT,
        ],
        state=ChatDialog.active,
    )
    async def chat_message_handler(message: types.Message, state: FSMContext):
        if (message.text or "").strip() == "⬅️ Назад":
            data = await state.get_data()
            role = data.get("role")
            await state.finish()

            if role == "master":
                await message.answer("↩️ Ви вийшли з чату.", reply_markup=master_menu_kb())
            else:
                await message.answer(
                    "↩️ Ви вийшли з чату.",
                    reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
                )
            return

        await _save_and_forward(dp, message, state)

    @dp.callback_query_handler(
        lambda c: c.data.startswith("chat_close_") or c.data.startswith("close_chat_"),
        state="*",
    )
    async def close_chat_handler(call: types.CallbackQuery, state: FSMContext):
        raw = call.data
        prefixes = ["chat_close_", "close_chat_"]

        order_id = None
        for prefix in prefixes:
            if raw.startswith(prefix):
                value = raw.replace(prefix, "", 1)
                if value.isdigit():
                    order_id = int(value)
                break

        if not order_id:
            await call.answer("Не вдалося закрити чат", show_alert=True)
            return

        ctx = await _resolve_chat_context(call.from_user.id, order_id)
        if not ctx:
            await call.answer("Чат недоступний", show_alert=True)
            return

        await close_chat(order_id)

        try:
            await dp.bot.send_message(
                ctx["peer_user_id"],
                f"🔒 Чат по заявці #{order_id} закрито."
            )
        except Exception as e:
            logging.warning("Не вдалося повідомити співрозмовника про закриття чату: %s", e)

        await state.finish()
        await call.message.answer(f"🔒 Чат по заявці #{order_id} закрито.", reply_markup=back_menu_kb())
        await call.answer()
