from typing import Optional

from db import get_pool
from utils import now_ts


# =========================
# BASE HELPERS
# =========================

async def fetch(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


# =========================
# MASTERS
# =========================

async def master_any_row(user_id: int):
    return await fetchrow(
        "SELECT * FROM masters WHERE user_id=$1",
        user_id,
    )


async def approved_master_row(user_id: int):
    return await fetchrow(
        "SELECT * FROM masters WHERE user_id=$1 AND status='approved'",
        user_id,
    )


async def create_or_update_master(data: dict):
    ts = now_ts()
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO masters(
                user_id, name, category, district, phone, description, experience, photo,
                rating, reviews_count, status, availability, last_seen
            )
            VALUES($1, $2, $3, $4, $5, $6, $7, $8, 0, 0, 'pending', 'offline', $9)
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
                last_seen=EXCLUDED.last_seen
            """,
            data["user_id"],
            data.get("name"),
            data.get("category"),
            data.get("district"),
            data.get("phone"),
            data.get("description"),
            data.get("experience"),
            data.get("photo"),
            ts,
        )


async def update_master_profile(user_id: int, field_name: str, value):
    allowed = {"name", "district", "phone", "description", "experience", "photo"}
    if field_name not in allowed:
        raise ValueError(f"Unsupported field: {field_name}")

    query = f"UPDATE masters SET {field_name}=$1 WHERE user_id=$2"
    await execute(query, value, user_id)


async def touch_master_presence(user_id: int):
    await execute(
        """
        UPDATE masters
        SET availability='online',
            last_seen=$1
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


async def list_new_orders_for_master(category: str):
    return await fetch(
        """
        SELECT *
        FROM orders
        WHERE category=$1
          AND status = ANY($2::text[])
        ORDER BY created_at DESC
        LIMIT 50
        """,
        category,
        ["new", "offered"],
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
    if availability:
        await execute(
            "UPDATE masters SET status=$1, availability=$2 WHERE id=$3",
            status,
            availability,
            master_id,
        )
    else:
        await execute(
            "UPDATE masters SET status=$1 WHERE id=$2",
            status,
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
    return rows, int(total["c"])


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
    return rows, int(total["c"])


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


async def create_order(
    user_id: int,
    category: str,
    district: str,
    problem: str,
    media_type: Optional[str] = None,
    media_file_id: Optional[str] = None,
    client_phone: Optional[str] = None,
) -> int:
    ts = now_ts()
    row = await fetchrow(
        """
        INSERT INTO orders(
            user_id, category, district, problem, client_phone,
            media_type, media_file_id, status, created_at, updated_at
        )
        VALUES($1, $2, $3, $4, $5, $6, $7, 'new', $8, $8)
        RETURNING id
        """,
        user_id,
        category,
        district,
        problem,
        client_phone,
        media_type,
        media_file_id,
        ts,
    )
    return int(row["id"])


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
    return rows, int(total["c"])


async def set_order_status(order_id: int, status: str, selected_master_id=None):
    await execute(
        """
        UPDATE orders
        SET status=$1,
            selected_master_id=$2,
            updated_at=$3
        WHERE id=$4
        """,
        status,
        selected_master_id,
        now_ts(),
        order_id,
    )


async def cancel_order(order_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
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


async def refuse_order(order_id: int):
    await execute(
        """
        UPDATE orders
        SET selected_master_id=NULL,
            status='offered',
            updated_at=$1
        WHERE id=$2
        """,
        now_ts(),
        order_id,
    )
    await close_chat(order_id)


async def finish_order(order_id: int):
    await execute(
        "UPDATE orders SET status='done', updated_at=$1 WHERE id=$2",
        now_ts(),
        order_id,
    )
    await close_chat(order_id)


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
        data[key] = int(row["c"])
    return data


# =========================
# OFFERS
# =========================

async def create_offer(
    order_id: int,
    master_user_id: int,
    price: str,
    eta: str,
    comment: str,
):
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order = await conn.fetchrow(
                """
                SELECT *
                FROM orders
                WHERE id=$1
                  AND status = ANY($2::text[])
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
                RETURNING id
                """,
                order_id,
                master_user_id,
                price,
                eta,
                comment,
                now_ts(),
            )

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

            return row["id"]


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
            masters.category
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

            chat = await conn.fetchrow(
                "SELECT * FROM chats WHERE order_id=$1",
                offer["order_id"],
            )

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

            return await conn.fetchrow(
                "SELECT * FROM offers WHERE id=$1",
                offer_id,
            )


# =========================
# CHATS
# =========================

async def get_chat_for_order(order_id: int):
    return await fetchrow(
        "SELECT * FROM chats WHERE order_id=$1 ORDER BY id DESC LIMIT 1",
        order_id,
    )


async def close_chat(order_id: int):
    await execute(
        "UPDATE chats SET status='closed' WHERE order_id=$1",
        order_id,
    )


async def create_chat_message(
    chat_id: int,
    order_id: int,
    sender_user_id: int,
    sender_role: str,
    message_type: str,
    text: Optional[str],
    file_id: Optional[str],
):
    await execute(
        """
        INSERT INTO chat_messages(
            chat_id, order_id, sender_user_id, sender_role,
            message_type, text, file_id, created_at
        )
        VALUES($1, $2, $3, $4, $5, $6, $7, $8)
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
                    reviews_count=$2
                WHERE user_id=$3
                """,
                float(stats["avg_rating"] or 0),
                int(stats["reviews_count"] or 0),
                master_user_id,
            )

            return await conn.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)
