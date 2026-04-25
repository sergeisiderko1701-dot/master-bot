import logging

from repositories import execute


logger = logging.getLogger(__name__)


ORDER_NOTIFICATION_TYPES = ("new_order", "reopened_order")


async def cleanup_duplicate_order_notification_jobs() -> int:
    """
    Видаляє старі дублікати order notification jobs перед створенням UNIQUE index.

    Унікальність потрібна для:
    - один майстер;
    - одна заявка;
    - один тип notification_type.

    Захищає типи:
    - notification_type='new_order'
    - notification_type='reopened_order'

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
            WHERE notification_type = ANY($1::text[])
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
        """,
        list(ORDER_NOTIFICATION_TYPES),
    )

    # asyncpg для SELECT через execute може повернути "SELECT 1",
    # тому для сумісності парсимо останнє число. Якщо не вийде — просто 0.
    try:
        return int(str(result).split()[-1])
    except Exception:
        logger.warning("Could not parse duplicate notification jobs cleanup result=%r", result)
        return 0


# Backward-compatible alias, якщо десь ще імпортується стара назва.
async def cleanup_duplicate_new_order_notification_jobs() -> int:
    return await cleanup_duplicate_order_notification_jobs()


async def ensure_notification_jobs_unique_index() -> None:
    """
    Створює partial UNIQUE index для notification_jobs.

    Захист:
    - один і той самий майстер не отримає дубль однієї і тієї ж заявки;
    - create_notification_job(... ON CONFLICT DO NOTHING) починає реально працювати;
    - захист працює і для першої розсилки, і для повторно відкритої заявки.

    Індекс:
    UNIQUE(user_id, order_id, notification_type)
    WHERE notification_type IN ('new_order', 'reopened_order')
      AND order_id IS NOT NULL
    """
    try:
        deleted_count = await cleanup_duplicate_order_notification_jobs()
        if deleted_count:
            logger.warning(
                "Cleaned duplicate order notification_jobs before unique index: deleted=%s",
                deleted_count,
            )
    except Exception:
        logger.exception("Failed to cleanup duplicate order notification_jobs before unique index")
        raise

    # Старий індекс захищав тільки notification_type='new_order'.
    # Видаляємо його, щоб не тримати зайвий дублюючий індекс поруч із новим.
    await execute(
        """
        DROP INDEX IF EXISTS ux_notification_jobs_new_order_unique
        """
    )

    await execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_notification_jobs_order_unique
        ON notification_jobs(user_id, order_id, notification_type)
        WHERE notification_type IN ('new_order', 'reopened_order')
          AND order_id IS NOT NULL
        """
    )

    logger.info("Notification jobs unique index ensured: ux_notification_jobs_order_unique")
