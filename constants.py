import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import settings
from db import init_db
from handlers import admin, chat, client, common, master, misc, offers


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


async def main():
    await init_db(settings.database_url)

    bot = Bot(token=settings.bot_token, parse_mode="HTML")
    dp = Dispatcher(bot, storage=MemoryStorage())

    common.register(dp)
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
