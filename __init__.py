from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import back_menu_kb, main_menu_kb
from repositories import add_complaint, add_support_message, approved_master_row, execute, touch_master_presence
from states import ComplaintWrite, RatingFlow, SupportReply, SupportWrite
from utils import is_admin, normalize_text


def register(dp):
    @dp.message_handler(state=SupportWrite.text)
    async def support_write(message: types.Message, state: FSMContext):
        text = normalize_text(message.text or "Без тексту", 2000) or "Без тексту"
        await add_support_message(message.from_user.id, text)
        await dp.bot.send_message(
            settings.admin_id,
            f"🆘 Повідомлення в підтримку\n\n👤 user_id: {message.from_user.id}\n📝 {text}",
            reply_markup=__import__("keyboards").support_reply_inline(message.from_user.id),
        )
        await state.finish()
        await message.answer("✅ Повідомлення відправлено адміністратору.", reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)))

    @dp.message_handler(state=SupportReply.text)
    async def support_reply_send(message: types.Message, state: FSMContext):
        data = await state.get_data()
        text = normalize_text(message.text, 2000)
        try:
            await dp.bot.send_message(data["support_target_user_id"], f"💬 Відповідь служби підтримки:\n\n{text}")
            await message.answer("✅ Відповідь надіслано.")
        except Exception as e:
            await message.answer(f"Не вдалося надіслати відповідь: {e}")
        await state.finish()

    @dp.message_handler(state=ComplaintWrite.text)
    async def complaint_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        text = normalize_text(message.text or "Без тексту", 2000) or "Без тексту"
        await add_complaint(data["complaint_order_id"], message.from_user.id, data["against_user_id"], data["against_role"], text)
        await dp.bot.send_message(
            settings.admin_id,
            f"⚠️ Нова скарга\n\n🆔 Заявка: {data['complaint_order_id']}\n👤 Від: {message.from_user.id}\n🎯 На кого: {data['against_user_id']} ({data['against_role']})\n📝 {text}",
        )
        await state.finish()
        await message.answer("✅ Скаргу відправлено адміністратору.", reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)))

    @dp.message_handler(state=RatingFlow.value)
    async def rating_value(message: types.Message, state: FSMContext):
        if (message.text or "").strip() not in ["1", "2", "3", "4", "5"]:
            await message.answer("Будь ласка, надішліть оцінку цифрою від 1 до 5.")
            return
        data = await state.get_data()
        rating_value = int(message.text)
        await execute(
            '''
            UPDATE masters
            SET rating = (rating * reviews_count + $1) / (reviews_count + 1),
                reviews_count = reviews_count + 1,
                updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT
            WHERE user_id=$2
            ''',
            rating_value, data["rating_master_user_id"]
        )
        await execute("UPDATE orders SET rating=$1 WHERE id=$2", rating_value, data["rating_order_id"])
        await state.update_data(rating_value=rating_value)
        await RatingFlow.next()
        await message.answer("📝 Напишіть короткий текстовий відгук або напишіть 'пропустити':", reply_markup=back_menu_kb())

    @dp.message_handler(state=RatingFlow.review)
    async def rating_review(message: types.Message, state: FSMContext):
        data = await state.get_data()
        text = None if (message.text or "").strip().lower() == "пропустити" else normalize_text(message.text or "", 2000)
        await execute("UPDATE orders SET review_text=$1 WHERE id=$2", text, data["rating_order_id"])
        await state.finish()
        await message.answer("✅ Дякуємо за відгук!", reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)))

    @dp.message_handler(lambda m: m.text == "⬅️ Назад", state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        current = await state.get_state()
        await state.finish()
        await message.answer("Головне меню:", reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)))

    @dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
    async def fallback(message: types.Message, state: FSMContext):
        if await approved_master_row(message.from_user.id):
            await touch_master_presence(message.from_user.id)
        if (message.text or "").startswith("/"):
            return
        current = await state.get_state()
        if not current:
            await message.answer("Скористайтесь меню нижче.", reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)))
            return
        await message.answer("Не зрозумів дію. Скористайтесь кнопками меню.", reply_markup=back_menu_kb())
