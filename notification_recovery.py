import logging

from repositories import execute
from utils import now_ts


logger = logging.getLogger(__name__)


async def recover_stale_notification_jobs(stale_after_seconds: int = 300) -> int:
    """
    Повертає завислі notification_jobs зі статусу 'processing' назад у 'pending'.

    Навіщо:
    - worker забрав job і поставив status='processing';
    - Render перезапустив/вбив процес до mark_notification_job_sent/retry/failed;
    - job більше ніколи не буде оброблена, бо claim_notification_jobs бере тільки pending.

    Якщо job висить processing довше stale_after_seconds, вважаємо її завислою
    і повертаємо в чергу.
    """
    current_ts = now_ts()
    threshold_ts = current_ts - int(stale_after_seconds)

    result = await execute(
        """
        UPDATE notification_jobs
        SET status='pending',
            error_text=$1,
            next_attempt_at=$2,
            updated_at=$2
        WHERE status='processing'
          AND COALESCE(updated_at, 0) <= $3
        """,
        f"Recovered stale processing job after {int(stale_after_seconds)} sec",
        current_ts,
        threshold_ts,
    )

    try:
        return int(str(result).split()[-1])
    except Exception:
        logger.warning("Could not parse recovered notification jobs count from result=%r", result)
        return 0
