import logging
import os
import socket

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import back_menu_kb, main_menu_kb, support_reply_inline
from repositories import add_support_message, approved_master_row, touch_master_presence
from states import SupportWrite
from ui_texts import menu_text, support_intro, support_sent, welcome_text
from utils import is_admin, normalize_text


logger = logging.getLogger(__name__)

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}


def register(dp):
    async def update_master_presence_if_needed(user_id: int):
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)

    @dp.message_handler(commands=["diag"], state="*")
    async def diag_handler(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        await message.answer(
            f"hostname={socket.gethostname()}\n"
            f"pid={os.getpid()}"
        )

    @dp.message_handler(commands=["start"], state="*")
    async def start_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            welcome_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(lambda m: (m.text or "").strip() == "🏠 У меню", state="*")
    async def menu_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.callback_query_handler(lambda c: c.data == "exit_chat", state="*")
    async def exit_chat(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        role = data.get("chat_role")
        order_id = data.get("order_id")

        await state.finish()
        await update_master_presence_if_needed(call.from_user.id)

        if role and order_id:
            from keyboards import client_order_actions_inline, selected_order_master_actions

            reply_markup = (
                client_order_actions_inline(order_id, "matched")
                if role == "client"
                else selected_order_master_actions(order_id)
            )

            await call.message.answer(
                f"💬 <b>Режим написання по заявці #{order_id} закрито</b>",
                reply_markup=reply_markup,
            )
        else:
            await call.message.answer(
                "💬 <b>Діалог закрито</b>\n\nПовертаю вас до меню.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id)),
            )

        await call.answer()

    @dp.message_handler(lambda m: m.text == "🆘 Допомога", state="*")
    async def support_start(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await SupportWrite.text.set()
        await message.answer(
            support_intro(),
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(lambda m: (m.text or "").strip() in BACK_BUTTONS, state=SupportWrite.text)
    async def support_back(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(state=SupportWrite.text, content_types=types.ContentTypes.TEXT)
    async def support_send(message: types.Message, state: FSMContext):
        text = normalize_text(message.text, 2000)

        if not text or len(text) < 3:
            await message.answer(
                "Напишіть повідомлення трохи детальніше.",
                reply_markup=back_menu_kb(),
            )
            return

        user = message.from_user
        username_line = f"🔗 Username: @{user.username}\n" if user.username else ""

        admin_text = (
            "🆘 <b>Нове звернення в підтримку</b>\n\n"
            f"👤 <b>Користувач:</b> {user.full_name}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"{username_line}"
            f"\n💬 <b>Повідомлення:</b>\n{text}"
        )

        try:
            await add_support_message(user.id, text)

            await message.bot.send_message(
                settings.admin_id,
                admin_text,
                reply_markup=support_reply_inline(user.id),
            )
        except Exception as e:
            logger.warning("Не вдалося відправити повідомлення в підтримку адміну: %s", e)
            await message.answer(
                "Не вдалося надіслати повідомлення адміністратору. Спробуйте пізніше.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            await state.finish()
            return

        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            support_sent(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )
