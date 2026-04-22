from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import back_menu_kb, help_role_inline_kb
from repositories import approved_master_row, touch_master_presence


def client_help_text() -> str:
    return (
        "👤 <b>Як створити заявку</b>\n\n"
        "1. Оберіть потрібну послугу\n"
        "2. Натисніть <b>📨 Створити заявку</b>\n"
        "3. Вкажіть <b>район або адресу</b>\n"
        "4. Коротко опишіть проблему\n"
        "5. 📷 Додайте фото або відео <i>(за бажанням)</i>\n"
        "6. Вкажіть номер телефону\n\n"
        "📬 Після цього ви отримаєте пропозиції від майстрів\n"
        "🤝 Оберіть найкращий варіант\n"
        "⭐ Після виконання оцініть роботу\n\n"
        "💡 Чим точніше опис і фото — тим швидше вам допоможуть"
    )


def master_help_text() -> str:
    return (
        "🔧 <b>Як працювати з заявками</b>\n\n"
        "1. Пройдіть реєстрацію майстра\n"
        "2. Дочекайтесь підтвердження\n"
        "3. Відкрийте <b>📦 Нові заявки</b>\n"
        "4. Оберіть заявку та натисніть <b>📨 Відгукнутись</b>\n"
        "5. Вкажіть ціну та час виконання\n"
        "6. Додайте короткий коментар\n\n"
        "📞 Якщо клієнт обере вас — відкриються контакти\n"
        "💬 Зв'яжіться з клієнтом та виконайте роботу\n"
        "🏁 Після завершення закрийте заявку\n\n"
        "💡 Швидкий і чіткий відгук підвищує шанс отримати замовлення"
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
            "ℹ️ <b>Інструкція користування</b>\n\n"
            "Оберіть, для кого показати інструкцію:",
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
