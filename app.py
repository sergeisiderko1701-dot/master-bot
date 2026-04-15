import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import settings
from db import init_db

import admin
import chat
import client
import master
import misc
import offers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def main():
    await init_db(settings.database_url)

    bot = Bot(token=settings.bot_token, parse_mode="HTML")
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(bot, storage=MemoryStorage())

    client.register(dp)
    master.register(dp)
    offers.register(dp)
    chat.register(dp)
    admin.register(dp)
    misc.register(dp)

    logging.info("Bot starting...")
    await dp.start_polling()


if __name__ == "__main__":
    asyncio.run(main())
