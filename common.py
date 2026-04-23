from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import back_menu_kb, help_role_inline_kb
from presence import update_master_presence_if_needed


def client_help_text() -> str:
    return (
        "👤 <b>Як створити заявку</b>

"
        "1. Оберіть потрібну послугу
"
        "2. Натисніть <b>📨 Створити заявку</b>
"
        "3. Вкажіть <b>район або адресу</b>
"
        "4. Коротко опишіть проблему
"
        "5. Вкажіть номер телефону
"
        "6. 📷 Додайте фото або відео <i>(за бажанням)</i>

"
        "📬 Після цього ви отримаєте пропозиції від майстрів
"
        "🤝 Оберіть найкращий варіант
"
        "⭐ Після виконання оцініть роботу

"
        "💡 Чим точніше опис і фото — тим швидше вам допоможуть"
    )


def master_help_text() -> str:
    return (
        "🔧 <b>Як працювати з заявками</b>

"
        "1. Пройдіть реєстрацію майстра
"
        "2. Дочекайтесь підтвердження
"
        "3. Відкрийте <b>📦 Нові заявки</b>
"
        "4. Оберіть заявку та натисніть <b>📨 Відгукнутись</b>
"
        "5. Вкажіть ціну та час виконання
"
        "6. Додайте короткий коментар

"
        "📞 Якщо клієнт обере вас — відкриються контакти
"
        "💬 Зв'яжіться з клієнтом та виконайте роботу
"
        "🏁 Після завершення закрийте заявку

"
        "💡 Швидкий і чіткий відгук підвищує шанс отримати замовлення"
    )


def register(dp):
    @dp.message_handler(lambda m: m.text == "ℹ️ Як користуватись", state="*")
    async def open_help(message: types.Message, state: FSMContext):
        await update_master_presence_if_needed(message.from_user.id)
        await message.answer(
            "ℹ️ <b>Інструкція користування</b>

"
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
