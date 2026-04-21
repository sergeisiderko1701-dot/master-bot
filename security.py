import time
from collections import defaultdict, deque


_action_hits = defaultdict(deque)
_user_mutes = {}


def now_ts() -> int:
    return int(time.time())


def _cleanup_old_hits(key, window_seconds: int):
    current = now_ts()
    q = _action_hits[key]
    while q and current - q[0] > window_seconds:
        q.popleft()
    return q


def mute_user(user_id: int, mute_seconds: int):
    _user_mutes[user_id] = now_ts() + max(1, int(mute_seconds))


def get_mute_left(user_id: int) -> int:
    until = int(_user_mutes.get(user_id, 0) or 0)
    left = until - now_ts()
    if left <= 0:
        _user_mutes.pop(user_id, None)
        return 0
    return left


def is_user_muted(user_id: int) -> bool:
    return get_mute_left(user_id) > 0


def register_action_and_check(
    user_id: int,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    mute_left = get_mute_left(user_id)
    if mute_left > 0:
        return False, f"⏳ Забагато дій. Спробуйте ще раз через {mute_left} сек."

    key = (user_id, action_key)
    q = _cleanup_old_hits(key, window_seconds)

    q.append(now_ts())

    if len(q) > limit:
        mute_user(user_id, mute_seconds)
        return False, f"⛔ Тимчасове обмеження через надто часті дії. Спробуйте через {mute_seconds} сек."

    return True, None


async def allow_message_action(
    message,
    action_key: str,
    limit: int,
    window_seconds: int,
    mute_seconds: int,
):
    allowed, error_text = register_action_and_check(
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
    allowed, error_text = register_action_and_check(
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
