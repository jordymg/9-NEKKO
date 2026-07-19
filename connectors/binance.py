"""Read-only Binance connector (public REST API, no keys).

Returns normalized dicts only — nothing outside /connectors knows API shapes.
Provides spot price, klines, and realized volatility (annualized, from log
returns) as reference-model inputs (ARCHITECTURE.md §2).
"""
from __future__ import annotations

import logging
import math
import time
from typing import Any, Iterator

import requests

log = logging.getLogger(__name__)

BASE = "https://api.binance.com"

KLINES_MAX_LIMIT = 1000  # API cap per request

_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}

_MS_PER_YEAR = 365 * 86_400_000

_session = requests.Session()


def _get(path: str, params: dict[str, Any] | None = None, retries: int = 5) -> Any:
    """GET with retry + exponential backoff (handles rate limits / 5xx)."""
    backoff = 1.0
    for attempt in range(retries):
        try:
            resp = _session.get(f"{BASE}{path}", params=params, timeout=30)
            if resp.status_code in (418, 429) or resp.status_code >= 500:
                resp.raise_for_status()
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries - 1:
                raise
            log.warning("GET %s failed (%s), retry in %.0fs", path, exc, backoff)
            time.sleep(backoff)
            backoff *= 2


def get_spot(symbol: str = "BTCUSDT") -> dict:
    """Current spot price. Returns {"symbol", "price", "ts"} (ts = epoch ms, local)."""
    d = _get("/api/v3/ticker/price", {"symbol": symbol})
    return {"symbol": d["symbol"], "price": float(d["price"]), "ts": int(time.time() * 1000)}


def _normalize_kline(k: list) -> dict:
    return {
        "open_time": int(k[0]),
        "open": float(k[1]),
        "high": float(k[2]),
        "low": float(k[3]),
        "close": float(k[4]),
        "volume": float(k[5]),
        "close_time": int(k[6]),
    }


def get_klines(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    start_ms: int | None = None,
    end_ms: int | None = None,
    limit: int = 500,
) -> list[dict]:
    """One page of candles (max 1000). Times are epoch ms."""
    params: dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": min(limit, KLINES_MAX_LIMIT)}
    if start_ms is not None:
        params["startTime"] = start_ms
    if end_ms is not None:
        params["endTime"] = end_ms
    return [_normalize_kline(k) for k in _get("/api/v3/klines", params)]


def iter_klines(
    symbol: str, interval: str, start_ms: int, end_ms: int
) -> Iterator[dict]:
    """All candles in [start_ms, end_ms), paginating past the 1000-per-request cap."""
    cursor = start_ms
    while cursor < end_ms:
        page = get_klines(symbol, interval, start_ms=cursor, end_ms=end_ms, limit=KLINES_MAX_LIMIT)
        if not page:
            return
        for k in page:
            if k["open_time"] >= end_ms:
                return
            yield k
        cursor = page[-1]["open_time"] + _INTERVAL_MS[interval]


def realized_vol(closes: list[float], interval: str) -> float:
    """Annualized realized volatility from close-to-close log returns.

    Model input per ARCHITECTURE.md (lognormal baseline). Needs >= 3 closes.
    """
    if len(closes) < 3:
        raise ValueError("need at least 3 closes to estimate vol")
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    periods_per_year = _MS_PER_YEAR / _INTERVAL_MS[interval]
    return math.sqrt(var) * math.sqrt(periods_per_year)


def realized_vol_at(
    ts_ms: int,
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    lookback: int = 168,
) -> dict:
    """Spot and annualized realized vol as of a historical timestamp.

    Uses the `lookback` candles closing at or before ts_ms (default 168 x 1h = 7d).
    This is the per-snapshot (ref_spot, ref_vol) pair from the data model.
    """
    start = ts_ms - (lookback + 1) * _INTERVAL_MS[interval]
    kl = [k for k in get_klines(symbol, interval, start_ms=start, end_ms=ts_ms, limit=KLINES_MAX_LIMIT)
          if k["close_time"] <= ts_ms]
    closes = [k["close"] for k in kl[-(lookback + 1):]]
    return {
        "symbol": symbol,
        "ts": ts_ms,
        "spot": closes[-1],
        "vol": realized_vol(closes, interval),
        "candles_used": len(closes),
    }


if __name__ == "__main__":
    # Smoke test against the live API.
    logging.basicConfig(level=logging.INFO)
    spot = get_spot()
    print("spot:", spot)
    now_ms = spot["ts"]
    week_ms = 7 * 86_400_000
    kl = list(iter_klines("BTCUSDT", "1h", now_ms - 2 * week_ms, now_ms))
    print(f"klines 2w/1h: {len(kl)} candles | first close: {kl[0]['close']} | last close: {kl[-1]['close']}")
    vol = realized_vol([k["close"] for k in kl], "1h")
    print(f"realized vol (2w, annualized): {vol:.2%}")
    hist = realized_vol_at(now_ms - week_ms)
    print("as-of 1w ago:", {k: round(v, 4) if isinstance(v, float) else v for k, v in hist.items() if k != 'symbol'})
