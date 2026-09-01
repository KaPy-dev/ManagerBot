from modules.async_.db.async_req import db

PER_PAGE = 8


async def upsert_user(user):
    await db.execute(
        """
        INSERT INTO users (tg_id, username, first_name, last_name, language_code, is_premium)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(tg_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            language_code = excluded.language_code,
            is_premium = excluded.is_premium,
            last_seen = CURRENT_TIMESTAMP
        """,
        (user.id, user.username, user.first_name, user.last_name,
         user.language_code, 1 if user.is_premium else 0),
    )


async def get_user(tg_id: int):
    return await db.fetch_one("SELECT * FROM users WHERE tg_id = ?", (tg_id,))


async def count_users() -> int:
    row = await db.fetch_one("SELECT COUNT(*) AS c FROM users")
    return row["c"] if row else 0


async def get_users_page(page: int, per_page: int = PER_PAGE):
    return await db.fetch_all(
        "SELECT * FROM users ORDER BY last_seen DESC LIMIT ? OFFSET ?",
        (per_page, page * per_page),
    )


async def search_users(query: str, limit: int = 10):
    like = f"%{query}%"
    return await db.fetch_all(
        """
        SELECT * FROM users
        WHERE CAST(tg_id AS TEXT) LIKE ?
           OR LOWER(COALESCE(username, '')) LIKE LOWER(?)
           OR LOWER(COALESCE(first_name, '')) LIKE LOWER(?)
        ORDER BY last_seen DESC LIMIT ?
        """,
        (like, like, like, limit),
    )


async def find_by_username(username: str):
    return await db.fetch_one(
        "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,)
    )


async def save_brief(tg_id: int, status: str, data: dict):
    await db.execute(
        """
        INSERT INTO briefs (tg_id, status, purchase, communication, mounting,
                            service, screen_size, city, phone, email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tg_id, status, data.get("purchase"), data.get("communication"),
         data.get("mounting"), data.get("service"), data.get("screen_size"),
         data.get("city"), data.get("phone"), data.get("email")),
    )


async def user_dossier(tg_id: int):
    user = await get_user(tg_id)
    if not user:
        return None
    stats = await db.fetch_all(
        "SELECT status, COUNT(*) AS c FROM briefs WHERE tg_id = ? GROUP BY status", (tg_id,)
    )
    last = await db.fetch_one(
        "SELECT * FROM briefs WHERE tg_id = ? ORDER BY id DESC LIMIT 1", (tg_id,)
    )
    counts = {row["status"]: row["c"] for row in stats}
    return {"user": user, "counts": counts, "last_brief": last}
