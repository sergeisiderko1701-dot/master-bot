import logging

from repositories import execute


logger = logging.getLogger(__name__)


async def cleanup_duplicate_new_order_notification_jobs() -> int:
    """
    Видаляє старі дублікати new_order jobs перед створенням UNIQUE index.

    Унікальність потрібна для:
    - один майстер;
    - одна заявка;
    - один тип notification_type='new_order'.

    Якщо дублікати вже є, PostgreSQL не дозволить створити unique index.
    Тому спочатку залишаємо один найкорисніший запис:
    - sent важливіший за processing;
    - processing важливіший за pending;
    - pending важливіший за failed;
    - якщо однаковий статус — лишаємо новіший id.
    """
    result = await execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id, order_id, notification_type
                    ORDER BY
                        CASE status
                            WHEN 'sent' THEN 0
                            WHEN 'processing' THEN 1
                            WHEN 'pending' THEN 2
                            WHEN 'failed' THEN 3
                            ELSE 4
                        END,
                        id DESC
                ) AS rn
            FROM notification_jobs
            WHERE notification_type='new_order'
              AND order_id IS NOT NULL
        ), deleted AS (
            DELETE FROM notification_jobs
            WHERE id IN (
                SELECT id
                FROM ranked
                WHERE rn > 1
            )
            RETURNING id
        )
        SELECT COUNT(*) FROM deleted
        """
    )

    # asyncpg для SELECT через execute може повернути "SELECT 1",
    # тому для сумісності парсимо останнє число. Якщо не вийде — просто 0.
    try:
        return int(str(result).split()[-1])
    except Exception:
        logger.warning("Could not parse duplicate notification jobs cleanup result=%r", result)
        return 0


async def ensure_notification_jobs_unique_index() -> None:
    """
    Створює partial UNIQUE index для notification_jobs.

    Захист:
    - один і той самий майстер не отримає дубль однієї і тієї ж заявки;
    - create_notification_job(... ON CONFLICT DO NOTHING) починає реально працювати.

    Індекс:
    UNIQUE(user_id, order_id, notification_type)
    WHERE notification_type='new_order' AND order_id IS NOT NULL
    """
    try:
        deleted_count = await cleanup_duplicate_new_order_notification_jobs()
        if deleted_count:
            logger.warning(
                "Cleaned duplicate new_order notification_jobs before unique index: deleted=%s",
                deleted_count,
            )
    except Exception:
        logger.exception("Failed to cleanup duplicate new_order notification_jobs before unique index")
        raise

    await execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_jobs_new_order_unique
        ON notification_jobs(user_id, order_id, notification_type)
        WHERE notification_type='new_order'
          AND order_id IS NOT NULL
        """
    )

    logger.info("Notification jobs unique index ensured: ux_notification_jobs_new_order_unique")
