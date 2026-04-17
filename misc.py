from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import back_menu_kb, main_menu_kb
from repositories import approved_master_row, touch_master_presence
from states import SupportWrite
from utils import is_admin
from ui_texts import menu_text, support_intro, welcome_text


def register(dp):
    @dp.message_handler(commands=["start"], state="*")
    async def start_handler(message: types.Message, state: FSMContext):
        await state.finish()
        if await approved_master_row(message.from_user.id):
            await touch_master_presence(message.from_user.id)

        await message.answer(
            welcome_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.message_handler(lambda m: (m.text or "").strip() == "🏠 У меню", state="*")
    async def menu_handler(message: types.Message, state: FSMContext):
        await state.finish()
        if await approved_master_row(message.from_user.id):
            await touch_master_presence(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.callback_query_handler(lambda c: c.data == "exit_chat", state="*")
    async def exit_chat(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await call.message.answer(
            "💬 <b>Чат завершено</b>\n\nПовертаю вас у головне меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id))
        )
        await call.answer()

    @dp.message_handler(lambda m: m.text == "🆘 Допомога", state="*")
    async def support_start(message: types.Message, state: FSMContext):
        await state.finish()
        await SupportWrite.text.set()
        await message.answer(
            support_intro(),
            reply_markup=back_menu_kb()
        )
