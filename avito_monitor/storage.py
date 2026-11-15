"""SQLite: просмотренные объявления, цены по моделям, находки/покупки, настройки."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any

from .market import market_price


class Storage:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS seen (
                    search TEXT NOT NULL, item_id TEXT NOT NULL, price INTEGER, first_seen REAL NOT NULL,
                    PRIMARY KEY (search, item_id));
                CREATE TABLE IF NOT EXISTS market (
                    cat TEXT NOT NULL, item_id TEXT NOT NULL, model TEXT NOT NULL, variant TEXT,
                    price INTEGER NOT NULL, ts REAL NOT NULL, PRIMARY KEY (cat, item_id));
                CREATE INDEX IF NOT EXISTS market_model ON market(cat, model, variant);
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, cat TEXT, item_id TEXT, model TEXT, title TEXT,
                    url TEXT, price INTEGER, market REAL, score REAL, ts REAL,
                    status TEXT DEFAULT 'new', sold_price INTEGER, bought_ts REAL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
                """
            )

    # --- просмотренные ---
    def has_any(self, search: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM seen WHERE search=? LIMIT 1", (search,)).fetchone() is not None

    def seen_price(self, search: str, item_id: str) -> tuple[bool, int | None]:
        with self.lock:
            row = self.db.execute("SELECT price FROM seen WHERE search=? AND item_id=?",
                                  (search, item_id)).fetchone()
        return (row is not None, row[0] if row else None)

    def mark_seen(self, search: str, item_id: str, price: int | None) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO seen(search, item_id, price, first_seen) VALUES(?,?,?,?) "
                "ON CONFLICT(search, item_id) DO UPDATE SET price=excluded.price",
                (search, item_id, price, time.time()))

    # --- рынок ---
    def record_price(self, cat: str, item_id: str, model: str, variant: str | None, price: int) -> None:
        with self.lock:
            self.db.execute(
                "INSERT INTO market(cat, item_id, model, variant, price, ts) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(cat, item_id) DO UPDATE SET price=excluded.price, ts=excluded.ts, "
                "model=excluded.model, variant=excluded.variant",
                (cat, item_id, model, variant, price, time.time()))

    def market_for(self, cat: str, model: str, variant: str | None, days: float,
                   min_samples: int) -> tuple[float | None, int, str]:
        """(цена, сколько объявлений, по чему считали). Сначала точная версия, иначе вся модель."""
        since = time.time() - days * 86400
        with self.lock:
            if variant:
                rows = [r[0] for r in self.db.execute(
                    "SELECT price FROM market WHERE cat=? AND model=? AND variant=? AND ts>=?",
                    (cat, model, variant, since))]
                if len(rows) >= min_samples:
                    return market_price(rows), len(rows), f"{model} {variant}"
            rows = [r[0] for r in self.db.execute(
                "SELECT price FROM market WHERE cat=? AND model=? AND ts>=?", (cat, model, since))]
        if len(rows) >= min_samples:
            return market_price(rows), len(rows), model
        return None, len(rows), model

    def market_overview(self, cat: str, days: float, limit: int = 10) -> list[tuple[str, float, int]]:
        since = time.time() - days * 86400
        with self.lock:
            groups = self.db.execute(
                "SELECT model, COALESCE(variant,'') v, COUNT(*) n FROM market WHERE cat=? AND ts>=? "
                "GROUP BY model, v ORDER BY n DESC LIMIT ?", (cat, since, limit)).fetchall()
            out = []
            for g in groups:
                prices = [r[0] for r in self.db.execute(
                    "SELECT price FROM market WHERE cat=? AND model=? AND COALESCE(variant,'')=? AND ts>=?",
                    (cat, g["model"], g["v"], since))]
                out.append((f"{g['model']} {g['v']}".strip(), market_price(prices), g["n"]))
        return out

    # --- находки и покупки ---
    def add_deal(self, **kw: Any) -> int:
        kw.setdefault("ts", time.time())
        cols = ",".join(kw)
        with self.lock:
            cur = self.db.execute(f"INSERT INTO deals({cols}) VALUES({','.join('?' * len(kw))})",
                                  tuple(kw.values()))
            self.db.commit()
            return cur.lastrowid

    def deal(self, deal_id: int) -> sqlite3.Row | None:
        with self.lock:
            return self.db.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()

    def set_deal(self, deal_id: int, **kw: Any) -> None:
        with self.lock:
            self.db.execute(f"UPDATE deals SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                            (*kw.values(), deal_id))
            self.db.commit()

    def deals(self, statuses: tuple[str, ...], limit: int = 10) -> list[sqlite3.Row]:
        with self.lock:
            return self.db.execute(
                f"SELECT * FROM deals WHERE status IN ({','.join('?' * len(statuses))}) "
                "ORDER BY COALESCE(bought_ts, ts) DESC LIMIT ?", (*statuses, limit)).fetchall()

    def deals_count_since(self, since: float) -> int:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM deals WHERE ts>=?", (since,)).fetchone()[0]

    # --- настройки ---
    def get(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        with self.lock:
            self.db.execute("INSERT INTO settings(key, value) VALUES(?,?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value)))
            self.db.commit()

    def commit(self) -> None:
        with self.lock:
            self.db.commit()
