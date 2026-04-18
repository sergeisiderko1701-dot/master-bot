import asyncio
import hashlib
import logging
import os
import signal
import socket
from contextlib import suppress

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


def make_lock_key(token: str) -> int:
    """
    Генерує стабільний advisory lock key лише з BOT_TOKEN.
    Це важливо, щоб усі інстанси одного й того ж бота
    боролися за один і той самий lock.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


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
    storage = None
    lock_conn = None
    polling_task = None
    shutdown_wait_task = None
    lock_key = None

    shutdown_event = asyncio.Event()

    def request_shutdown(signame: str) -> None:
        logger.warning("Received signal %s. Starting graceful shutdown...", signame)
        shutdown_event.set()

    try:
        token = settings.bot_token.strip()
        if not token:
            raise ValueError("BOT_TOKEN is empty")

        database_url = settings.database_url
        if not database_url:
            raise ValueError("DATABASE_URL is empty")

        enable_polling = os.getenv("ENABLE_POLLING", "true").lower() == "true"

        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
        lock_key = make_lock_key(token)

        logger.info("PID: %s", os.getpid())
        logger.info("HOSTNAME: %s", socket.gethostname())
        logger.info("APP_INSTANCE_NAME: %s", (settings.app_instance_name or "").strip() or "<empty>")
        logger.info("BOT_TOKEN fingerprint: %s", fingerprint)
        logger.info("ENABLE_POLLING: %s", enable_polling)
        logger.info("LOCK_KEY: %s", lock_key)

        if not enable_polling:
            logger.warning("Polling disabled for this instance. Exiting without polling.")
            return

        logger.info("Connecting to PostgreSQL for polling lock...")
        lock_conn = await asyncpg.connect(database_url)

        pg_backend_pid = await lock_conn.fetchval("SELECT pg_backend_pid()")
        logger.info("PostgreSQL backend pid for lock connection: %s", pg_backend_pid)

        locked = await lock_conn.fetchval(
            "SELECT pg_try_advisory_lock($1)",
            lock_key,
        )

        if not locked:
            logger.error(
                "Polling lock is already held by another instance. "
                "This instance will exit. PID=%s HOST=%s",
                os.getpid(),
                socket.gethostname(),
            )
            raise SystemExit(1)

        logger.info("Polling lock acquired successfully")

        logger.info("Initializing database...")
        await init_db(database_url)
        logger.info("Database initialized")

        bot = Bot(token=token, parse_mode="HTML")
        storage = MemoryStorage()
        dp = Dispatcher(bot, storage=storage)

        register_handlers(dp)

        me = await bot.get_me()
        logger.info(
            "Authorized as bot: @%s (id=%s). PID=%s HOST=%s",
            me.username,
            me.id,
            os.getpid(),
            socket.gethostname(),
        )

        logger.info("Deleting webhook without dropping pending updates...")
        await bot.delete_webhook(drop_pending_updates=False)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, request_shutdown, sig.name)

        logger.info(
            "Starting polling. PID=%s HOST=%s PG_PID=%s",
            os.getpid(),
            socket.gethostname(),
            pg_backend_pid,
        )

        polling_task = asyncio.create_task(dp.start_polling())
        shutdown_wait_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            {polling_task, shutdown_wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if shutdown_event.is_set():
            logger.warning("Shutdown requested. Stopping polling task...")

            if polling_task and not polling_task.done():
                polling_task.cancel()
                with suppress(asyncio.CancelledError):
                    await polling_task

        else:
            if polling_task in done:
                exc = polling_task.exception()
                if exc:
                    raise exc

    except TerminatedByOtherGetUpdates:
        logger.exception(
            "Telegram reported conflict: another active polling instance exists. "
            "Make sure only one instance with this BOT_TOKEN is running. "
            "PID=%s HOST=%s",
            os.getpid(),
            socket.gethostname(),
        )
        raise SystemExit(1)

    except SystemExit:
        raise

    except asyncio.CancelledError:
        logger.warning("Main task cancelled")
        raise

    except Exception:
        logger.exception(
            "Fatal error while starting/running bot. PID=%s HOST=%s",
            os.getpid(),
            socket.gethostname(),
        )
        raise

    finally:
        logger.info("Shutting down bot...")

        if shutdown_wait_task and not shutdown_wait_task.done():
            shutdown_wait_task.cancel()
            with suppress(asyncio.CancelledError):
                await shutdown_wait_task

        if polling_task and not polling_task.done():
            polling_task.cancel()
            with suppress(asyncio.CancelledError):
                await polling_task

        if dp and dp.storage:
            try:
                await dp.storage.close()
                await dp.storage.wait_closed()
                logger.info("Dispatcher storage closed")
            except Exception:
                logger.exception("Failed to close dispatcher storage")

        if bot:
            try:
                session = await bot.get_session()
                await session.close()
                logger.info("Bot session closed")
            except Exception:
                logger.exception("Failed to close bot session")

        if lock_conn:
            try:
                if not lock_conn.is_closed() and lock_key is not None:
                    unlocked = await lock_conn.fetchval(
                        "SELECT pg_advisory_unlock($1)",
                        lock_key,
                    )
                    logger.info("Polling lock released: %s", unlocked)
                else:
                    logger.warning("Lock connection already closed before unlock")
            except Exception:
                logger.exception("Failed to release advisory lock")

            try:
                if not lock_conn.is_closed():
                    await lock_conn.close()
                logger.info("Lock connection closed")
            except Exception:
                logger.exception("Failed to close lock connection")

        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
