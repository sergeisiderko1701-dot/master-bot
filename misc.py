import os
import socket

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import back_menu_kb, main_menu_kb
from repositories import approved_master_row, touch_master_presence
from states import SupportWrite
from ui_texts import menu_text, support_intro, welcome_text
from utils import is_admin


BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}


def register(dp):
    async def update_master_presence_if_needed(user_id: int):
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)

    # 🔥 ДІАГНОСТИКА (без перевірки адміна)
    @dp.message_handler(commands=["diag"], state="*")
    async def diag_handler(message: types.Message, state: FSMContext):
        await message.answer(
            f"instance={settings.app_instance_name}\n"
            f"hostname={socket.gethostname()}\n"
            f"pid={os.getpid()}"
        )

    # START
    @dp.message_handler(commands=["start"], state="*")
    async def start_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            welcome_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    # 🏠 МЕНЮ
    @dp.message_handler(lambda m: (m.text or "").strip() == "🏠 У меню", state="*")
    async def menu_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    # ⬅️ НАЗАД
    @dp.message_handler(lambda m: (m.text or "") in BACK_BUTTONS, state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    # 💬 ВИХІД З ЧАТУ
    @dp.callback_query_handler(lambda c: c.data == "exit_chat", state="*")
    async def exit_chat(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(call.from_user.id)

        await call.message.answer(
            "💬 <b>Чат завершено</b>\n\nПовертаю вас у головне меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id))
        )
        await call.answer()

    # 🆘 ПІДТРИМКА (старт)
    @dp.message_handler(lambda m: m.text == "🆘 Допомога", state="*")
    async def support_start(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await SupportWrite.text.set()
        await message.answer(
            support_intro(),
            reply_markup=back_menu_kb()
        )

    # 📝 ПІДТРИМКА (ввід тексту)
    @dp.message_handler(state=SupportWrite.text, content_types=types.ContentTypes.TEXT)
    async def support_text_input(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if not text or len(text) < 3:
            await message.answer(
                "Опишіть питання трохи детальніше.",
                reply_markup=back_menu_kb()
            )
            return

        await message.answer(
            "✅ Ваше повідомлення прийнято. Найближчим часом вам дадуть відповідь.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

        await state.finish()

    # ❗ FALLBACK
    @dp.message_handler(state="*")
    async def fallback_handler(message: types.Message, state: FSMContext):
        if message.text and message.text.startswith("/"):
            return

        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            "Я не зрозумів команду. Скористайтесь меню нижче.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )
