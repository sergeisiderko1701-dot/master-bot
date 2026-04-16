import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import TerminatedByOtherGetUpdates

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


async def start_bot(dp):
    while True:
        try:
            await dp.start_polling()
        except TerminatedByOtherGetUpdates:
            logging.warning("Another bot instance is still running. Waiting 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.exception(f"Unexpected polling error: {e}")
            await asyncio.sleep(5)


async def main():
    logging.info(f"PID: {os.getpid()}")
    logging.info(f"Bot token prefix: {settings.bot_token[:10]}")

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

    try:
        await start_bot(dp)
    finally:
        await bot.session.close()
        logging.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
