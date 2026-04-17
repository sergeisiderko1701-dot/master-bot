from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import chat_reply_kb, exit_chat_inline, main_menu_kb
from repositories import (
    create_chat_message,
    fetchrow,
    get_chat_for_order,
    get_chat_history,
    touch_master_presence,
)
from services import send_chat_history
from states import ChatFlow
from ui_texts import chat_media_caption, chat_open_text, chat_text_message
from utils import is_admin, normalize_text


def register(dp):
    async def open_chat_for_user(
        call: types.CallbackQuery,
        state: FSMContext,
        *,
        order_id: int,
        role: str,
        target_user_id: int,
        chat_id: int,
        is_client: bool,
    ):
        await state.update_data(
            chat_role=role,
            order_id=order_id,
            target_user_id=target_user_id,
            chat_id=chat_id,
        )
        await ChatFlow.message.set()
        await call.message.answer(
            chat_open_text(order_id, is_client),
            reply_markup=chat_reply_kb(),
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("client_chat_"), state="*")
    async def client_chat(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND user_id=$2
              AND selected_master_id IS NOT NULL
              AND status = ANY($3::text[])
            """,
            order_id,
            call.from_user.id,
            ["matched", "in_progress"],
        )
        if not order:
            await call.answer("Чат недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["client_user_id"] != call.from_user.id:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        await open_chat_for_user(
            call,
            state,
            order_id=order_id,
            role="client",
            target_user_id=chat["master_user_id"],
            chat_id=chat["id"],
            is_client=True,
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("master_chat_open_"), state="*")
    async def master_chat(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND selected_master_id=$2
              AND status = ANY($3::text[])
            """,
            order_id,
            call.from_user.id,
            ["matched", "in_progress"],
        )
        if not order:
            await call.answer("Чат недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["master_user_id"] != call.from_user.id:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        await touch_master_presence(call.from_user.id)

        await open_chat_for_user(
            call,
            state,
            order_id=order_id,
            role="master",
            target_user_id=chat["client_user_id"],
            chat_id=chat["id"],
            is_client=False,
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("chat_history_"), state="*")
    async def history(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        chat = await get_chat_for_order(order_id)
        if not chat:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        if call.from_user.id not in (chat["client_user_id"], chat["master_user_id"]):
            await call.answer("Доступ заборонено", show_alert=True)
            return

        msgs = await get_chat_history(order_id, 30)
        await send_chat_history(dp.bot, call.message.chat.id, order_id, msgs)
        await call.answer()

    @dp.message_handler(lambda m: m.text == "📜 Історія", state=ChatFlow.message)
    async def history_from_chat(message: types.Message, state: FSMContext):
        data = await state.get_data()
        msgs = await get_chat_history(data["order_id"], 30)
        await send_chat_history(dp.bot, message.chat.id, data["order_id"], msgs)

    @dp.message_handler(lambda m: m.text == "❌ Закрити чат", state=ChatFlow.message)
    async def close_chat_reply(message: types.Message, state: FSMContext):
        await state.finish()
        await message.answer(
            "💬 <b>Чат закрито</b>\n\nПовертаю вас у головне меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ChatFlow.message)
    async def relay_chat(message: types.Message, state: FSMContext):
        data = await state.get_data()
        target_id = data["target_user_id"]
        role = data["chat_role"]
        order_id = data["order_id"]
        chat_id = data["chat_id"]

        try:
            if role == "master":
                await touch_master_presence(message.from_user.id)

            if message.photo:
                caption = normalize_text(message.caption or "", 1000)
                await create_chat_message(
                    chat_id,
                    order_id,
                    message.from_user.id,
                    role,
                    "photo",
                    caption,
                    message.photo[-1].file_id,
                )
                await dp.bot.send_photo(
                    target_id,
                    message.photo[-1].file_id,
                    caption=chat_media_caption(order_id, role, caption, "📷"),
                    reply_markup=exit_chat_inline(),
                )
                await message.answer("📷 <b>Фото надіслано</b>", reply_markup=chat_reply_kb())
                return

            if message.video:
                caption = normalize_text(message.caption or "", 1000)
                await create_chat_message(
                    chat_id,
                    order_id,
                    message.from_user.id,
                    role,
                    "video",
                    caption,
                    message.video.file_id,
                )
                await dp.bot.send_video(
                    target_id,
                    message.video.file_id,
                    caption=chat_media_caption(order_id, role, caption, "📹"),
                    reply_markup=exit_chat_inline(),
                )
                await message.answer("📹 <b>Відео надіслано</b>", reply_markup=chat_reply_kb())
                return

            text = normalize_text(message.text or "", 1500)
            if not text:
                await message.answer(
                    "Напишіть повідомлення текстом або надішліть фото / відео.",
                    reply_markup=chat_reply_kb(),
                )
                return

            await create_chat_message(
                chat_id,
                order_id,
                message.from_user.id,
                role,
                "text",
                text,
                None,
            )
            await dp.bot.send_message(
                target_id,
                chat_text_message(order_id, role, text),
                reply_markup=exit_chat_inline(),
            )
            await message.answer("✅ <b>Повідомлення надіслано</b>", reply_markup=chat_reply_kb())

        except Exception:
            await message.answer(
                "Не вдалося переслати повідомлення. Спробуйте ще раз.",
                reply_markup=chat_reply_kb(),
            )
