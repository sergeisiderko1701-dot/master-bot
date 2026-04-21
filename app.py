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
from aiogram.contrib.fsm_storage.redis import RedisStorage2
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
    Усі інстанси одного й того ж бота будуть боротися за один lock.
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


def build_storage():
    if settings.fsm_storage == "redis":
        logger.info(
            "Using Redis FSM storage: host=%s port=%s db=%s prefix=%s",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
            settings.redis_prefix,
        )
        return RedisStorage2(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            ssl=settings.redis_ssl,
            pool_size=settings.redis_pool_size,
            prefix=settings.redis_prefix,
            state_ttl=settings.redis_state_ttl or None,
            data_ttl=settings.redis_data_ttl or None,
            bucket_ttl=settings.redis_bucket_ttl or None,
        )

    logger.warning("Using MemoryStorage for FSM")
    return MemoryStorage()


async def safe_close_storage(dp: Dispatcher | None):
    if not dp or not dp.storage:
        return

    try:
        await dp.storage.close()
        await dp.storage.wait_closed()
        logger.info("Dispatcher storage closed")
    except Exception:
        logger.exception("Failed to close dispatcher storage")


async def safe_close_bot_session(bot: Bot | None):
    if not bot:
        return

    try:
        session = await bot.get_session()
        await session.close()
        logger.info("Bot session closed")
    except Exception:
        logger.exception("Failed to close bot session")


async def safe_release_lock(lock_conn, lock_key):
    if not lock_conn:
        return

    try:
        if lock_conn.is_closed():
            logger.warning("Lock connection already closed before unlock")
            return

        if lock_key is None:
            logger.warning("Lock key is missing, unlock skipped")
            return

        unlocked = await lock_conn.fetchval(
            "SELECT pg_advisory_unlock($1)",
            lock_key,
        )
        logger.info("Polling lock released: %s", unlocked)
    except Exception:
        logger.exception("Failed to release advisory lock")


async def safe_close_lock_conn(lock_conn):
    if not lock_conn:
        return

    try:
        if not lock_conn.is_closed():
            await lock_conn.close()
        logger.info("Lock connection closed")
    except Exception:
        logger.exception("Failed to close lock connection")


async def main():
    bot = None
    dp = None
    lock_conn = None
    polling_task = None
    shutdown_wait_task = None
    lock_key = None
    pg_backend_pid = None

    shutdown_event = asyncio.Event()

    def request_shutdown(signame: str) -> None:
        logger.warning("Received signal %s. Starting graceful shutdown...", signame)
        shutdown_event.set()

    try:
        settings.validate()

        token = settings.bot_token
        database_url = settings.database_url
        enable_polling = os.getenv("ENABLE_POLLING", "true").lower() == "true"

        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]
        lock_key = make_lock_key(token)

        logger.info("PID: %s", os.getpid())
        logger.info("HOSTNAME: %s", socket.gethostname())
        logger.info("APP_INSTANCE_NAME: %s", settings.app_instance_name or "<empty>")
        logger.info("BOT_TOKEN fingerprint: %s", fingerprint)
        logger.info("ENABLE_POLLING: %s", enable_polling)
        logger.info("LOCK_KEY: %s", lock_key)
        logger.info("FSM_STORAGE: %s", settings.fsm_storage)

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
        storage = build_storage()
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

        for task in pending:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if shutdown_event.is_set():
            logger.warning("Shutdown requested. Stopping polling task...")

            if polling_task and not polling_task.done():
                polling_task.cancel()
                with suppress(asyncio.CancelledError):
                    await polling_task

            logger.warning("Polling stopped.")

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

        await safe_close_storage(dp)
        await safe_close_bot_session(bot)
        await safe_release_lock(lock_conn, lock_key)
        await safe_close_lock_conn(lock_conn)

        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
