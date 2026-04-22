from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import back_menu_kb, help_role_inline_kb
from repositories import approved_master_row, touch_master_presence


def client_help_text() -> str:
    return (
        "👤 <b>Як користуватись клієнту</b>\n\n"
        "1. Оберіть потрібну спеціальність\n"
        "2. Натисніть <b>📨 Створити заявку</b>\n"
        "3. Вкажіть район\n"
        "4. Опишіть проблему\n"
        "5. 📷 Додайте фото або відео проблеми <i>(за бажанням)</i>\n"
        "6. Вкажіть номер телефону\n"
        "7. Дочекайтесь пропозицій від майстрів\n"
        "8. Оберіть майстра, який вам підходить\n"
        "9. Після виконання оцініть роботу\n\n"
        "💡 Чим точніше опис і фото, тим швидше майстри відгукнуться."
    )


def master_help_text() -> str:
    return (
        "🔧 <b>Як користуватись майстру</b>\n\n"
        "1. Пройдіть реєстрацію майстра\n"
        "2. Дочекайтесь підтвердження від адміністратора\n"
        "3. Перейдіть у <b>📦 Нові заявки</b>\n"
        "4. Натисніть <b>📨 Відгукнутись</b>\n"
        "5. Вкажіть ціну\n"
        "6. Напишіть, коли зможете приїхати\n"
        "7. Додайте короткий коментар\n"
        "8. Якщо клієнт обере вас — зв'яжіться з ним\n"
        "9. Після виконання натисніть <b>🏁 Завершити заявку</b>\n\n"
        "💡 Чим швидше і зрозуміліше ви відгукнетесь, тим вищий шанс, що клієнт обере саме вас."
    )


def register(dp):
    async def update_master_presence_if_needed(user_id: int):
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)

    @dp.message_handler(lambda m: m.text == "ℹ️ Як користуватись", state="*")
    async def open_help(message: types.Message, state: FSMContext):
        await update_master_presence_if_needed(message.from_user.id)
        await message.answer(
            "ℹ️ <b>Інструкція користування</b>\n\nОберіть, для кого показати інструкцію:",
            reply_markup=help_role_inline_kb(),
        )

    @dp.callback_query_handler(lambda c: c.data == "help_client", state="*")
    async def show_client_help(call: types.CallbackQuery, state: FSMContext):
        await update_master_presence_if_needed(call.from_user.id)
        await call.message.answer(
            client_help_text(),
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "help_master", state="*")
    async def show_master_help(call: types.CallbackQuery, state: FSMContext):
        await update_master_presence_if_needed(call.from_user.id)
        await call.message.answer(
            master_help_text(),
            reply_markup=back_menu_kb(),
        )
        await call.answer()

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
