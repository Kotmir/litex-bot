"""Асинхронная работа с SQLite через aiosqlite."""
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS verifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    support_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    action     TEXT    NOT NULL CHECK (action IN ('accept', 'denied')),
    reason     TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verifications_support
    ON verifications (support_id, created_at);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    verification_id INTEGER UNIQUE REFERENCES verifications (id) ON DELETE SET NULL,
    support_id      INTEGER NOT NULL,
    author_id       INTEGER NOT NULL,
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    date            TEXT    NOT NULL,
    created_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reviews_support
    ON reviews (support_id, created_at);

CREATE TABLE IF NOT EXISTS voice_time (
    support_id    INTEGER PRIMARY KEY,
    total_seconds INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    # ───────────────────────── жизненный цикл ─────────────────────────
    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База данных не подключена")
        return self._conn

    async def _fetchone(self, sql: str, params: tuple = ()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()):
        async with self.conn.execute(sql, params) as cur:
            return await cur.fetchall()

    # ─────────────────────────── верификации ──────────────────────────
    async def add_verification(
        self,
        support_id: int,
        user_id: int,
        action: str,
        reason: str | None,
        created_at: int,
    ) -> int:
        cur = await self.conn.execute(
            "INSERT INTO verifications (support_id, user_id, action, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (support_id, user_id, action, reason, created_at),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_verification(self, verification_id: int):
        return await self._fetchone(
            "SELECT * FROM verifications WHERE id = ?", (verification_id,)
        )

    async def count_actions(self, support_id: int, since: int | None = None) -> tuple[int, int]:
        """(принято, отказано) саппорта; since — unix-время начала периода."""
        row = await self._fetchone(
            "SELECT COALESCE(SUM(action = 'accept'), 0), COALESCE(SUM(action = 'denied'), 0) "
            "FROM verifications WHERE support_id = ? AND created_at >= ?",
            (support_id, since or 0),
        )
        return int(row[0]), int(row[1])

    async def get_top(self):
        return await self._fetchall(
            "SELECT support_id, "
            "       SUM(action = 'accept') AS accepted, "
            "       SUM(action = 'denied') AS denied, "
            "       COUNT(*)               AS total "
            "FROM verifications GROUP BY support_id "
            "ORDER BY total DESC, accepted DESC, support_id ASC"
        )

    async def has_activity(self, support_id: int) -> bool:
        row = await self._fetchone(
            "SELECT (SELECT COUNT(*) FROM verifications WHERE support_id = ?) "
            "     + (SELECT COUNT(*) FROM reviews WHERE support_id = ?) "
            "     + (SELECT COALESCE(SUM(total_seconds), 0) FROM voice_time WHERE support_id = ?)",
            (support_id, support_id, support_id),
        )
        return bool(row[0])

    # ───────────────────────────── отзывы ─────────────────────────────
    async def review_exists(self, verification_id: int) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM reviews WHERE verification_id = ?", (verification_id,)
        )
        return row is not None

    async def add_review(
        self,
        verification_id: int,
        support_id: int,
        author_id: int,
        rating: int,
        comment: str | None,
        date: str,
        created_at: int,
    ) -> int | None:
        """Сохраняет отзыв. None — если на эту проверку отзыв уже оставлен."""
        try:
            cur = await self.conn.execute(
                "INSERT INTO reviews "
                "(verification_id, support_id, author_id, rating, comment, date, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (verification_id, support_id, author_id, rating, comment, date, created_at),
            )
            await self.conn.commit()
            return cur.lastrowid
        except aiosqlite.IntegrityError:
            return None

    async def get_rating(self, support_id: int) -> tuple[float | None, int]:
        """(средняя оценка | None, количество отзывов)."""
        row = await self._fetchone(
            "SELECT AVG(rating), COUNT(*) FROM reviews WHERE support_id = ?", (support_id,)
        )
        avg = float(row[0]) if row[0] is not None else None
        return avg, int(row[1])

    async def count_reviews(self, support_id: int) -> int:
        row = await self._fetchone(
            "SELECT COUNT(*) FROM reviews WHERE support_id = ?", (support_id,)
        )
        return int(row[0])

    async def get_reviews(self, support_id: int, limit: int, offset: int):
        return await self._fetchall(
            "SELECT * FROM reviews WHERE support_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (support_id, limit, offset),
        )

    # ─────────────────────── время в проходной ────────────────────────
    async def add_voice_time(self, support_id: int, seconds: int) -> None:
        await self.conn.execute(
            "INSERT INTO voice_time (support_id, total_seconds) VALUES (?, ?) "
            "ON CONFLICT(support_id) DO UPDATE SET total_seconds = total_seconds + excluded.total_seconds",
            (support_id, int(seconds)),
        )
        await self.conn.commit()

    async def get_voice_time(self, support_id: int) -> int:
        row = await self._fetchone(
            "SELECT total_seconds FROM voice_time WHERE support_id = ?", (support_id,)
        )
        return int(row[0]) if row else 0
