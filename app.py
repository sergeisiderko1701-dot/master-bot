import asyncio
import hashlib
import logging
import os
import socket

import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import TerminatedByOtherGetUpdates

import admin
import client
import common
import master
import misc
import offers
from config import settings
from db import init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

LOCK_KEY = 987654321


def register_handlers(dp: Dispatcher) -> None:
    client.register(dp)
    master.register(dp)
    offers.register(dp)
    admin.register(dp)
    misc.register(dp)
    common.register(dp)


async def main():
    bot = None
    dp = None
    lock_conn = None

    try:
        token = settings.bot_token.strip()
        if not token:
            raise ValueError("BOT_TOKEN is empty")

        if not settings.database_url:
            raise ValueError("DATABASE_URL is empty")

        fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]

        logger.info("PID: %s", os.getpid())
        logger.info("BOT_TOKEN fingerprint: %s", fingerprint)
        logger.info("APP_INSTANCE_NAME: %s", settings.app_instance_name)
        logger.info("HOSTNAME: %s", socket.gethostname())

        logger.info("Initializing database...")
        await init_db(settings.database_url)
        logger.info("Database initialized")

        logger.info("Connecting to PostgreSQL for advisory lock...")
        lock_conn = await asyncpg.connect(settings.database_url)

        row = await lock_conn.fetchrow(
            "SELECT pg_try_advisory_lock($1) AS locked",
            LOCK_KEY
        )

        if not row or not row["locked"]:
            logger.error("Another instance already owns polling lock. Force exit.")
            raise SystemExit(1)

        logger.info("Polling lock acquired")

        bot = Bot(token=token, parse_mode="HTML")
        storage = MemoryStorage()
        dp = Dispatcher(bot, storage=storage)

        me = await bot.get_me()
        logger.info("Running as bot: @%s (id=%s)", me.username, me.id)

        await bot.delete_webhook(drop_pending_updates=True)

        register_handlers(dp)

        logger.info("Bot starting polling...")
        logger.info("Start polling.")

        try:
            await dp.start_polling()
        except TerminatedByOtherGetUpdates:
            logger.error("Another Telegram polling instance detected. Force exit.")
            raise SystemExit(1)

    except SystemExit:
        raise

    except Exception as e:
        logger.exception("Fatal error while starting bot: %s", e)
        raise

    finally:
        logger.info("Shutting down bot...")

        if dp and dp.storage:
            try:
                await dp.storage.close()
                await dp.storage.wait_closed()
            except Exception:
                logger.exception("Failed to close dispatcher storage")

        if bot:
            try:
                await bot.session.close()
            except Exception:
                logger.exception("Failed to close bot session")

        if lock_conn:
            try:
                await lock_conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
            except Exception:
                logger.exception("Failed to release advisory lock")

            try:
                await lock_conn.close()
            except Exception:
                logger.exception("Failed to close lock connection")

        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
