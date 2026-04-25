from typing import Optional

import asyncpg

from config import settings
from constants import DISTRICT_ALL_ODESSA, normalize_categories_value, parse_categories, parse_districts
from db import get_pool
from utils import now_ts


# =========================
# BASE HELPERS
# =========================

async def _run_with_retry(method_name: str, query: str, *args):
    """Run a DB command and recover from asyncpg cached statement errors."""
    pool = get_pool()

    async with pool.acquire() as conn:
        method = getattr(conn, method_name)

        try:
            return await method(query, *args)

        except asyncpg.exceptions.InvalidCachedStatementError:
            try:
                await conn.reload_schema_state()
            except Exception:
                pass

            try:
                await conn.execute("DISCARD PLANS")
            except Exception:
                pass

            method = getattr(conn, method_name)
            return await method(query, *args)

        except asyncpg.InvalidCachedStatementError:
            try:
                await conn.reload_schema_state()
            except Exception:
                pass

            try:
                await conn.execute("DISCARD PLANS")
            except Exception:
                pass

            method = getattr(conn, method_name)
            return await method(query, *args)


async def fetch(query: str, *args):
    return await _run_with_retry("fetch", query, *args)


async def fetchrow(query: str, *args):
    return await _run_with_retry("fetchrow", query, *args)


async def fetchval(query: str, *args):
    return await _run_with_retry("fetchval", query, *args)


async def execute(query: str, *args):
    return await _run_with_retry("execute", query, *args)


async def ensure_order_client_address_column() -> None:
    """
    Backward-compatible migration for client_address.
    Safe to call multiple times.
    """
    await execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS client_address TEXT")


# =========================
# ORDER EVENTS
# =========================

