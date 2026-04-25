import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardRemove

from keyboards import client_order_actions_inline, main_menu_kb, selected_order_master_actions
from repositories import get_chat_history, get_order_row, touch_master_presence
from security import allow_message_action
from services import send_chat_history
from states import ChatFlow
from utils import is_admin


logger = logging.getLogger(__name__)

CHAT_CLOSE_BUTTONS = {"❌ Закрити", "❌ Закрити чат", "Закрити"}
CHAT_HISTORY_BUTTONS = {"📜 Історія", "Історія"}
CHAT_MENU_BUTTONS = {"🏠 У меню", "⬅️ Назад", "Назад", "🔙 Назад"}


async def _client_after_chat_markup(order_id: int):
    order = await get_order_row(order_id)
    status = order["status"] if order else "matched"
    return client_order_actions_inline(order_id, status)


async def _master_after_chat_markup(order_id: int):
    order = await get_order_row(order_id)
    if order and order["status"] in {"matched", "in_progress"}:
        return selected_order_master_actions(order_id)
    return None


async def _send_after_chat_screen(message: types.Message, *, role: str | None, order_id: int | None):
    """
    Спочатку прибирає ReplyKeyboard, щоб кнопки "📜 Історія / ❌ Закрити"
    не залишались після виходу з ChatFlow.message.
    """
    await message.answer(
        "✋ <b>Режим написання закрито</b>",
        reply_markup=ReplyKeyboardRemove(),
    )

    if role == "client" and order_id:
        await message.answer(
            f"📄 <b>Ви повернулись до заявки #{order_id}</b>",
            reply_markup=await _client_after_chat_markup(order_id),
        )
        return

    if role == "master" and order_id:
        markup = await _master_after_chat_markup(order_id)
        if markup:
            try:
                await touch_master_presence(message.from_user.id)
            except Exception:
                logger.exception("Failed to update master presence after chat close")

            await message.answer(
                f"📄 <b>Ви повернулись до заявки #{order_id}</b>",
                reply_markup=markup,
            )
            return

    await message.answer(
        "🏠 <b>Повернення в меню</b>",
        reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
    )


def register(dp):
    @dp.message_handler(lambda m: (m.text or "") in CHAT_HISTORY_BUTTONS, state=ChatFlow.message)
    async def fixed_history_from_dialog(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="open_chat_history_message_fixed",
            limit=10,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        data = await state.get_data()
        order_id = data.get("order_id")

        if not order_id:
            await state.finish()
            await message.answer(
                "Не вдалося визначити заявку. Чат закрито.",
                reply_markup=ReplyKeyboardRemove(),
            )
            await message.answer(
                "🏠 <b>Повернення в меню</b>",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        msgs = await get_chat_history(int(order_id), 30)
        await send_chat_history(dp.bot, message.chat.id, int(order_id), msgs)
        await message.answer(
            "💬 <b>Режим чату активний</b>\n\n"
            "Можете написати ще повідомлення або натиснути <b>❌ Закрити</b>."
        )

    @dp.message_handler(lambda m: (m.text or "") in CHAT_CLOSE_BUTTONS, state=ChatFlow.message)
    async def fixed_close_dialog_mode(message: types.Message, state: FSMContext):
        data = await state.get_data()
        role = data.get("chat_role")
        order_id = data.get("order_id")

        await state.finish()
        await _send_after_chat_screen(
            message,
            role=role,
            order_id=int(order_id) if order_id else None,
        )

    @dp.message_handler(lambda m: (m.text or "") in CHAT_MENU_BUTTONS, state=ChatFlow.message)
    async def fixed_close_dialog_navigation(message: types.Message, state: FSMContext):
        data = await state.get_data()
        role = data.get("chat_role")
        order_id = data.get("order_id")

        await state.finish()

        if message.text == "🏠 У меню":
            await message.answer(
                "🏠 <b>Повернення в меню</b>",
                reply_markup=ReplyKeyboardRemove(),
            )
            await message.answer(
                "Оберіть дію 👇",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await _send_after_chat_screen(
            message,
            role=role,
            order_id=int(order_id) if order_id else None,
        )
