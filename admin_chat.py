import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from keyboards import main_menu_kb
from repositories import create_chat_message, get_chat_for_order, get_chat_history
from security import allow_callback_action, allow_message_action
from services import send_chat_history
from utils import is_admin, safe_user_text


logger = logging.getLogger(__name__)


class AdminChatFlow(StatesGroup):
    message = State()


def admin_chat_actions_inline(order_id: int, chat) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)

    if chat and chat.get("client_user_id"):
        kb.add(
            InlineKeyboardButton(
                "👨‍💼 Відповісти клієнту як підтримка",
                callback_data=f"admin_chat_reply_client_{order_id}",
            )
        )

    if chat and chat.get("master_user_id"):
        kb.add(
            InlineKeyboardButton(
                "👨‍💼 Відповісти майстру як підтримка",
                callback_data=f"admin_chat_reply_master_{order_id}",
            )
        )

    return kb


def admin_chat_close_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("❌ Закрити"))
    kb.row(types.KeyboardButton("🏠 У меню"))
    return kb


def _admin_message_text(order_id: int, text: str) -> str:
    return (
        f"👨‍💼 <b>Адмін / підтримка</b>\n"
        f"💬 <b>Заявка #{order_id}</b>\n\n"
        f"{safe_user_text(text)}"
    )


def _admin_media_caption(order_id: int, caption: str | None, icon: str) -> str:
    base = (
        f"{icon} <b>Заявка #{order_id}</b>\n"
        "👨‍💼 <b>Адмін / підтримка</b>"
    )
    if caption:
        return f"{base}\n\n{safe_user_text(caption)}"
    return base


def register(dp):
    @dp.callback_query_handler(
        lambda c: c.data.startswith("chat_history_") and is_admin(c.from_user.id),
        state="*",
    )
    async def admin_chat_history(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="admin_open_chat_history",
            limit=20,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])
        chat = await get_chat_for_order(order_id)

        if not chat:
            await call.answer("Історію не знайдено", show_alert=True)
            return

        msgs = await get_chat_history(order_id, 50)
        await send_chat_history(dp.bot, call.message.chat.id, order_id, msgs)

        await call.message.answer(
            "👨‍💼 <b>Адмін-дії з чатом</b>\n\n"
            "Можете відповісти клієнту або майстру як підтримка.",
            reply_markup=admin_chat_actions_inline(order_id, chat),
        )
        await call.answer()

    @dp.callback_query_handler(
        lambda c: c.data.startswith("admin_chat_reply_") and is_admin(c.from_user.id),
        state="*",
    )
    async def admin_chat_reply_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="admin_chat_reply_start",
            limit=15,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        # admin_chat_reply_client_{order_id}
        # admin_chat_reply_master_{order_id}
        parts = call.data.split("_")
        target_role = parts[3]
        order_id = int(parts[-1])

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active":
            await call.answer("Активний чат не знайдено", show_alert=True)
            return

        if target_role == "client":
            target_user_id = int(chat["client_user_id"])
            target_label = "клієнту"
        elif target_role == "master":
            target_user_id = int(chat["master_user_id"])
            target_label = "майстру"
        else:
            await call.answer("Некоректний одержувач", show_alert=True)
            return

        await state.finish()
        await state.update_data(
            admin_chat_order_id=order_id,
            admin_chat_id=int(chat["id"]),
            admin_chat_target_user_id=target_user_id,
            admin_chat_target_role=target_role,
        )
        await AdminChatFlow.message.set()

        await call.message.answer(
            f"👨‍💼 <b>Відповідь як підтримка</b>\n\n"
            f"Заявка: <b>#{order_id}</b>\n"
            f"Кому: <b>{target_label}</b>\n\n"
            "Надішліть текст, фото або відео.\n"
            "Одержувач побачить повідомлення з тегом <b>👨‍💼 Адмін / підтримка</b>.",
            reply_markup=admin_chat_close_kb(),
        )
        await call.answer("Напишіть повідомлення")

    @dp.message_handler(
        lambda m: is_admin(m.from_user.id) and (m.text in {"❌ Закрити", "🏠 У меню", "⬅️ Назад"}),
        state=AdminChatFlow.message,
    )
    async def admin_chat_close(message: types.Message, state: FSMContext):
        await state.finish()
        await message.answer(
            "👨‍💼 <b>Режим відповіді підтримки закрито</b>",
            reply_markup=main_menu_kb(is_admin_user=True),
        )

    @dp.message_handler(
        lambda m: is_admin(m.from_user.id),
        content_types=types.ContentTypes.ANY,
        state=AdminChatFlow.message,
    )
    async def admin_chat_send(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="admin_chat_send",
            limit=20,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        data = await state.get_data()
        order_id = data.get("admin_chat_order_id")
        chat_id = data.get("admin_chat_id")
        target_user_id = data.get("admin_chat_target_user_id")
        target_role = data.get("admin_chat_target_role")

        if not order_id or not chat_id or not target_user_id or not target_role:
            await state.finish()
            await message.answer(
                "Не вдалося визначити чат. Відкрийте історію заявки ще раз.",
                reply_markup=main_menu_kb(is_admin_user=True),
            )
            return

        chat = await get_chat_for_order(int(order_id))
        if not chat or chat["status"] != "active":
            await state.finish()
            await message.answer(
                "Цей чат уже недоступний.",
                reply_markup=main_menu_kb(is_admin_user=True),
            )
            return

        try:
            if message.photo:
                caption = message.caption or ""
                file_id = message.photo[-1].file_id

                await create_chat_message(
                    int(chat_id),
                    int(order_id),
                    message.from_user.id,
                    "admin",
                    "photo",
                    caption,
                    file_id,
                )

                await dp.bot.send_photo(
                    int(target_user_id),
                    file_id,
                    caption=_admin_media_caption(int(order_id), caption, "📷"),
                )

                await message.answer(
                    "✅ <b>Фото надіслано від імені підтримки</b>",
                    reply_markup=admin_chat_close_kb(),
                )
                return

            if message.video:
                caption = message.caption or ""
                file_id = message.video.file_id

                await create_chat_message(
                    int(chat_id),
                    int(order_id),
                    message.from_user.id,
                    "admin",
                    "video",
                    caption,
                    file_id,
                )

                await dp.bot.send_video(
                    int(target_user_id),
                    file_id,
                    caption=_admin_media_caption(int(order_id), caption, "📹"),
                )

                await message.answer(
                    "✅ <b>Відео надіслано від імені підтримки</b>",
                    reply_markup=admin_chat_close_kb(),
                )
                return

            text = (message.text or "").strip()
            if not text:
                await message.answer(
                    "Надішліть текст, фото або відео.",
                    reply_markup=admin_chat_close_kb(),
                )
                return

            await create_chat_message(
                int(chat_id),
                int(order_id),
                message.from_user.id,
                "admin",
                "text",
                text,
                None,
            )

            await dp.bot.send_message(
                int(target_user_id),
                _admin_message_text(int(order_id), text),
            )

            await message.answer(
                "✅ <b>Повідомлення надіслано від імені підтримки</b>",
                reply_markup=admin_chat_close_kb(),
            )

        except Exception as e:
            logger.warning(
                "Failed to send admin chat message order_id=%s target_user_id=%s: %s",
                order_id,
                target_user_id,
                e,
            )
            await message.answer(
                "Не вдалося надіслати повідомлення. Спробуйте ще раз.",
                reply_markup=admin_chat_close_kb(),
            )
