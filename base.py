from modules.async_.db.async_req import db

SQL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        tg_id         INTEGER PRIMARY KEY,
        username      TEXT,
        first_name    TEXT,
        last_name     TEXT,
        language_code TEXT,
        is_premium    INTEGER DEFAULT 0,
        first_seen    TEXT DEFAULT CURRENT_TIMESTAMP,
        last_seen     TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS briefs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id         INTEGER NOT NULL,
        status        TEXT NOT NULL,
        purchase      TEXT,
        communication TEXT,
        mounting      TEXT,
        service       TEXT,
        screen_size   TEXT,
        city          TEXT,
        phone         TEXT,
        email         TEXT,
        created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_briefs_tg_id     ON briefs(tg_id)",
    "CREATE INDEX IF NOT EXISTS idx_briefs_created   ON briefs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_users_username   ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_users_last_seen  ON users(last_seen DESC)",
]


async def create_tables():
    for stmt in SQL_STATEMENTS:
        await db.execute(stmt)
