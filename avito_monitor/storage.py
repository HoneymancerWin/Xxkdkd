"""SQLite: просмотренные объявления и история цен для расчёта рынка."""
from __future__ import annotations

import sqlite3
import time


class Storage:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen (
                search TEXT NOT NULL,
                item_id TEXT NOT NULL,
                price INTEGER,
                first_seen REAL NOT NULL,
                PRIMARY KEY (search, item_id)
            );
            CREATE TABLE IF NOT EXISTS prices (
                search TEXT NOT NULL,
                item_id TEXT NOT NULL,
                price INTEGER NOT NULL,
                ts REAL NOT NULL,
                PRIMARY KEY (search, item_id)
            );
            """
        )

    def has_any(self, search: str) -> bool:
        return self.db.execute("SELECT 1 FROM seen WHERE search=? LIMIT 1", (search,)).fetchone() is not None

    def seen_price(self, search: str, item_id: str) -> tuple[bool, int | None]:
        row = self.db.execute(
            "SELECT price FROM seen WHERE search=? AND item_id=?", (search, item_id)
        ).fetchone()
        return (row is not None, row[0] if row else None)

    def mark_seen(self, search: str, item_id: str, price: int | None) -> None:
        self.db.execute(
            "INSERT INTO seen(search, item_id, price, first_seen) VALUES(?,?,?,?) "
            "ON CONFLICT(search, item_id) DO UPDATE SET price=excluded.price",
            (search, item_id, price, time.time()),
        )

    def record_price(self, search: str, item_id: str, price: int) -> None:
        self.db.execute(
            "INSERT INTO prices(search, item_id, price, ts) VALUES(?,?,?,?) "
            "ON CONFLICT(search, item_id) DO UPDATE SET price=excluded.price, ts=excluded.ts",
            (search, item_id, price, time.time()),
        )

    def recent_prices(self, search: str, days: float) -> list[int]:
        since = time.time() - days * 86400
        return [r[0] for r in self.db.execute(
            "SELECT price FROM prices WHERE search=? AND ts>=?", (search, since)
        )]

    def commit(self) -> None:
        self.db.commit()
