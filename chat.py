from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import exit_chat_inline
from repositories import (
    get_chat_for_order,
    create_chat_if_not_exists,
    save_chat_message,
)
from utils import normalize_text


def register(dp):

    @dp.callback_query_handler(lambda c: c.data.startswith("open_chat_"), state="*")
    async def open_chat(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        chat = await create_chat_if_not_exists(order_id)

        await state.update_data(active_chat_id=chat["id"], order_id=order_id)

        await call.message.answer(
            "💬 <b>Чат відкрито</b>\n\nПишіть повідомлення 👇",
            reply_markup=exit_chat_inline()
        )

        await call.answer()

    @dp.message_handler(state="*")
    async def chat_message(message: types.Message, state: FSMContext):
        data = await state.get_data()
        chat_id = data.get("active_chat_id")

        if not chat_id:
            return

        text = normalize_text(message.text, 2000)

        if not text:
            return

        chat = await get_chat_for_order(data["order_id"])
        if not chat:
            return

        sender_role = "client"
        receiver_id = chat["master_id"]

        if message.from_user.id == chat["master_id"]:
            sender_role = "master"
            receiver_id = chat["client_id"]

        # зберігаємо в БД
        await save_chat_message(chat_id, sender_role, text)

        # відправляємо іншій стороні
        try:
            await dp.bot.send_message(
                receiver_id,
                f"💬 {text}"
            )
        except Exception:
            pass
