from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import back_menu_kb
from repositories import approved_master_row, touch_master_presence


def register(dp):
    async def update_master_presence_if_needed(user_id: int):
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)

    @dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
    async def fallback(message: types.Message, state: FSMContext):
        await update_master_presence_if_needed(message.from_user.id)

        if (message.text or "").startswith("/"):
            return

        current_state = await state.get_state()

        # Якщо state неактивний — нічого не відповідаємо,
        # щоб не дублювати реакції інших handler-ів.
        if not current_state:
            return

        await message.answer(
            "Не зрозумів дію. Скористайтесь кнопками меню.",
            reply_markup=back_menu_kb(),
        )
