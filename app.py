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


def make_lock_key(token: str, instance_name: str = "") -> int:
    raw = f"{instance_name}:{token}".encode()
    digest = hashlib.sha256(raw).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


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
    lock_key = None

    try:
        token = settings.bot_token.strip()
        if not token:
            raise ValueError("BOT_TOKEN is empty")

        if not settings.database_url:
            raise ValueError("DATABASE_URL is empty")

        fingerprint = hashlib.sha256(token.encode()).hexdigest()[:12]
        lock_key = make_lock_key(token, settings.app_instance_name or "")

        logger.info("PID: %s", os.getpid())
        logger.info("BOT_TOKEN fingerprint: %s", fingerprint)
        logger.info("APP_INSTANCE_NAME: %s", settings.app_instance_name)
        logger.info("HOSTNAME: %s", socket.gethostname())
        logger.info("LOCK_KEY: %s", lock_key)

        logger.info("Connecting to PostgreSQL for advisory lock...")
        lock_conn = await asyncpg.connect(settings.database_url)

        pg_pid = await lock_conn.fetchval("SELECT pg_backend_pid()")
        logger.info("Lock connection backend pid: %s", pg_pid)

        locked = await lock_conn.fetchval(
            "SELECT pg_try_advisory_lock($1)",
            lock_key,
        )

        if not locked:
            logger.error("Another instance already owns polling lock. Exit.")
            raise SystemExit(1)

        logger.info("Polling lock acquired")

        logger.info("Initializing database...")
        await init_db(settings.database_url)
        logger.info("Database initialized")

        bot = Bot(token=token, parse_mode="HTML")
        storage = MemoryStorage()
        dp = Dispatcher(bot, storage=storage)

        me = await bot.get_me()
        logger.info("Running as bot: @%s (id=%s)", me.username, me.id)

        await bot.delete_webhook(drop_pending_updates=False)

        register_handlers(dp)

        logger.info("Bot starting polling...")
        await dp.start_polling()

    except TerminatedByOtherGetUpdates:
        logger.exception("Telegram reported another active polling instance")
        raise SystemExit(1)

    except SystemExit:
        raise

    except Exception:
        logger.exception("Fatal error while starting bot")
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
                if lock_key is not None:
                    await lock_conn.execute(
                        "SELECT pg_advisory_unlock($1)",
                        lock_key,
                    )
            except Exception:
                logger.exception("Failed to release advisory lock")

            try:
                await lock_conn.close()
            except Exception:
                logger.exception("Failed to close lock connection")

        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