async def add_order_event(
    order_id: int,
    event_type: str,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    payload: Optional[str] = None,
):
    await execute(
        """
        INSERT INTO order_events (
            order_id,
            event_type,
            from_status,
            to_status,
            actor_user_id,
            actor_role,
            payload,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        order_id,
        event_type,
        from_status,
        to_status,
        actor_user_id,
        actor_role,
        payload,
        now_ts(),
    )


# =========================
# ADMIN FUNNEL / STATS
# =========================

async def admin_funnel_stats(period_seconds: Optional[int] = None):
    threshold = now_ts() - period_seconds if period_seconds else None
    args = [threshold] if threshold is not None else []

    total_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        {"WHERE created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    total_orders = int(total_row["c"] or 0)

    with_offers_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders o
        WHERE EXISTS (
            SELECT 1
            FROM offers f
            WHERE f.order_id = o.id
        )
        {"AND o.created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    with_offers = int(with_offers_row["c"] or 0)

    matched_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE (
            status IN ('matched', 'in_progress', 'done')
            OR selected_master_id IS NOT NULL
        )
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    matched = int(matched_row["c"] or 0)

    in_progress_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE status='in_progress'
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    in_progress = int(in_progress_row["c"] or 0)

    done_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE status='done'
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    done = int(done_row["c"] or 0)

    rated_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE rating IS NOT NULL
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    rated = int(rated_row["c"] or 0)

    cancelled_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE status='cancelled'
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    cancelled = int(cancelled_row["c"] or 0)

    expired_row = await fetchrow(
        f"""
        SELECT COUNT(*) AS c
        FROM orders
        WHERE status='expired'
        {"AND created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    expired = int(expired_row["c"] or 0)

    reopened_row = await fetchrow(
        f"""
        SELECT COUNT(DISTINCT e.order_id) AS c
        FROM order_events e
        JOIN orders o ON o.id = e.order_id
        WHERE e.event_type='order_reopened_by_client'
        {"AND o.created_at >= $1" if threshold is not None else ""}
        """,
        *args,
    )
    reopened = int(reopened_row["c"] or 0)

    def _pct(a: int, b: int) -> float:
        if b <= 0:
            return 0.0
        return round((a / b) * 100, 1)

    return {
        "total_orders": total_orders,
        "with_offers": with_offers,
        "matched": matched,
        "in_progress": in_progress,
        "done": done,
        "rated": rated,
        "cancelled": cancelled,
        "expired": expired,
        "reopened": reopened,
        "conv_offers_from_total": _pct(with_offers, total_orders),
        "conv_matched_from_offers": _pct(matched, with_offers),
        "conv_done_from_matched": _pct(done, matched),
        "conv_rated_from_done": _pct(rated, done),
    }


async def admin_stats():
    keys = {
        "masters_total": "SELECT COUNT(*) AS c FROM masters",
        "masters_approved": "SELECT COUNT(*) AS c FROM masters WHERE status='approved'",
        "masters_pending": "SELECT COUNT(*) AS c FROM masters WHERE status='pending'",
        "masters_blocked": "SELECT COUNT(*) AS c FROM masters WHERE status='blocked'",
        "orders_total": "SELECT COUNT(*) AS c FROM orders",
        "orders_new": "SELECT COUNT(*) AS c FROM orders WHERE status='new'",
        "orders_offered": "SELECT COUNT(*) AS c FROM orders WHERE status='offered'",
        "orders_matched": "SELECT COUNT(*) AS c FROM orders WHERE status='matched'",
        "orders_progress": "SELECT COUNT(*) AS c FROM orders WHERE status='in_progress'",
        "orders_done": "SELECT COUNT(*) AS c FROM orders WHERE status='done'",
        "orders_cancelled": "SELECT COUNT(*) AS c FROM orders WHERE status='cancelled'",
        "orders_expired": "SELECT COUNT(*) AS c FROM orders WHERE status='expired'",
    }
    data = {}
    for key, query in keys.items():
        row = await fetchrow(query)
        data[key] = int(row["c"] or 0)
    return data


# =========================
# SPAM LOGS
# =========================

async def add_spam_log(
    user_id: int,
    scope: str,
    action_key: Optional[str] = None,
    hit_count: Optional[int] = None,
    limit_value: Optional[int] = None,
    window_seconds: Optional[int] = None,
    mute_seconds: Optional[int] = None,
    reason_text: Optional[str] = None,
):
    await execute(
        """
        INSERT INTO spam_logs (
            user_id,
            action_key,
            scope,
            hit_count,
            limit_value,
            window_seconds,
            mute_seconds,
            reason_text,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        user_id,
        action_key,
        scope,
        hit_count,
        limit_value,
        window_seconds,
        mute_seconds,
        reason_text,
        now_ts(),
    )


# =========================
# MASTERS
# =========================

async def master_any_row(user_id: int):
    return await fetchrow("SELECT * FROM masters WHERE user_id=$1", user_id)


async def approved_master_row(user_id: int):
    return await fetchrow(
        "SELECT * FROM masters WHERE user_id=$1 AND status='approved'",
        user_id,
    )


async def create_or_update_master(data: dict):
    ts = now_ts()
    category_value = normalize_categories_value(data.get("category"))
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO masters(
                user_id, name, category, district, phone, description, experience, photo,
                rating, reviews_count, status, availability, last_seen, created_at, updated_at
            )
            VALUES($1, $2, $3, $4, $5, $6, $7, $8, 0, 0, 'pending', 'offline', $9, $9, $9)
            ON CONFLICT(user_id) DO UPDATE SET
                name=EXCLUDED.name,
                category=EXCLUDED.category,
                district=EXCLUDED.district,
                phone=EXCLUDED.phone,
                description=EXCLUDED.description,
                experience=EXCLUDED.experience,
                photo=EXCLUDED.photo,
                status='pending',
                availability='offline',
                last_seen=EXCLUDED.last_seen,
                updated_at=EXCLUDED.updated_at
            """,
            data["user_id"],
            data.get("name"),
            category_value,
            data.get("district"),
            data.get("phone"),
            data.get("description"),
            data.get("experience"),
            data.get("photo"),
            ts,
        )


async def update_master_profile(user_id: int, field_name: str, value):
    allowed = {"name", "category", "district", "phone", "description", "experience", "photo"}
    if field_name not in allowed:
        raise ValueError(f"Unsupported field: {field_name}")

    if field_name == "category":
        value = normalize_categories_value(value)

    query = f"UPDATE masters SET {field_name}=$1, updated_at=$2 WHERE user_id=$3"
    await execute(query, value, now_ts(), user_id)


async def touch_master_presence(user_id: int):
    await execute(
        """
        UPDATE masters
        SET availability='online',
            last_seen=$1,
            updated_at=$1
        WHERE user_id=$2
        """,
        now_ts(),
        user_id,
    )


async def master_active_orders_count(master_user_id: int) -> int:
    value = await fetchval(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE selected_master_id=$1
          AND status = ANY($2::text[])
        """,
        master_user_id,
        ["matched", "in_progress"],
    )
    return int(value or 0)


async def master_active_offers_count(master_user_id: int) -> int:
    value = await fetchval(
        """
        SELECT COUNT(*)
        FROM offers
        WHERE master_user_id=$1
          AND status='active'
        """,
        master_user_id,
    )
    return int(value or 0)


async def list_new_orders_for_master(category_value, district_value=None):
    """
    New orders visible to a master.

    Filters by:
    - master's selected categories;
    - master's selected districts;
    - if master selected "Вся Одеса", show all districts.

    This prevents masters from seeing orders outside their working districts
    when they open "🔔 Нові заявки" manually.
    """
    categories = parse_categories(category_value)
    if not categories:
        return []

    districts = parse_districts(district_value)

    # Master works across all Odessa: show all orders in selected categories.
    if DISTRICT_ALL_ODESSA in districts:
        return await fetch(
            """
            SELECT *
            FROM orders
            WHERE category = ANY($1::text[])
              AND status = ANY($2::text[])
              AND moderation_status='approved'
            ORDER BY created_at DESC
            LIMIT 50
            """,
            categories,
            ["new", "offered"],
        )

    # No districts configured: do not show random city-wide orders.
    if not districts:
        return []

    return await fetch(
        """
        SELECT *
        FROM orders
        WHERE category = ANY($1::text[])
          AND district = ANY($2::text[])
          AND status = ANY($3::text[])
          AND moderation_status='approved'
        ORDER BY created_at DESC
        LIMIT 50
        """,
        categories,
        districts,
        ["new", "offered"],
    )


async def list_approved_masters_for_category(category: str, district: Optional[str] = None):
    """
    Approved masters by category.
    If district is provided, returns only masters who work in that district
    or selected "Вся Одеса".
    """
    if district:
        return await fetch(
            """
            SELECT user_id, category, status, district
            FROM masters
            WHERE status='approved'
              AND $1 = ANY(string_to_array(category, ','))
              AND (
                    $2 = ANY(string_to_array(COALESCE(district, ''), ','))
                    OR $3 = ANY(string_to_array(COALESCE(district, ''), ','))
              )
            """,
            category,
            district,
            DISTRICT_ALL_ODESSA,
        )

    return await fetch(
        """
        SELECT user_id, category, status, district
        FROM masters
        WHERE status='approved'
          AND $1 = ANY(string_to_array(category, ','))
        """,
        category,
    )


async def list_active_orders_for_master(master_user_id: int):
    return await fetch(
        """
        SELECT *
        FROM orders
        WHERE selected_master_id=$1
          AND status = ANY($2::text[])
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 50
        """,
        master_user_id,
        ["matched", "in_progress"],
    )


async def get_master_name(master_user_id: Optional[int]) -> str:
    if not master_user_id:
        return "—"
    row = await fetchrow("SELECT name FROM masters WHERE user_id=$1", master_user_id)
    return row["name"] if row else "—"


async def set_master_status_by_id(master_id: int, status: str, availability: Optional[str] = None):
    ts = now_ts()

    if availability:
        await execute(
            """
            UPDATE masters
            SET status=$1,
                availability=$2,
                verification_status=CASE
                    WHEN $1='approved' AND COALESCE(verification_status, 'not_verified')='pending' THEN 'verified'
                    WHEN $1='blocked' AND COALESCE(verification_status, 'not_verified')='pending' THEN 'rejected'
                    ELSE verification_status
                END,
                updated_at=$3
            WHERE id=$4
            """,
            status,
            availability,
            ts,
            master_id,
        )
    else:
        await execute(
            """
            UPDATE masters
            SET status=$1,
                verification_status=CASE
                    WHEN $1='approved' AND COALESCE(verification_status, 'not_verified')='pending' THEN 'verified'
                    WHEN $1='blocked' AND COALESCE(verification_status, 'not_verified')='pending' THEN 'rejected'
                    ELSE verification_status
                END,
                updated_at=$2
            WHERE id=$3
            """,
            status,
            ts,
            master_id,
        )


async def delete_master_by_id(master_id: int):
    await execute("DELETE FROM masters WHERE id=$1", master_id)


async def get_master_by_id(master_id: int):
    return await fetchrow("SELECT * FROM masters WHERE id=$1", master_id)


async def list_pending_masters(limit: int, offset: int):
    rows = await fetch(
        "SELECT * FROM masters WHERE status='pending' ORDER BY id DESC LIMIT $1 OFFSET $2",
        limit,
        offset,
    )
    total = await fetchrow("SELECT COUNT(*) AS c FROM masters WHERE status='pending'")
    return rows, int(total["c"] or 0)


async def list_admin_masters(limit: int, offset: int):
    rows = await fetch(
        """
        SELECT *
        FROM masters
        WHERE status = ANY($1::text[])
        ORDER BY rating DESC, reviews_count DESC, name ASC
        LIMIT $2 OFFSET $3
        """,
        ["approved", "blocked"],
        limit,
        offset,
    )
    total = await fetchrow(
        "SELECT COUNT(*) AS c FROM masters WHERE status = ANY($1::text[])",
        ["approved", "blocked"],
    )
    return rows, int(total["c"] or 0)


# =========================
# ORDERS
# =========================

async def client_active_orders_count(user_id: int) -> int:
    value = await fetchval(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE user_id=$1
          AND status = ANY($2::text[])
        """,
        user_id,
        ["new", "offered", "matched", "in_progress"],
    )
    return int(value or 0)


async def get_recent_client_order_count(user_id: int, seconds: int = 3600) -> int:
    threshold = now_ts() - seconds
    value = await fetchval(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE user_id=$1
          AND created_at >= $2
        """,
        user_id,
        threshold,
    )
    return int(value or 0)


async def has_duplicate_recent_problem(user_id: int, problem: str, days: int = 7) -> bool:
    threshold = now_ts() - (days * 24 * 60 * 60)
    value = await fetchval(
        """
        SELECT 1
        FROM orders
        WHERE user_id=$1
          AND LOWER(TRIM(problem)) = LOWER(TRIM($2))
          AND created_at >= $3
        LIMIT 1
        """,
        user_id,
        problem,
        threshold,
    )
    return bool(value)


async def create_order(
    user_id: int,
    category: str,
    district: str,
    problem: str,
    client_address: Optional[str] = None,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
    client_phone: Optional[str] = None,
    is_suspect: bool = False,
    suspicion_score: int = 0,
    suspicion_reasons: Optional[str] = None,
    moderation_status: str = "approved",
) -> int:
    await ensure_order_client_address_column()

    ts = now_ts()
    row = await fetchrow(
        """
        INSERT INTO orders(
            user_id,
            category,
            district,
            client_address,
            problem,
            client_phone,
            media_type,
            media_file_id,
            status,
            is_suspect,
            suspicion_score,
            suspicion_reasons,
            moderation_status,
            created_at,
            updated_at
        )
        VALUES(
            $1, $2, $3, $4, $5, $6, $7, $8,
            'new',
            $9, $10, $11, $12,
            $13, $13
        )
        RETURNING id
        """,
        user_id,
        category,
        district,
        client_address,
        problem,
        client_phone,
        media_type,
        media_file_id,
        is_suspect,
        suspicion_score,
        suspicion_reasons,
        moderation_status,
        ts,
    )
    order_id = int(row["id"])

    await add_order_event(
        order_id=order_id,
        event_type="order_created",
        from_status=None,
        to_status="new",
        actor_user_id=user_id,
        actor_role="client",
        payload=(
            f"category={category};district={district or ''};address={client_address or ''};"
            f"is_suspect={int(bool(is_suspect))};moderation_status={moderation_status}"
        ),
    )

    return order_id


async def get_order_row(order_id: int):
    return await fetchrow("SELECT * FROM orders WHERE id=$1", order_id)


async def list_client_orders(user_id: int):
    return await fetch(
        """
        SELECT *
        FROM orders
        WHERE user_id=$1
        ORDER BY created_at DESC
        LIMIT 50
        """,
        user_id,
    )


async def list_admin_orders(limit: int, offset: int, status_filter: Optional[str] = None):
    if status_filter:
        rows = await fetch(
            "SELECT * FROM orders WHERE status=$1 ORDER BY id DESC LIMIT $2 OFFSET $3",
            status_filter,
            limit,
            offset,
        )
        total = await fetchrow("SELECT COUNT(*) AS c FROM orders WHERE status=$1", status_filter)
    else:
        rows = await fetch(
            "SELECT * FROM orders ORDER BY id DESC LIMIT $1 OFFSET $2",
            limit,
            offset,
        )
        total = await fetchrow("SELECT COUNT(*) AS c FROM orders")
    return rows, int(total["c"] or 0)


async def list_suspicious_orders(limit: int = 20, offset: int = 0):
    rows = await fetch(
        """
        SELECT *
        FROM orders
        WHERE moderation_status='pending_review'
        ORDER BY created_at DESC, id DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await fetchrow(
        """
        SELECT COUNT(*) AS c
        FROM orders
        WHERE moderation_status='pending_review'
        """
    )
    return rows, int(total["c"] or 0)


async def approve_suspicious_order(order_id: int, admin_user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND moderation_status='pending_review'
                FOR UPDATE
                """,
                order_id,
            )
            if not order:
                return None

            await conn.execute(
                """
                UPDATE orders
                SET moderation_status='approved',
                    updated_at=$1
                WHERE id=$2
                """,
                now_ts(),
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="order_approved_by_admin",
        from_status=order["status"],
        to_status=order["status"],
        actor_user_id=admin_user_id,
        actor_role="admin",
        payload="moderation_status=approved",
    )

    return await get_order_row(order_id)


async def reject_suspicious_order(order_id: int, admin_user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND moderation_status='pending_review'
                FOR UPDATE
                """,
                order_id,
            )
            if not order:
                return None

            await conn.execute(
                """
                UPDATE orders
                SET moderation_status='rejected',
                    status='cancelled',
                    updated_at=$1
                WHERE id=$2
                """,
                now_ts(),
                order_id,
            )

            await conn.execute(
                """
                UPDATE offers
                SET status='rejected'
                WHERE order_id=$1
                  AND status='active'
                """,
                order_id,
            )

            await conn.execute(
                "UPDATE chats SET status='closed' WHERE order_id=$1",
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="order_rejected_as_suspect",
        from_status=order["status"],
        to_status="cancelled",
        actor_user_id=admin_user_id,
        actor_role="admin",
        payload="moderation_status=rejected",
    )

    return await get_order_row(order_id)


async def set_order_status(order_id: int, status: str, selected_master_id=None):
    """
    Атомарна зміна статусу заявки для адмінських дій.

    Що стало краще:
    - order блокується через FOR UPDATE;
    - пов'язані offers/chats оновлюються в одній транзакції;
    - або всі зміни проходять, або все відкочується.

    Важливо:
    - offers.status має тільки active/chosen/rejected, тому НЕ використовуємо 'closed';
    - при expired/cancelled/new активні офери переводимо в rejected;
    - при done закриваємо чат, але не чіпаємо chosen offer;
    - при in_progress/matched зберігаємо selected_master_id.
    """
    pool = get_pool()
    ts = now_ts()

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            current = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                FOR UPDATE
                """,
                order_id,
            )
            if not current:
                return None

            await conn.execute(
                """
                UPDATE orders
                SET status=$1,
                    selected_master_id=$2,
                    updated_at=$3
                WHERE id=$4
                """,
                status,
                selected_master_id,
                ts,
                order_id,
            )

            if status in {"expired", "cancelled"}:
                await conn.execute(
                    """
                    UPDATE offers
                    SET status='rejected'
                    WHERE order_id=$1
                      AND status IN ('active', 'chosen')
                    """,
                    order_id,
                )
                await conn.execute(
                    "UPDATE chats SET status='closed' WHERE order_id=$1",
                    order_id,
                )

            elif status == "done":
                await conn.execute(
                    "UPDATE chats SET status='closed' WHERE order_id=$1",
                    order_id,
                )

            elif status == "new":
                await conn.execute(
                    """
                    UPDATE offers
                    SET status='rejected'
                    WHERE order_id=$1
                      AND status IN ('active', 'chosen')
                    """,
                    order_id,
                )
                await conn.execute(
                    "UPDATE chats SET status='closed' WHERE order_id=$1",
                    order_id,
                )

            updated = await conn.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)

    await add_order_event(
        order_id=order_id,
        event_type="order_status_changed",
        from_status=current["status"],
        to_status=status,
        actor_user_id=None,
        actor_role="system",
        payload=f"selected_master_id={selected_master_id}",
    )

    return updated


async def cancel_order(order_id: int, client_user_id: Optional[int] = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if client_user_id is None:
                order = await conn.fetchrow(
                    """
                    SELECT *
                    FROM orders
                    WHERE id=$1
                      AND status = ANY($2::text[])
                    FOR UPDATE
                    """,
                    order_id,
                    ["new", "offered", "matched"],
                )
            else:
                order = await conn.fetchrow(
                    """
                    SELECT *
                    FROM orders
                    WHERE id=$1
                      AND user_id=$2
                      AND status = ANY($3::text[])
                    FOR UPDATE
                    """,
                    order_id,
                    client_user_id,
                    ["new", "offered", "matched"],
                )
            if not order:
                return None

            await conn.execute(
                "UPDATE orders SET status='cancelled', updated_at=$1 WHERE id=$2",
                now_ts(),
                order_id,
            )
            await conn.execute(
                "UPDATE offers SET status='rejected' WHERE order_id=$1 AND status='active'",
                order_id,
            )
            await conn.execute(
                "UPDATE chats SET status='closed' WHERE order_id=$1",
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="order_cancelled",
        from_status=order["status"],
        to_status="cancelled",
        actor_user_id=order["user_id"],
        actor_role="client",
        payload=None,
    )

    return order


async def refuse_order(order_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                FOR UPDATE
                """,
                order_id,
            )
            if not order:
                return None

            selected_master_id = order["selected_master_id"]

            if selected_master_id is not None:
                await conn.execute(
                    """
                    UPDATE offers
                    SET status='rejected'
                    WHERE order_id=$1
                      AND master_user_id=$2
                      AND status='chosen'
                    """,
                    order_id,
                    selected_master_id,
                )

            await conn.execute(
                """
                UPDATE offers
                SET status='active'
                WHERE order_id=$1
                  AND status='rejected'
                  AND ($2::bigint IS NULL OR master_user_id <> $2::bigint)
                """,
                order_id,
                selected_master_id,
            )

            active_offers_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM offers
                WHERE order_id=$1
                  AND status='active'
                """,
                order_id,
            )

            new_status = "offered" if int(active_offers_count or 0) > 0 else "new"

            await conn.execute(
                """
                UPDATE orders
                SET selected_master_id=NULL,
                    status=$1,
                    updated_at=$2
                WHERE id=$3
                """,
                new_status,
                now_ts(),
                order_id,
            )
            await conn.execute(
                "UPDATE chats SET status='closed' WHERE order_id=$1",
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="master_refused",
        from_status=order["status"],
        to_status=new_status,
        actor_user_id=selected_master_id,
        actor_role="master",
        payload=f"active_offers_after={int(active_offers_count or 0)}",
    )

    return await get_order_row(order_id)


async def reopen_order_by_client(order_id: int, client_user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND user_id=$2
                  AND status = ANY($3::text[])
                  AND selected_master_id IS NOT NULL
                FOR UPDATE
                """,
                order_id,
                client_user_id,
                ["matched", "in_progress"],
            )
            if not order:
                return None

            selected_master_id = order["selected_master_id"]

            await conn.execute(
                """
                UPDATE offers
                SET status='rejected'
                WHERE order_id=$1
                  AND master_user_id=$2
                  AND status='chosen'
                """,
                order_id,
                selected_master_id,
            )

            await conn.execute(
                """
                UPDATE offers
                SET status='active'
                WHERE order_id=$1
                  AND status='rejected'
                  AND master_user_id <> $2
                """,
                order_id,
                selected_master_id,
            )

            active_offers_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM offers
                WHERE order_id=$1
                  AND status='active'
                """,
                order_id,
            )

            new_status = "offered" if int(active_offers_count or 0) > 0 else "new"

            await conn.execute(
                """
                UPDATE orders
                SET selected_master_id=NULL,
                    status=$1,
                    updated_at=$2
                WHERE id=$3
                """,
                new_status,
                now_ts(),
                order_id,
            )

            await conn.execute(
                "UPDATE chats SET status='closed' WHERE order_id=$1",
                order_id,
            )

            updated_order = await conn.fetchrow(
                "SELECT * FROM orders WHERE id=$1",
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="order_reopened_by_client",
        from_status=order["status"],
        to_status=new_status,
        actor_user_id=client_user_id,
        actor_role="client",
        payload=f"previous_master_id={selected_master_id};active_offers_after={int(active_offers_count or 0)}",
    )

    return updated_order


async def finish_order(order_id: int, master_user_id: Optional[int] = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if master_user_id is None:
                order = await conn.fetchrow(
                    """
                    SELECT *
                    FROM orders
                    WHERE id=$1
                      AND status = ANY($2::text[])
                    FOR UPDATE
                    """,
                    order_id,
                    ["matched", "in_progress"],
                )
            else:
                order = await conn.fetchrow(
                    """
                    SELECT *
                    FROM orders
                    WHERE id=$1
                      AND selected_master_id=$2
                      AND status = ANY($3::text[])
                    FOR UPDATE
                    """,
                    order_id,
                    master_user_id,
                    ["matched", "in_progress"],
                )
            if not order:
                return None

            await conn.execute(
                "UPDATE orders SET status='done', updated_at=$1 WHERE id=$2",
                now_ts(),
                order_id,
            )
            await conn.execute(
                "UPDATE chats SET status='closed' WHERE order_id=$1",
                order_id,
            )

    await add_order_event(
        order_id=order_id,
        event_type="order_finished",
        from_status=order["status"],
        to_status="done",
        actor_user_id=order["selected_master_id"],
        actor_role="master",
        payload=None,
    )

    return order


# =========================
# OFFERS
# =========================

async def create_offer(order_id: int, master_user_id: int, price: str, eta: str, comment: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND status = ANY($2::text[])
                  AND moderation_status='approved'
                FOR UPDATE
                """,
                order_id,
                ["new", "offered"],
            )
            if not order:
                return None

            existing = await conn.fetchrow(
                """
                SELECT id
                FROM offers
                WHERE order_id=$1
                  AND master_user_id=$2
                  AND status='active'
                """,
                order_id,
                master_user_id,
            )
            if existing:
                return None

            row = await conn.fetchrow(
                """
                INSERT INTO offers (
                    order_id,
                    master_user_id,
                    price,
                    eta,
                    comment,
                    status,
                    created_at
                )
                VALUES ($1,$2,$3,$4,$5,'active',$6)
                ON CONFLICT (order_id, master_user_id) DO NOTHING
                RETURNING id
                """,
                order_id,
                master_user_id,
                price,
                eta,
                comment,
                now_ts(),
            )

            if not row:
                return None

            previous_status = order["status"]

            await conn.execute(
                """
                UPDATE orders
                SET status='offered',
                    updated_at=$1
                WHERE id=$2
                """,
                now_ts(),
                order_id,
            )

            offer_id = row["id"]

    await add_order_event(
        order_id=order_id,
        event_type="offer_created",
        from_status=previous_status,
        to_status="offered",
        actor_user_id=master_user_id,
        actor_role="master",
        payload=f"offer_id={offer_id};price={price};eta={eta}",
    )

    return offer_id


