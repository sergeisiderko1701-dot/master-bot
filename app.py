import asyncio
import logging
import os
import hashlib
import asyncpg

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

LOCK_KEY = 987654321


async def main():
    token = settings.bot_token.strip()
    fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]

    logging.info(f"PID: {os.getpid()}")
    logging.info(f"BOT_TOKEN fingerprint: {fingerprint}")

    await init_db(settings.database_url)

    lock_conn = await asyncpg.connect(settings.database_url)
    row = await lock_conn.fetchrow(
        "SELECT pg_try_advisory_lock($1) AS locked",
        LOCK_KEY
    )

    if not row or not row["locked"]:
        logging.warning("Another instance already owns polling lock. Exiting.")
        await lock_conn.close()
        return

    logging.info("Polling lock acquired")

    bot = Bot(token=token, parse_mode="HTML")

    try:
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

        await dp.start_polling()

    finally:
        try:
            await bot.session.close()
        except Exception:
            pass

        try:
            await lock_conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
            await lock_conn.close()
        except Exception:
            pass

        logging.info("Bot session closed")


if __name__ == "__main__":
    asyncio.run(main())
