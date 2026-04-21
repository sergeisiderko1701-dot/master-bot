import asyncio
from typing import Optional

from redis.asyncio import Redis

from config import settings


# =========================
# REDIS CLIENT
# =========================

_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    global _redis

    if _redis:
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


# =========================
# HELPERS
# =========================

def _action_key(user_id: int, action: str) -> str:
    return f"rate:{user_id}:{action}"


def _mute_key(user_id: int) -> str:
    return f"mute:{user_id}"


# =========================
# MUTE
# =========================

async def mute_user(user_id: int, mute_seconds: int):
    r = await get_redis()
    await r.set(_mute_key(user_id), "1", ex=max(1, int(mute_seconds)))


async def get_mute_left(user_id: int) -> int:
    r = await get_redis()
    ttl = await r.ttl(_mute_key(user_id))
    return max(0, int(ttl)) if ttl and ttl > 0 else 0


async def is_user_muted(user_id: int) -> bool:
    return (await get_mute_left(user_id)) > 0


# =========================
# RATE LIMIT
# =========================

async def register_action_and_check(
    user_id: int,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    r = await get_redis()

    # перевірка mute
    mute_left = await get_mute_left(user_id)
    if mute_left > 0:
        return False, f"⏳ Забагато дій. Спробуйте через {mute_left} сек."

    key = _action_key(user_id, action_key)

    async with r.pipeline() as pipe:
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

    # якщо ключ новий — ставимо TTL
    if ttl == -1:
        await r.expire(key, window_seconds)

    if int(count) > limit:
        await mute_user(user_id, mute_seconds)
        return False, f"⛔ Обмеження через часті дії. Спробуйте через {mute_seconds} сек."

    return True, None


# =========================
# TELEGRAM HELPERS
# =========================

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
            pass
        return False

    return True