async def list_order_offers(order_id: int):
    return await fetch(
        """
        SELECT
            offers.id,
            offers.order_id,
            offers.master_user_id,
            offers.price,
            offers.eta,
            offers.comment,
            offers.status,
            masters.name,
            masters.rating,
            masters.reviews_count,
            masters.phone,
            masters.category,
            masters.availability,
            masters.last_seen
        FROM offers
        JOIN masters ON masters.user_id = offers.master_user_id
        WHERE offers.order_id=$1
          AND offers.status='active'
        ORDER BY offers.created_at ASC
        """,
        order_id,
    )


async def choose_offer(offer_id: int, client_user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            offer = await conn.fetchrow(
                """
                SELECT *
                FROM offers
                WHERE id=$1
                  AND status='active'
                FOR UPDATE
                """,
                offer_id,
            )
            if not offer:
                return None

            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND user_id=$2
                  AND status = ANY($3::text[])
                FOR UPDATE
                """,
                offer["order_id"],
                client_user_id,
                ["new", "offered"],
            )
            if not order:
                return None

            await conn.execute(
                """
                UPDATE orders
                SET selected_master_id=$1,
                    status='matched',
                    updated_at=$2
                WHERE id=$3
                """,
                offer["master_user_id"],
                now_ts(),
                offer["order_id"],
            )

            await conn.execute(
                """
                UPDATE offers
                SET status=CASE
                    WHEN id=$1 THEN 'chosen'
                    ELSE 'rejected'
                END
                WHERE order_id=$2
                  AND status='active'
                """,
                offer_id,
                offer["order_id"],
            )

            chat = await conn.fetchrow("SELECT * FROM chats WHERE order_id=$1", offer["order_id"])

            if chat:
                await conn.execute(
                    """
                    UPDATE chats
                    SET client_user_id=$1,
                        master_user_id=$2,
                        status='active'
                    WHERE id=$3
                    """,
                    client_user_id,
                    offer["master_user_id"],
                    chat["id"],
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO chats (
                        order_id,
                        client_user_id,
                        master_user_id,
                        status,
                        created_at
                    )
                    VALUES ($1,$2,$3,'active',$4)
                    """,
                    offer["order_id"],
                    client_user_id,
                    offer["master_user_id"],
                    now_ts(),
                )

            selected_offer = await conn.fetchrow("SELECT * FROM offers WHERE id=$1", offer_id)

    await add_order_event(
        order_id=offer["order_id"],
        event_type="offer_chosen",
        from_status=order["status"],
        to_status="matched",
        actor_user_id=client_user_id,
        actor_role="client",
        payload=f"offer_id={offer_id};master_user_id={offer['master_user_id']}",
    )

    return selected_offer


