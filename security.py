import logging
from typing import Optional

from redis.asyncio import Redis

from config import settings


logger = logging.getLogger(__name__)

_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis

    if _redis is not None:
        return _redis

    _redis = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password or None,
        ssl=settings.redis_ssl,
        decode_responses=True,
    )
    return _redis


def _prefix() -> str:
    return settings.security_prefix.strip() or "sec"


def _action_key(user_id: int, action_key: str) -> str:
    return f"{_prefix()}:rate:{user_id}:{action_key}"


def _global_key(user_id: int) -> str:
    return f"{_prefix()}:global:{user_id}"


def _mute_key(user_id: int) -> str:
    return f"{_prefix()}:mute:{user_id}"


async def mute_user(user_id: int, mute_seconds: int):
    r = await get_redis()
    await r.set(_mute_key(user_id), "1", ex=max(1, int(mute_seconds)))


async def get_mute_left(user_id: int) -> int:
    r = await get_redis()
    ttl = await r.ttl(_mute_key(user_id))

    if ttl is None or ttl < 0:
        return 0

    return int(ttl)


async def is_user_muted(user_id: int) -> bool:
    return (await get_mute_left(user_id)) > 0


async def _increment_with_window(key: str, window_seconds: int) -> int:
    r = await get_redis()

    async with r.pipeline() as pipe:
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

    if ttl == -1:
        await r.expire(key, max(1, int(window_seconds)))

    return int(count or 0)


async def _check_global_limit(user_id: int):
    if settings.security_global_limit <= 0:
        return True, None

    count = await _increment_with_window(
        _global_key(user_id),
        settings.security_global_window_seconds,
    )

    if count > settings.security_global_limit:
        await mute_user(user_id, settings.security_global_mute_seconds)
        return (
            False,
            f"⛔ Забагато дій за короткий час. Спробуйте через "
            f"{settings.security_global_mute_seconds} сек.",
        )

    return True, None


async def register_action_and_check(
    user_id: int,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    if user_id == settings.admin_id:
        return True, None

    try:
        mute_left = await get_mute_left(user_id)
        if mute_left > 0:
            return False, f"⏳ Забагато дій. Спробуйте ще раз через {mute_left} сек."

        allowed, global_error = await _check_global_limit(user_id)
        if not allowed:
            return False, global_error

        action_count = await _increment_with_window(
            _action_key(user_id, action_key),
            window_seconds,
        )

        if action_count > int(limit):
            await mute_user(user_id, mute_seconds)
            logger.warning(
                "Rate limit hit: user_id=%s action=%s count=%s limit=%s window=%s mute=%s",
                user_id,
                action_key,
                action_count,
                limit,
                window_seconds,
                mute_seconds,
            )
            return False, f"⛔ Тимчасове обмеження. Спробуйте через {mute_seconds} сек."

        return True, None

    except Exception as e:
        logger.exception(
            "Security backend error for user_id=%s action=%s: %s",
            user_id,
            action_key,
            e,
        )

        if settings.security_fail_open:
            return True, None

        return False, "⚠️ Тимчасово недоступна перевірка безпеки. Спробуйте трохи пізніше."


async def allow_message_action(
    message,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    allowed, error_text = await register_action_and_check(
        user_id=message.from_user.id,
        action_key=action_key,
        limit=limit,
        window_seconds=window_seconds,
        mute_seconds=mute_seconds,
    )

    if not allowed:
        await message.answer(error_text)
        return False

    return True


async def allow_callback_action(
    call,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    allowed, error_text = await register_action_and_check(
        user_id=call.from_user.id,
        action_key=action_key,
        limit=limit,
        window_seconds=window_seconds,
        mute_seconds=mute_seconds,
    )

    if not allowed:
        try:
            await call.answer(error_text, show_alert=True)
        except Exception:
            logger.warning(
                "Failed to answer callback rate limit alert for user_id=%s action=%s",
                call.from_user.id,
                action_key,
            )
        return False

    return True
