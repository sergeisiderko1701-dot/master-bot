from aiogram import types
from aiogram.dispatcher import FSMContext
import asyncpg

from config import settings
from keyboards import back_menu_kb, main_menu_kb, master_menu_kb
from repositories import (
    approved_master_row,
    choose_offer,
    create_offer,
    fetchrow,
    get_cooldown,
    get_order_row,
    master_active_orders_count,
    set_cooldown,
)
from states import OfferCreate, RatingFlow, ComplaintWrite
from utils import is_admin, normalize_text, now_ts


def register(dp):
    @dp.callback_query_handler(lambda c: c.data.startswith("offer_start_"), state="*")
    async def offer_start(call: types.CallbackQuery, state: FSMContext):
        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Ви не підтверджений майстер", show_alert=True)
            return

        if await master_active_orders_count(call.from_user.id) >= settings.max_active_master_orders:
            await call.answer("У вас уже забагато активних заявок", show_alert=True)
            return

        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order or order["category"] != master["category"] or order["status"] not in ["new", "offered"]:
            await call.answer("Заявка вже недоступна", show_alert=True)
            return

        prev = await get_cooldown(call.from_user.id, "master_offer")
        current = now_ts()
        if current - prev < settings.master_offer_cooldown:
            await call.answer("Зачекайте перед новим відгуком", show_alert=True)
            return

        await state.update_data(order_id=order_id)
        await OfferCreate.price.set()
        await call.message.answer("💰 <b>Ваш офер</b>\n\nВкажіть вашу ціну.", reply_markup=back_menu_kb())
        await call.answer()

    @dp.message_handler(state=OfferCreate.price)
    async def offer_price(message: types.Message, state: FSMContext):
        await state.update_data(price=normalize_text(message.text, 100))
        await OfferCreate.next()
        await message.answer("⏱ <b>Коли зможете взятись?</b>\n\nНапишіть час текстом.", reply_markup=back_menu_kb())

    @dp.message_handler(state=OfferCreate.eta)
    async def offer_eta(message: types.Message, state: FSMContext):
        await state.update_data(eta=normalize_text(message.text, 100))
        await OfferCreate.next()
        await message.answer("📝 <b>Коментар до оферу</b>\n\nКоротко опишіть, що входить у вашу пропозицію.", reply_markup=back_menu_kb())

    @dp.message_handler(state=OfferCreate.comment)
    async def offer_comment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_id = int(data["order_id"])
        comment = normalize_text(message.text, 1000) or "-"
        try:
            await create_offer(order_id, message.from_user.id, data["price"], data["eta"], comment)
            await set_cooldown(message.from_user.id, "master_offer", now_ts())
        except asyncpg.UniqueViolationError:
            await state.finish()
            await message.answer("❌ Ви вже відгукнулися на цю заявку.", reply_markup=master_menu_kb())
            return

        order = await get_order_row(order_id)
        await state.finish()
        await message.answer("✅ <b>Пропозицію надіслано клієнту</b>", reply_markup=master_menu_kb())
        try:
            await dp.bot.send_message(
                order["user_id"],
                f"📬 На вашу заявку #{order_id} надійшла нова пропозиція від майстра.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(order["user_id"]))
            )
        except Exception:
            pass

    @dp.callback_query_handler(lambda c: c.data.startswith("choose_offer_"), state="*")
    async def choose_offer_handler(call: types.CallbackQuery, state: FSMContext):
        offer_id = int(call.data.split("_")[-1])
        offer = await choose_offer(offer_id, call.from_user.id)
        if not offer:
            await call.answer("Пропозиція недоступна", show_alert=True)
            return
        await call.message.answer("🎉 <b>Майстра обрано</b>\n\nТепер можна обговорити деталі в чаті 💬")
        try:
            await dp.bot.send_message(offer["master_user_id"], f"🎉 Вас обрали по заявці #{offer['order_id']}.", reply_markup=master_menu_kb())
        except Exception:
            pass
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("finish_order_"), state="*")
    async def finish_order(call: types.CallbackQuery, state: FSMContext):
        from repositories import finish_order as finish_order_repo
        order_id = int(call.data.split("_")[-1])
        order = await fetchrow(
            "SELECT * FROM orders WHERE id=$1 AND selected_master_id=$2 AND status = ANY($3::text[])",
            order_id, call.from_user.id, ['matched', 'in_progress']
        )
        if not order:
            await call.answer("Заявка недоступна", show_alert=True)
            return
        await finish_order_repo(order_id)
        await call.message.answer("✅ Заявку завершено.")
        await state.update_data(rating_order_id=order_id, rating_master_user_id=call.from_user.id)
        await RatingFlow.value.set()
        await dp.bot.send_message(order["user_id"], "⭐ Оцініть майстра цифрою від 1 до 5")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("refuse_order_"), state="*")
    async def refuse_order(call: types.CallbackQuery, state: FSMContext):
        from repositories import refuse_order as refuse_order_repo
        order_id = int(call.data.split("_")[-1])
        order = await fetchrow(
            "SELECT * FROM orders WHERE id=$1 AND selected_master_id=$2 AND status = ANY($3::text[])",
            order_id, call.from_user.id, ['matched', 'in_progress']
        )
        if not order:
            await call.answer("Заявка недоступна", show_alert=True)
            return
        await refuse_order_repo(order_id)
        try:
            await dp.bot.send_message(order["user_id"], f"⚠️ Майстер відмовився від заявки #{order_id}.")
        except Exception:
            pass
        await call.message.answer("✅ Ви відмовились від заявки.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("client_cancel_"), state="*")
    async def client_cancel(call: types.CallbackQuery, state: FSMContext):
        from repositories import cancel_order
        order_id = int(call.data.split("_")[-1])
        order = await fetchrow(
            "SELECT * FROM orders WHERE id=$1 AND user_id=$2 AND status = ANY($3::text[])",
            order_id, call.from_user.id, ['new', 'offered', 'matched']
        )
        if not order:
            await call.answer("Заявку не можна скасувати", show_alert=True)
            return
        await cancel_order(order_id)
        if order["selected_master_id"]:
            try:
                await dp.bot.send_message(order["selected_master_id"], f"❌ Клієнт скасував заявку #{order_id}.")
            except Exception:
                pass
        await call.message.answer("✅ Заявку скасовано.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("complain_master_"), state="*")
    async def complain_master(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order or order["user_id"] != call.from_user.id or not order["selected_master_id"]:
            await call.answer("Скарга недоступна", show_alert=True)
            return
        await state.update_data(complaint_order_id=order_id, against_user_id=order["selected_master_id"], against_role="master")
        await ComplaintWrite.text.set()
        await call.message.answer("Напишіть текст скарги на майстра:", reply_markup=back_menu_kb())
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("complain_client_"), state="*")
    async def complain_client(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order or order["selected_master_id"] != call.from_user.id:
            await call.answer("Скарга недоступна", show_alert=True)
            return
        await state.update_data(complaint_order_id=order_id, against_user_id=order["user_id"], against_role="client")
        await ComplaintWrite.text.set()
        await call.message.answer("Напишіть текст скарги на клієнта:", reply_markup=back_menu_kb())
        await call.answer()