# =========================
# CHATS
# =========================

async def get_chat_for_order(order_id: int):
    return await fetchrow(
        "SELECT * FROM chats WHERE order_id=$1 ORDER BY id DESC LIMIT 1",
        order_id,
    )


async def create_chat_if_not_exists(order_id: int, client_user_id: int, master_user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            chat = await conn.fetchrow(
                "SELECT * FROM chats WHERE order_id=$1 ORDER BY id DESC LIMIT 1 FOR UPDATE",
                order_id,
            )
            if chat:
                if (
                    chat["client_user_id"] != client_user_id
                    or chat["master_user_id"] != master_user_id
                    or chat["status"] != "active"
                ):
                    await conn.execute(
                        """
                        UPDATE chats
                        SET client_user_id=$1,
                            master_user_id=$2,
                            status='active'
                        WHERE id=$3
                        """,
                        client_user_id,
                        master_user_id,
                        chat["id"],
                    )
                    chat = await conn.fetchrow("SELECT * FROM chats WHERE id=$1", chat["id"])
                return chat

            return await conn.fetchrow(
                """
                INSERT INTO chats (
                    order_id,
                    client_user_id,
                    master_user_id,
                    status,
                    created_at
                )
                VALUES ($1,$2,$3,'active',$4)
                RETURNING *
                """,
                order_id,
                client_user_id,
                master_user_id,
                now_ts(),
            )


async def close_chat(order_id: int):
    await execute("UPDATE chats SET status='closed' WHERE order_id=$1", order_id)


async def create_chat_message(
    chat_id: int,
    order_id: int,
    sender_user_id: int,
    sender_role: str,
    message_type: str,
    text: Optional[str],
    file_id: Optional[str],
):
    return await fetchrow(
        """
        INSERT INTO chat_messages(
            chat_id,
            order_id,
            sender_user_id,
            sender_role,
            message_type,
            text,
            file_id,
            created_at
        )
        VALUES($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING *
        """,
        chat_id,
        order_id,
        sender_user_id,
        sender_role,
        message_type,
        text,
        file_id,
        now_ts(),
    )


async def save_chat_message(chat_id: int, sender_role: str, text: str):
    chat = await fetchrow("SELECT * FROM chats WHERE id=$1", chat_id)
    if not chat:
        return None

    sender_user_id = chat["client_user_id"] if sender_role == "client" else chat["master_user_id"]

    return await create_chat_message(
        chat_id=chat_id,
        order_id=chat["order_id"],
        sender_user_id=sender_user_id,
        sender_role=sender_role,
        message_type="text",
        text=text,
        file_id=None,
    )


async def get_chat_history(order_id: int, limit: int = 30):
    return await fetch(
        """
        SELECT
            sender_user_id,
            sender_role,
            text,
            message_type,
            file_id,
            created_at
        FROM chat_messages
        WHERE order_id=$1
        ORDER BY id DESC
        LIMIT $2
        """,
        order_id,
        limit,
    )


# =========================
# SUPPORT / COMPLAINTS
# =========================

async def add_complaint(order_id: int, from_user_id: int, against_user_id: int, against_role: str, text: str):
    await execute(
        """
        INSERT INTO complaints(order_id, from_user_id, against_user_id, against_role, text, created_at)
        VALUES($1, $2, $3, $4, $5, $6)
        """,
        order_id,
        from_user_id,
        against_user_id,
        against_role,
        text,
        now_ts(),
    )


async def add_support_message(from_user_id: int, text: str):
    await execute(
        "INSERT INTO support_messages(from_user_id, text, created_at) VALUES($1, $2, $3)",
        from_user_id,
        text,
        now_ts(),
    )


# =========================
# COOLDOWNS
# =========================

async def get_cooldown(user_id: int, action_key: str) -> int:
    row = await fetchrow(
        "SELECT last_at FROM user_cooldowns WHERE user_id=$1 AND action_key=$2",
        user_id,
        action_key,
    )
    return int(row["last_at"]) if row else 0


async def set_cooldown(user_id: int, action_key: str, ts: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_cooldowns(user_id, action_key, last_at)
            VALUES($1, $2, $3)
            ON CONFLICT(user_id, action_key) DO UPDATE SET last_at=EXCLUDED.last_at
            """,
            user_id,
            action_key,
            ts,
        )


# =========================
# RATING
# =========================

async def rate_order(order_id: int, client_user_id: int, rating: int, review_text: str = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND user_id=$2
                  AND status='done'
                FOR UPDATE
                """,
                order_id,
                client_user_id,
            )

            if not order:
                return None

            if order["rating"] is not None:
                return None

            master_user_id = order["selected_master_id"]
            if not master_user_id:
                return None

            await conn.execute(
                """
                UPDATE orders
                SET rating=$1,
                    review_text=$2,
                    updated_at=$3
                WHERE id=$4
                """,
                rating,
                review_text,
                now_ts(),
                order_id,
            )

            stats = await conn.fetchrow(
                """
                SELECT
                    COALESCE(AVG(rating), 0) AS avg_rating,
                    COUNT(rating) AS reviews_count
                FROM orders
                WHERE selected_master_id=$1
                  AND rating IS NOT NULL
                """,
                master_user_id,
            )

            await conn.execute(
                """
                UPDATE masters
                SET rating=$1,
                    reviews_count=$2,
                    updated_at=$4
                WHERE user_id=$3
                """,
                float(stats["avg_rating"] or 0),
                int(stats["reviews_count"] or 0),
                master_user_id,
                now_ts(),
            )

            updated_order = await conn.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)

    await add_order_event(
        order_id=order_id,
        event_type="order_rated",
        from_status="done",
        to_status="done",
        actor_user_id=client_user_id,
        actor_role="client",
        payload=f"rating={rating};review={'1' if review_text else '0'}",
    )

    return updated_order


