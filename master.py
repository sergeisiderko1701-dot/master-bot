from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import category_label
from keyboards import (
    back_menu_kb,
    edit_profile_inline_kb,
    main_menu_kb,
    master_categories_inline_kb,
    master_menu_kb,
)
from repositories import (
    approved_master_row,
    create_or_update_master,
    fetchrow,
    list_active_orders_for_master,
    list_new_orders_for_master,
    master_any_row,
    touch_master_presence,
    update_master_profile,
)
from services import send_master_card, send_order_card
from states import MasterRegistration, ProfileEdit
from utils import is_admin, normalize_text
from ui_texts import ask_district_text


PROFILE_FIELD_MAP = {
    "name": "name",
    "district": "district",
    "phone": "phone",
    "description": "description",
    "experience": "experience",
    "photo": "photo",
}


def register(dp):
    @dp.message_handler(lambda m: m.text in ["🔧 Майстер", "🔧 Я майстер"], state="*")
    async def master_entry(message: types.Message, state: FSMContext):
        await state.finish()
        master = await master_any_row(message.from_user.id)

        if master and master["status"] == "approved":
            await touch_master_presence(message.from_user.id)
            await show_master_profile(message, master)
            return

        if master and master["status"] == "pending":
            await message.answer("Ваша заявка вже на модерації.", reply_markup=back_menu_kb())
            return

        if master and master["status"] == "blocked":
            await message.answer(
                "Ваш профіль майстра заблокований. Зверніться в підтримку.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
            )
            return

        await MasterRegistration.name.set()
        await message.answer(
            "👤 <b>Реєстрація майстра</b>\n\nВведіть ваше ім'я:",
            reply_markup=back_menu_kb()
        )

    async def show_master_profile(message: types.Message, master_row):
        text = (
            f"👤 Ваш профіль майстра\n\n"
            f"👤 Ім'я: {master_row['name']}\n"
            f"🔧 Категорія: {category_label(master_row['category'])}\n"
            f"📍 Район: {master_row['district'] or '-'}\n"
            f"📞 Телефон: {master_row['phone']}\n"
            f"🧾 Про себе: {master_row['description'] or '-'}\n"
            f"🛠 Досвід: {master_row['experience'] or '-'}\n"
            f"⭐ Рейтинг: {float(master_row['rating']):.2f}\n"
            f"💬 Відгуків: {master_row['reviews_count']}\n"
            f"🟢 Статус: {master_row['availability']}"
        )

        if master_row["photo"]:
            try:
                await dp.bot.send_photo(message.chat.id, master_row["photo"], caption=text)
            except Exception:
                await message.answer(text)
        else:
            await message.answer(text)

        await message.answer("👇 <b>Меню майстра</b>", reply_markup=master_menu_kb())

    @dp.message_handler(state=MasterRegistration.name)
    async def reg_name(message: types.Message, state: FSMContext):
        await state.update_data(name=normalize_text(message.text, 120))
        await MasterRegistration.next()
        await message.answer("🔧 Оберіть спеціальність кнопкою:", reply_markup=back_menu_kb())
        await message.answer("Категорії:", reply_markup=master_categories_inline_kb())

    @dp.callback_query_handler(lambda c: c.data.startswith("master_cat_"), state=MasterRegistration.category)
    async def reg_category(call: types.CallbackQuery, state: FSMContext):
        await state.update_data(category=call.data.split("master_cat_", 1)[1])
        await MasterRegistration.next()
        await call.message.answer(ask_district_text(), reply_markup=back_menu_kb())
        await call.answer()

    @dp.message_handler(state=MasterRegistration.district)
    async def reg_district(message: types.Message, state: FSMContext):
        await state.update_data(district=normalize_text(message.text, 255))
        await MasterRegistration.next()
        await message.answer(
            "🧾 <b>Коротко про себе</b>\n\nНапишіть кілька речень про ваш досвід і спеціалізацію.",
            reply_markup=back_menu_kb()
        )

    @dp.message_handler(state=MasterRegistration.description)
    async def reg_description(message: types.Message, state: FSMContext):
        await state.update_data(description=normalize_text(message.text, 1000))
        await MasterRegistration.next()
        await message.answer(
            "🛠 <b>Досвід роботи</b>\n\nНапишіть, з чим саме допомагаєте клієнтам.",
            reply_markup=back_menu_kb()
        )

    @dp.message_handler(state=MasterRegistration.experience)
    async def reg_experience(message: types.Message, state: FSMContext):
        await state.update_data(experience=normalize_text(message.text, 1000))
        await MasterRegistration.next()
        await message.answer(
            "📞 <b>Контактний телефон</b>\n\nВведіть номер у зручному форматі.",
            reply_markup=back_menu_kb()
        )

    @dp.message_handler(state=MasterRegistration.phone)
    async def reg_phone(message: types.Message, state: FSMContext):
        await state.update_data(phone=normalize_text(message.text, 50))
        await MasterRegistration.next()
        await message.answer(
            "📸 <b>Фото профілю</b>\n\nНадішліть фото або напишіть <b>пропустити</b>.",
            reply_markup=back_menu_kb()
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=MasterRegistration.photo)
    async def reg_photo(message: types.Message, state: FSMContext):
        text = (message.text or "").strip().lower()
        photo = message.photo[-1].file_id if message.photo else None

        if not photo and text != "пропустити":
            await message.answer("Надішліть фото або напишіть 'пропустити'.", reply_markup=back_menu_kb())
            return

        data = await state.get_data()
        data["user_id"] = message.from_user.id
        data["photo"] = photo
        await create_or_update_master(data)

        master_row = await fetchrow("SELECT * FROM masters WHERE user_id=$1", message.from_user.id)
        await send_master_card(dp.bot, settings.admin_id, master_row, title="📝 Нова заявка майстра")

        await state.finish()
        await message.answer(
            "⏳ <b>Заявку надіслано</b>\n\nПісля перевірки адміністратор активує ваш профіль.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
        )

    @dp.message_handler(lambda m: m.text == "👤 Мій профіль", state="*")
    async def profile(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "Профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
            )
            return
        await show_master_profile(message, master)

    @dp.message_handler(lambda m: m.text == "✏️ Редагувати профіль", state="*")
    async def edit_profile(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "Профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
            )
            return

        await message.answer("Оберіть, що хочете змінити:", reply_markup=back_menu_kb())
        await message.answer("Поля профілю:", reply_markup=edit_profile_inline_kb())

    @dp.callback_query_handler(lambda c: c.data.startswith("edit_"), state="*")
    async def edit_profile_field(call: types.CallbackQuery, state: FSMContext):
        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Профіль недоступний", show_alert=True)
            return

        field = call.data.replace("edit_", "", 1)
        if field not in PROFILE_FIELD_MAP:
            await call.answer()
            return

        await state.update_data(edit_field=field)
        await ProfileEdit.value.set()

        prompt = "Надішліть нове значення:" if field != "photo" else "Надішліть нове фото або напишіть 'пропустити':"
        await call.message.answer(prompt, reply_markup=back_menu_kb())
        await call.answer()

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ProfileEdit.value)
    async def edit_profile_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        field = data["edit_field"]

        if field == "photo":
            value = message.photo[-1].file_id if message.photo else None
            if not value and (message.text or "").strip().lower() != "пропустити":
                await message.answer("Надішліть фото або напишіть 'пропустити'.", reply_markup=back_menu_kb())
                return
        else:
            value = normalize_text(message.text, 1000)
            if not value:
                await message.answer("Надішліть текстове значення.", reply_markup=back_menu_kb())
                return

        await update_master_profile(message.from_user.id, PROFILE_FIELD_MAP[field], value)
        await state.finish()
        await message.answer("✅ Профіль оновлено.", reply_markup=master_menu_kb())

    @dp.message_handler(lambda m: m.text == "📦 Нові заявки", state="*")
    async def new_orders(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "❌ Ви не підтверджений майстер.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id))
            )
            return

        rows = await list_new_orders_for_master(master["category"])
        if not rows:
            await message.answer("Наразі нових заявок у вашій категорії немає.", reply_markup=master_menu_kb())
            return

        await message.answer(f"📦 Нові заявки ({category_label(master['category'])}):", reply_markup=master_menu_kb())

        from keyboards import order_card_master_actions
        for row in rows:
            await send_order_card(
                dp.bot,
                message.chat.id,
                row,
                title="📢 Доступна заявка",
                reply_markup=order_card_master_actions(row["id"])
            )

    @dp.message_handler(lambda m: m.text == "💬 Активні чати", state="*")
    async def active_orders(message: types.Message, state: FSMContext):
        rows = await list_active_orders_for_master(message.from_user.id)
        if not rows:
            await message.answer("У вас немає активних заявок.", reply_markup=master_menu_kb())
            return

        await message.answer("✅ Ваші активні заявки:", reply_markup=master_menu_kb())

        from keyboards import selected_order_master_actions
        for row in rows:
            await send_order_card(
                dp.bot,
                message.chat.id,
                row,
                title="📄 Активна заявка",
                reply_markup=selected_order_master_actions(row["id"])
            )
