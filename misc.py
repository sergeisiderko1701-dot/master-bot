import logging
import socket

from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import main_menu_kb
from utils import is_admin
from presence import update_master_presence_if_needed


logger = logging.getLogger(__name__)


def register(dp):
    @dp.message_handler(commands=["start"], state="*")
    async def start_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            "👋 Вітаємо!\n\nОберіть дію:",
            reply_markup=main_menu_kb(),
        )

    @dp.message_handler(lambda m: m.text == "⬅️ Назад", state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            "🔙 Повернулись у головне меню",
            reply_markup=main_menu_kb(),
        )

    @dp.message_handler(commands=["diag"])
    async def diag_handler(message: types.Message):
        if not is_admin(message.from_user.id):
            return

        text = (
            "🛠 <b>Діагностика</b>\n\n"
            f"hostname={socket.gethostname()}\n"
            f"user_id={message.from_user.id}"
        )

        await message.answer(text)
