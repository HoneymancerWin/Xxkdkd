"""Оценка рыночной цены."""
from __future__ import annotations

import statistics


def market_price(prices: list[int], trim: float = 0.1) -> float | None:
    """Медиана после отсечения краёв (мусор за 1 ₽ и «космос» не влияют)."""
    values = sorted(p for p in prices if p and p > 0)
    if not values:
        return None
    k = int(len(values) * trim)
    if k and len(values) - 2 * k >= 3:
        values = values[k:-k]
    return statistics.median(values)
