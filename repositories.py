async def choose_offer(offer_id: int, client_user_id: int):
    pool = get_pool()
    ts = now_ts()

    async with pool.acquire() as conn:
        async with conn.transaction():
            offer = await conn.fetchrow(
                '''
                SELECT offers.*, orders.user_id AS client_user_id, orders.id AS order_id
                FROM offers
                JOIN orders ON offers.order_id = orders.id
                WHERE offers.id=$1 AND offers.status='active'
                FOR UPDATE
                ''',
                offer_id
            )

            if not offer or int(offer["client_user_id"]) != client_user_id:
                return None

            order_id = int(offer["order_id"])
            master_user_id = int(offer["master_user_id"])

            await conn.execute(
                "UPDATE offers SET status='rejected' WHERE order_id=$1 AND status='active'",
                order_id
            )

            await conn.execute(
                "UPDATE offers SET status='selected' WHERE id=$1",
                offer_id
            )

            await conn.execute(
                '''
                UPDATE orders
                SET selected_master_id=$1, status='matched', updated_at=$2
                WHERE id=$3
                ''',
                master_user_id, ts, order_id
            )

            existing_chat = await conn.fetchrow(
                "SELECT id FROM chats WHERE order_id=$1",
                order_id
            )

            if existing_chat:
                await conn.execute(
                    '''
                    UPDATE chats
                    SET client_user_id=$1,
                        master_user_id=$2,
                        status='active',
                        updated_at=$3
                    WHERE order_id=$4
                    ''',
                    client_user_id, master_user_id, ts, order_id
                )
            else:
                await conn.execute(
                    '''
                    INSERT INTO chats(order_id, client_user_id, master_user_id, status, created_at, updated_at)
                    VALUES($1, $2, $3, 'active', $4, $4)
                    ''',
                    order_id, client_user_id, master_user_id, ts
                )

            return offer
