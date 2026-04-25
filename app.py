import asyncio
import hashlib
import logging
import os
import signal
import socket
from contextlib import suppress

import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.utils.exceptions import (
    BotBlocked,
    ChatNotFound,
    ConflictError,
    InvalidQueryID,
    MessageCantBeDeleted,
    MessageNotModified,
    RetryAfter,
    TelegramAPIError,
    TerminatedByOtherGetUpdates,
    UserDeactivated,
)

import admin
import admin_chat
import order_reopen_notify_fix
import client
import common
import master
import misc
import offers
from config import settings
from db import init_db
from monitoring import stale_orders_watcher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


class DuplicatePollingDetected(RuntimeError):
    pass


def make_lock_key(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def register_handlers(dp: Dispatcher) -> None:
    client.register(dp)
    master.register(dp)
    admin_chat.register(dp)  # must be before order_reopen_notify_fix.register(dp)
    offers.register(dp) to let admin intercept chat_history_ callbacks
    offers.register(dp)
    admin.register(dp)
    misc.register(dp)
    common.register(dp)


def register_error_handlers(dp: Dispatcher) -> None:
    @dp.errors_handler()
    async def global_error_handler(update, error):
        logger.exception("UNHANDLED ERROR | update=%r", update)

        if isinstance(
            error,
            (
                MessageNotModified,
                MessageCantBeDeleted,
                InvalidQueryID,
                BotBlocked,
                ChatNotFound,
                UserDeactivated,
            ),
        ):
            return True

        if isinstance(error, RetryAfter):
            logger.warning("Telegram flood control: retry after %s sec", error.timeout)
            return True

        try:
            if isinstance(update, types.Update):
                if update.callback_query:
                    with suppress(Exception):
                        await update.callback_query.answer(
                            "⚠️ Сталася технічна помилка. Спробуйте ще раз.",
                            show_alert=True,
                        )
                    with suppress(Exception):
                        await update.callback_query.message.answer(
                            "⚠️ Сталася технічна помилка. Спробуйте ще раз через кілька секунд."
                        )
                elif update.message:
                    with suppress(Exception):
                        await update.message.answer(
                            "⚠️ Сталася технічна помилка. Спробуйте ще раз через кілька секунд."
                        )
        except Exception:
            logger.exception("Failed to notify user about error")

        return True


async def ensure_redis_available() -> None:
    from redis.asyncio import Redis

    redis = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        ssl=settings.redis_ssl,
        decode_responses=True,
    )

    try:
        pong = await redis.ping()
        if not pong:
            raise RuntimeError("Redis ping returned falsy result")
        logger.info(
            "Redis connection OK: host=%s port=%s db=%s",
            settings.redis_host,
            settings.redis_port,
            settings.redis_db,
        )
    finally:
        with suppress(Exception):
            await redis.aclose()


def build_storage():
    if settings.fsm_storage != "redis":
        raise RuntimeError(
            "FSM_STORAGE must be set to 'redis'. MemoryStorage is disabled in this build."
        )

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


async def safe_release_lock(lock_conn: asyncpg.Connection | None, lock_key: int | None):
    if not lock_conn or lock_key is None:
        return
    try:
        if lock_conn.is_closed():
            logger.warning("Lock connection already closed before unlock")
            return
        unlocked = await lock_conn.fetchval(
            "SELECT pg_advisory_unlock($1)",
            lock_key,
        )
        logger.info("Polling lock released: %s", unlocked)
    except Exception:
        logger.exception("Failed to release advisory lock")


async def safe_close_lock_conn(lock_conn: asyncpg.Connection | None):
    if not lock_conn:
        return
    try:
        if not lock_conn.is_closed():
            await lock_conn.close()
        logger.info("Lock connection closed")
    except Exception:
        logger.exception("Failed to close lock connection")


async def acquire_polling_lock(database_url: str, lock_key: int) -> asyncpg.Connection:
    logger.info("Connecting to PostgreSQL for polling lock...")
    conn = await asyncpg.connect(database_url)

    pg_backend_pid = await conn.fetchval("SELECT pg_backend_pid()")
    logger.info("PostgreSQL backend pid for lock connection: %s", pg_backend_pid)

    locked = await conn.fetchval("SELECT pg_try_advisory_lock($1)", lock_key)
    if not locked:
        await conn.close()
        raise DuplicatePollingDetected("Polling lock is already held by another instance")

    logger.info("Polling lock acquired successfully")
    return conn