# =========================
# NOTIFICATION JOBS
# =========================

async def create_notification_job(
    *,
    user_id: int,
    notification_type: str,
    order_id: Optional[int] = None,
    payload: Optional[str] = None,
    next_attempt_at: int = 0,
):
    ts = now_ts()
    row = await fetchrow(
        """
        INSERT INTO notification_jobs (
            user_id,
            order_id,
            notification_type,
            payload,
            status,
            attempts,
            error_text,
            next_attempt_at,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, 'pending', 0, NULL, $5, $6, $6)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        user_id,
        order_id,
        notification_type,
        payload,
        int(next_attempt_at or 0),
        ts,
    )
    return int(row["id"]) if row else None


async def claim_notification_jobs(limit: int = 10):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """
                SELECT *
                FROM notification_jobs
                WHERE status='pending'
                  AND COALESCE(next_attempt_at, 0) <= $1
                ORDER BY id ASC
                LIMIT $2
                FOR UPDATE SKIP LOCKED
                """,
                now_ts(),
                limit,
            )

            if not rows:
                return []

            job_ids = [row["id"] for row in rows]
            await conn.execute(
                """
                UPDATE notification_jobs
                SET status='processing',
                    attempts=COALESCE(attempts, 0) + 1,
                    updated_at=$1
                WHERE id = ANY($2::int[])
                """,
                now_ts(),
                job_ids,
            )

            return await conn.fetch(
                """
                SELECT *
                FROM notification_jobs
                WHERE id = ANY($1::int[])
                ORDER BY id ASC
                """,
                job_ids,
            )


async def mark_notification_job_sent(job_id: int):
    await execute(
        """
        UPDATE notification_jobs
        SET status='sent',
            error_text=NULL,
            updated_at=$1
        WHERE id=$2
        """,
        now_ts(),
        job_id,
    )


async def mark_notification_job_retry(job_id: int, error_text: str, next_attempt_at: int):
    await execute(
        """
        UPDATE notification_jobs
        SET status='pending',
            error_text=$1,
            next_attempt_at=$2,
            updated_at=$3
        WHERE id=$4
        """,
        str(error_text or "")[:1000],
        int(next_attempt_at),
        now_ts(),
        job_id,
    )


async def mark_notification_job_failed(job_id: int, error_text: str):
    await execute(
        """
        UPDATE notification_jobs
        SET status='failed',
            error_text=$1,
            updated_at=$2
        WHERE id=$3
        """,
        str(error_text or "")[:1000],
        now_ts(),
        job_id,
    )


# =========================
# PUBLIC MASTER LIST / REVIEWS
# =========================

async def list_public_masters_for_category(category: str, district: Optional[str] = None, limit: int = 10):
    """
    Public masters list for client "Майстри поруч".
    If district is provided, show only masters who selected this district or "Вся Одеса".
    """
    if district:
        return await fetch(
            """
            SELECT
                user_id,
                name,
                category,
                district,
                description,
                experience,
                photo,
                rating,
                reviews_count,
                availability,
                last_seen,
                status
            FROM masters
            WHERE status='approved'
              AND $1 = ANY(string_to_array(category, ','))
              AND (
                    $2 = ANY(string_to_array(COALESCE(district, ''), ','))
                    OR $3 = ANY(string_to_array(COALESCE(district, ''), ','))
              )
            ORDER BY
                CASE WHEN availability='online' THEN 0 ELSE 1 END,
                rating DESC,
                reviews_count DESC,
                last_seen DESC,
                name ASC
            LIMIT $4
            """,
            category,
            district,
            DISTRICT_ALL_ODESSA,
            limit,
        )

    return await fetch(
        """
        SELECT
            user_id,
            name,
            category,
            district,
            description,
            experience,
            photo,
            rating,
            reviews_count,
            availability,
            last_seen,
            status
        FROM masters
        WHERE status='approved'
          AND $1 = ANY(string_to_array(category, ','))
        ORDER BY
            CASE WHEN availability='online' THEN 0 ELSE 1 END,
            rating DESC,
            reviews_count DESC,
            last_seen DESC,
            name ASC
        LIMIT $2
        """,
        category,
        limit,
    )


async def get_public_master_profile(master_user_id: int):
    return await fetchrow(
        """
        SELECT
            user_id,
            name,
            category,
            district,
            description,
            experience,
            photo,
            rating,
            reviews_count,
            availability,
            last_seen,
            status
        FROM masters
        WHERE user_id=$1
          AND status='approved'
        """,
        master_user_id,
    )


async def get_master_reviews_page(master_user_id: int, page: int = 0, page_size: int = 5):
    """
    Paginated reviews for master profile.

    Returns:
    - master row with rating/reviews_count
    - reviews page
    - total reviews count
    - normalized page
    - page_size
    """
    page_size = max(1, min(int(page_size or 5), 10))
    page = max(0, int(page or 0))
    offset = page * page_size

    master = await fetchrow(
        """
        SELECT user_id, name, rating, reviews_count
        FROM masters
        WHERE user_id=$1
          AND status='approved'
        """,
        master_user_id,
    )

    total = await fetchval(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE selected_master_id=$1
          AND rating IS NOT NULL
        """,
        master_user_id,
    )
    total = int(total or 0)

    if total > 0 and offset >= total:
        page = max(0, (total - 1) // page_size)
        offset = page * page_size

    rows = await fetch(
        """
        SELECT
            id AS order_id,
            rating,
            review_text,
            updated_at,
            created_at
        FROM orders
        WHERE selected_master_id=$1
          AND rating IS NOT NULL
        ORDER BY updated_at DESC, created_at DESC, id DESC
        LIMIT $2 OFFSET $3
        """,
        master_user_id,
        page_size,
        offset,
    )

    return {
        "master": master,
        "reviews": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_master_recent_reviews(master_user_id: int, limit: int = 5):
    return await fetch(
        """
        SELECT
            id AS order_id,
            rating,
            review_text,
            updated_at,
            created_at
        FROM orders
        WHERE selected_master_id=$1
          AND rating IS NOT NULL
        ORDER BY updated_at DESC, created_at DESC
        LIMIT $2
        """,
        master_user_id,
        limit,
    )


async def get_master_public_profile(master_user_id: int):
    return await get_public_master_profile(master_user_id)


async def get_master_reviews(master_user_id: int, limit: int = 5):
    return await get_master_recent_reviews(master_user_id, limit)

# =========================
# BLOCKED USERS
# =========================

async def ensure_blocked_users_table() -> None:
    """
    Backward-compatible runtime setup for blocked_users.

    Used by admin/client logic to block abusive clients or users.
    Safe to call multiple times.
    """
    await execute(
        """
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id BIGINT PRIMARY KEY,
            reason TEXT,
            blocked_by_admin_id BIGINT,
            created_at BIGINT
        )
        """
    )


async def block_user(user_id: int, admin_user_id: int, reason: Optional[str] = None) -> None:
    """
    Block a user from client/user actions.

    For now this is used mainly for clients, but the table is generic by user_id.
    """
    await ensure_blocked_users_table()

    await execute(
        """
        INSERT INTO blocked_users (
            user_id,
            reason,
            blocked_by_admin_id,
            created_at
        )
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id) DO UPDATE SET
            reason=EXCLUDED.reason,
            blocked_by_admin_id=EXCLUDED.blocked_by_admin_id,
            created_at=EXCLUDED.created_at
        """,
        int(user_id),
        reason,
        int(admin_user_id) if admin_user_id is not None else None,
        now_ts(),
    )


async def unblock_user(user_id: int) -> None:
    """
    Remove user block.
    """
    await ensure_blocked_users_table()

    await execute(
        """
        DELETE FROM blocked_users
        WHERE user_id=$1
        """,
        int(user_id),
    )


async def is_user_blocked(user_id: int) -> bool:
    """
    Return True if user is blocked.
    """
    await ensure_blocked_users_table()

    row = await fetchrow(
        """
        SELECT 1
        FROM blocked_users
        WHERE user_id=$1
        """,
        int(user_id),
    )
    return bool(row)


async def get_user_block_row(user_id: int):
    """
    Return block row for user, or None.
    """
    await ensure_blocked_users_table()

    return await fetchrow(
        """
        SELECT *
        FROM blocked_users
        WHERE user_id=$1
        """,
        int(user_id),
    )

# =========================
# ADMIN USER SUMMARY
# =========================

async def get_user_admin_summary(user_id: int) -> dict:
    """
    Aggregated user history for admin panel.

    Shows:
    - orders totals and statuses;
    - complaints from / against this user;
    - master profile status if user is also a master;
    - block status.
    """
    user_id = int(user_id)
    await ensure_blocked_users_table()

    orders_row = await fetchrow(
        """
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE status IN ('new', 'offered', 'matched', 'in_progress')) AS active_orders,
            COUNT(*) FILTER (WHERE status='done') AS done_orders,
            COUNT(*) FILTER (WHERE status='cancelled') AS cancelled_orders,
            COUNT(*) FILTER (WHERE status='expired') AS expired_orders,
            COUNT(*) FILTER (WHERE is_suspect IS TRUE) AS suspect_orders,
            MIN(created_at) AS first_order_at,
            MAX(created_at) AS last_order_at
        FROM orders
        WHERE user_id=$1
        """,
        user_id,
    )

    complaints_from_row = await fetchrow(
        """
        SELECT COUNT(*) AS c
        FROM complaints
        WHERE from_user_id=$1
        """,
        user_id,
    )

    complaints_against_row = await fetchrow(
        """
        SELECT COUNT(*) AS c
        FROM complaints
        WHERE against_user_id=$1
        """,
        user_id,
    )

    master_row = await fetchrow(
        """
        SELECT
            id,
            user_id,
            name,
            status,
            rating,
            reviews_count,
            category,
            district,
            availability,
            last_seen
        FROM masters
        WHERE user_id=$1
        ORDER BY id DESC
        LIMIT 1
        """,
        user_id,
    )

    block_row = await get_user_block_row(user_id)

    return {
        "user_id": user_id,
        "total_orders": int(orders_row["total_orders"] or 0) if orders_row else 0,
        "active_orders": int(orders_row["active_orders"] or 0) if orders_row else 0,
        "done_orders": int(orders_row["done_orders"] or 0) if orders_row else 0,
        "cancelled_orders": int(orders_row["cancelled_orders"] or 0) if orders_row else 0,
        "expired_orders": int(orders_row["expired_orders"] or 0) if orders_row else 0,
        "suspect_orders": int(orders_row["suspect_orders"] or 0) if orders_row else 0,
        "first_order_at": orders_row["first_order_at"] if orders_row else None,
        "last_order_at": orders_row["last_order_at"] if orders_row else None,
        "complaints_from": int(complaints_from_row["c"] or 0) if complaints_from_row else 0,
        "complaints_against": int(complaints_against_row["c"] or 0) if complaints_against_row else 0,
        "is_blocked": bool(block_row),
        "block_reason": block_row["reason"] if block_row else None,
        "blocked_by_admin_id": block_row["blocked_by_admin_id"] if block_row else None,
        "blocked_at": block_row["created_at"] if block_row else None,
        "master": master_row,
    }

