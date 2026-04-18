import asyncpg

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
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM masters WHERE user_id=$1",
            data["user_id"],
        )

        if row:
            await conn.execute(
                """
                UPDATE masters
                SET name=$1,
                    category=$2,
                    district=$3,
                    description=$4,
                    experience=$5,
                    phone=$6,
                    photo=$7,
                    status='pending'
                WHERE user_id=$8
                """,
                data.get("name"),
                data.get("category"),
                data.get("district"),
                data.get("description"),
                data.get("experience"),
                data.get("phone"),
                data.get("photo"),
                data["user_id"],
            )
        else:
            await conn.execute(
                """
                INSERT INTO masters (
                    user_id,
                    name,
                    category,
                    district,
                    phone,
                    description,
                    experience,
                    photo,
                    rating,
                    reviews_count,
                    status,
                    availability,
                    last_seen
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,0,0,'pending','offline',0)
                """,
                data["user_id"],
                data.get("name"),
                data.get("category"),
                data.get("district"),
                data.get("phone"),
                data.get("description"),
                data.get("experience"),
                data.get("photo"),
            )


async def update_master_profile(user_id: int, field: str, value):
    allowed = {"name", "district", "phone", "description", "experience", "photo"}
    if field not in allowed:
        raise ValueError(f"Unsupported field: {field}")

    query = f"UPDATE masters SET {field}=$1 WHERE user_id=$2"
    return await execute(query, value, user_id)


async def touch_master_presence(user_id: int):
    return await execute(
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


async def get_master_name(master_user_id):
    if not master_user_id:
        return "—"

    row = await fetchrow(
        "SELECT name FROM masters WHERE user_id=$1",
        master_user_id,
    )
    return row["name"] if row else "—"


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
    media_type: str = None,
    media_file_id: str = None,
    client_phone: str = None,
):
    row = await fetchrow(
        """
        INSERT INTO orders (
            user_id,
            category,
            district,
            problem,
            client_phone,
            media_type,
            media_file_id,
            status,
            created_at,
            updated_at
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7,
            'new',
            EXTRACT(EPOCH FROM NOW())::BIGINT,
            EXTRACT(EPOCH FROM NOW())::BIGINT
        )
        RETURNING id
        """,
        user_id,
        category,
        district,
        problem,
        client_phone,
        media_type,
        media_file_id,
    )
    return row["id"]


async def get_order_row(order_id: int):
    return await fetchrow(
        "SELECT * FROM orders WHERE id=$1",
        order_id,
    )


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
                VALUES ($1,$2,$3,$4,$5,'active',EXTRACT(EPOCH FROM NOW())::BIGINT)
                RETURNING id
                """,
                order_id,
                master_user_id,
                price,
                eta,
                comment,
            )

            await conn.execute(
                """
                UPDATE orders
                SET status='offered',
                    updated_at=EXTRACT(EPOCH FROM NOW())::BIGINT
                WHERE id=$1
                """,
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
                    updated_at=EXTRACT(EPOCH FROM NOW())::BIGINT
                WHERE id=$2
                """,
                offer["master_user_id"],
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

            existing_chat = await conn.fetchrow(
                """
                SELECT *
                FROM chats
                WHERE order_id=$1
                """,
                offer["order_id"],
            )

            if existing_chat:
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
                    existing_chat["id"],
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
                    VALUES ($1,$2,$3,'active',EXTRACT(EPOCH FROM NOW())::BIGINT)
                    """,
                    offer["order_id"],
                    client_user_id,
                    offer["master_user_id"],
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
        """
        SELECT *
        FROM chats
        WHERE order_id=$1
        """,
        order_id,
    )


async def create_chat_message(
    chat_id: int,
    order_id: int,
    sender_user_id: int,
    sender_role: str,
    media_type: str,
    message_text: str = None,
    media_file_id: str = None,
):
    return await execute(
        """
        INSERT INTO chat_messages (
            chat_id,
            order_id,
            sender_user_id,
            sender_role,
            message_text,
            media_type,
            media_file_id,
            created_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,EXTRACT(EPOCH FROM NOW())::BIGINT)
        """,
        chat_id,
        order_id,
        sender_user_id,
        sender_role,
        message_text,
        media_type,
        media_file_id,
    )


async def get_chat_history(order_id: int, limit: int = 30):
    return await fetch(
        """
        SELECT
            sender_user_id,
            sender_role,
            message_text AS text,
            media_type AS message_type,
            media_file_id,
            created_at
        FROM chat_messages
        WHERE order_id=$1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        order_id,
        limit,
    )


# =========================
# SUPPORT / COMPLAINTS
# =========================

async def add_support_message(from_user_id: int, text: str):
    return await execute(
        """
        INSERT INTO support_messages (
            from_user_id,
            text,
            created_at
        )
        VALUES ($1,$2,EXTRACT(EPOCH FROM NOW())::BIGINT)
        """,
        from_user_id,
        text,
    )


async def add_complaint(
    order_id: int,
    from_user_id: int,
    against_user_id: int,
    against_role: str,
    text: str,
):
    return await execute(
        """
        INSERT INTO complaints (
            order_id,
            from_user_id,
            against_user_id,
            against_role,
            text,
            created_at
        )
        VALUES ($1,$2,$3,$4,$5,EXTRACT(EPOCH FROM NOW())::BIGINT)
        """,
        order_id,
        from_user_id,
        against_user_id,
        against_role,
        text,
    )


# =========================
# COOLDOWNS
# =========================

async def get_cooldown(user_id: int, action_key: str) -> int:
    row = await fetchrow(
        """
        SELECT last_at
        FROM user_cooldowns
        WHERE user_id=$1 AND action_key=$2
        """,
        user_id,
        action_key,
    )
    return int(row["last_at"]) if row else 0


async def set_cooldown(user_id: int, action_key: str, ts: int):
    return await execute(
        """
        INSERT INTO user_cooldowns (user_id, action_key, last_at)
        VALUES ($1,$2,$3)
        ON CONFLICT (user_id, action_key)
        DO UPDATE SET last_at = EXCLUDED.last_at
        """,
        user_id,
        action_key,
        ts,
    )