async def hard_fail_on_duplicate_polling(bot: Bot):
    logger.info("Deleting webhook without dropping pending updates...")
    await bot.delete_webhook(drop_pending_updates=False)

    try:
        await bot.get_updates(timeout=1, limit=1)
    except (TerminatedByOtherGetUpdates, ConflictError) as e:
        raise DuplicatePollingDetected(f"Duplicate polling detected during preflight: {e}") from e


async def run_polling_loop(bot: Bot, dp: Dispatcher, shutdown_event: asyncio.Event):
    logger.info("Start polling.")
    offset = None

    while not shutdown_event.is_set():
        try:
            updates = await bot.get_updates(
                offset=offset,
                timeout=20,
                limit=100,
            )

            if not updates:
                continue

            offset = updates[-1].update_id + 1
            await dp.process_updates(updates, fast=True)

        except (TerminatedByOtherGetUpdates, ConflictError) as e:
            logger.exception(
                "Telegram reported polling conflict: another active instance exists."
            )
            shutdown_event.set()
            raise DuplicatePollingDetected(str(e)) from e

        except RetryAfter as e:
            logger.warning("RetryAfter from Telegram: sleep %s sec", e.timeout)
            await asyncio.sleep(e.timeout)

        except TelegramAPIError:
            logger.exception("Telegram API error in polling loop")
            await asyncio.sleep(3)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Unexpected polling loop error")
            await asyncio.sleep(3)

    logger.warning("Polling loop stopped")


async def main():
    bot = None
    dp = None
    lock_conn = None
    polling_task = None
    shutdown_wait_task = None
    monitoring_task = None
    lock_key = None

    shutdown_event = asyncio.Event()

    def request_shutdown(signame: str) -> None:
        logger.warning("Received signal %s. Starting graceful shutdown...", signame)
        shutdown_event.set()

    try:
        settings.validate()

        token = (settings.bot_token or "").strip()
        database_url = (settings.database_url or "").strip()
        enable_polling = os.getenv("ENABLE_POLLING", "true").lower() == "true"

        if not token:
            raise ValueError("BOT_TOKEN is empty")
        if not database_url:
            raise ValueError("DATABASE_URL is empty")

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

        logger.info("Checking Redis availability before startup...")
        await ensure_redis_available()

        lock_conn = await acquire_polling_lock(database_url, lock_key)

        logger.info("Initializing database...")
        await init_db(database_url)
        logger.info("Database initialized")

        bot = Bot(token=token, parse_mode="HTML")
        Bot.set_current(bot)

        storage = build_storage()
        dp = Dispatcher(bot, storage=storage)
        Dispatcher.set_current(dp)

        register_handlers(dp)
        register_error_handlers(dp)

        me = await bot.get_me()
        logger.info(
            "Authorized as bot: @%s (id=%s). PID=%s HOST=%s",
            me.username,
            me.id,
            os.getpid(),
            socket.gethostname(),
        )

        await hard_fail_on_duplicate_polling(bot)

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with suppress(NotImplementedError):
                loop.add_signal_handler(sig, request_shutdown, sig.name)

        pg_backend_pid = await lock_conn.fetchval("SELECT pg_backend_pid()")
        logger.info(
            "Starting polling. PID=%s HOST=%s PG_PID=%s",
            os.getpid(),
            socket.gethostname(),
            pg_backend_pid,
        )

        polling_task = asyncio.create_task(run_polling_loop(bot, dp, shutdown_event), name="polling_task")
        monitoring_task = asyncio.create_task(stale_orders_watcher(bot, shutdown_event), name="monitoring_task")
        shutdown_wait_task = asyncio.create_task(shutdown_event.wait(), name="shutdown_wait_task")

        done, pending = await asyncio.wait(
            {polling_task, monitoring_task, shutdown_wait_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in done:
            if task is shutdown_wait_task:
                continue
            exc = task.exception()
            if exc:
                raise exc

        if shutdown_event.is_set():
            logger.warning("Shutdown requested. Stopping tasks...")

        for task in pending:
            task.cancel()

        for task in pending:
            with suppress(asyncio.CancelledError):
                await task

        logger.warning("Background tasks stopped.")

    except DuplicatePollingDetected as e:
        logger.error("Duplicate polling protection triggered: %s", e)
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

        for task in (shutdown_wait_task, monitoring_task, polling_task):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        await safe_close_storage(dp)
        await safe_close_bot_session(bot)
        await safe_release_lock(lock_conn, lock_key)
        await safe_close_lock_conn(lock_conn)

        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
