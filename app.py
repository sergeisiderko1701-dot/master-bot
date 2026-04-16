import asyncio
import logging
import os
import hashlib

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


async def main():
    token = settings.bot_token.strip()
    fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]

    logging.info(f"PID: {os.getpid()}")
    logging.info(f"BOT_TOKEN fingerprint: {fingerprint}")

    await init_db(settings.database_url)

    bot = Bot(token=token, parse_mode="HTML")

    me = await bot.get_me()
    logging.info(f"Running as bot: @{me.username} (id={me.id})")

    await bot.delete_webhook(drop_pending_updates=True)

    dp = Dispatcher(bot, storage=MemoryStorage())

    client.register(dp)
    master.register(dp)
    offers.register(dp)
    chat.register(dp)
    admin.register(dp)
    misc.register(dp)

    logging.info("Bot starting...")
    logging.info("Start polling.")

    try:
        await dp.start_polling()
    except TerminatedByOtherGetUpdates:
        logging.exception("Another getUpdates client is using this same token")
        raise
    finally:
        await bot.session.close()
        logging.info("Bot session closed")


if __name__ == "__main__":
    asyncio.run(main())
