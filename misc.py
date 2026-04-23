import logging
import os
import socket

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import back_menu_kb, main_menu_kb
from presence import update_master_presence_if_needed
from repositories import add_support_message
from security import allow_message_action
from states import SupportWrite
from ui_texts import menu_text, support_intro, support_sent, welcome_text
from utils import is_admin


logger = logging.getLogger(__name__)

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}


def register(dp):
    @dp.message_handler(commands=["diag"], state="*")
    async def diag_handler(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        await message.answer(
            f"hostname={socket.gethostname()}
"
            f"pid={os.getpid()}"
        )

    @dp.message_handler(commands=["start"], state="*")
    async def start_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            welcome_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.message_handler(lambda m: (m.text or "").strip() == "🏠 У меню", state="*")
    async def menu_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.message_handler(lambda m: (m.text or "") in BACK_BUTTONS, state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            menu_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.callback_query_handler(lambda c: c.data == "exit_chat", state="*")
    async def exit_chat(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(call.from_user.id)

        await call.message.answer(
            "💬 <b>Діалог закрито</b>

Повертаю вас до меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id))
        )
        await call.answer()

    @dp.message_handler(lambda m: m.text in {"🆘 Підтримка", "🆘 Допомога"}, state="*")
    async def support_start(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="support_start",
            limit=6,
            window_seconds=300,
            mute_seconds=900,
        )
        if not allowed:
            return

        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await SupportWrite.text.set()
        await message.answer(
            support_intro(),
            reply_markup=back_menu_kb()
        )

    @dp.message_handler(state=SupportWrite.text, content_types=types.ContentTypes.TEXT)
    async def support_send(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="support_send",
            limit=5,
            window_seconds=600,
            mute_seconds=1800,
        )
        if not allowed:
            return

        text = (message.text or "").strip()

        if not text or len(text) < 3:
            await message.answer(
                "Напишіть повідомлення трохи детальніше.",
                reply_markup=back_menu_kb()
            )
            return

        user = message.from_user
        username_line = f"🔗 Username: @{user.username}
" if user.username else ""

        admin_text = (
            "🆘 <b>Нове звернення в підтримку</b>

"
            f"👤 <b>Користувач:</b> {user.full_name}
"
            f"🆔 <b>ID:</b> <code>{user.id}</code>
"
            f"{username_line}"
            f"
💬 <b>Повідомлення:</b>
{text}"
        )

        try:
            await add_support_message(user.id, text)

            from keyboards import support_reply_inline

            await message.bot.send_message(
                settings.admin_id,
                admin_text,
                reply_markup=support_reply_inline(user.id),
            )
        except Exception as e:
            logger.warning("Не вдалося відправити повідомлення в підтримку адміну: %s", e)
            await message.answer(
                "Не вдалося надіслати повідомлення адміністратору. Спробуйте пізніше.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
            )
            await state.finish()
            return

        await state.finish()
        await message.answer(
            support_sent(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )
