import logging

from repositories import approved_master_row, touch_master_presence


logger = logging.getLogger(__name__)


async def update_master_presence_if_needed(user_id: int) -> None:
    """
    Centralized helper for marking an approved master as online.

    Before this patch the same helper was duplicated in misc.py and common.py.
    Keeping it here avoids future drift and makes it easier to add throttling later.
    """
    if not user_id:
        return

    try:
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)
    except Exception:
        logger.exception("Failed to update master presence for user_id=%s", user_id)
