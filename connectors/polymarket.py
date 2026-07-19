"""Read-only Polymarket connector (Gamma + CLOB public APIs).

Returns normalized dicts only — nothing outside /connectors knows API shapes.
Verified behavior, field meanings, and caveats: docs/API-VERIFICATION.md.
No keys, no wallet: public read endpoints exclusively.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, timedelta
from typing import Any, Iterator

import requests

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

TAG_CRYPTO = 21
TAG_BITCOIN = 235

PAGE_LIMIT = 100  # Gamma hard cap per page
# Plain offset paging stops returning data at ~2,100 rows; if one date window
# approaches this, we split the window instead of trusting deeper offsets.
OFFSET_SAFE_MAX = 1500

_session = requests.Session()


def _get(url: str, params: dict[str, Any] | None = None, retries: int = 5) -> Any:
    """GET with retry + exponential backoff (handles rate limits / 5xx)."""
    backoff = 1.0
    for attempt in range(retries):
        try:
            resp = _session.get(url, params=params, timeout=30)
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()  # error del cliente: reintentar no ayuda
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500 \
                    and exc.response.status_code != 429:
                raise
            if attempt == retries - 1:
                raise
            log.warning("GET %s failed (%s), retry in %.0fs", url, exc, backoff)
            time.sleep(backoff)
            backoff *= 2
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries - 1:
                raise
            log.warning("GET %s failed (%s), retry in %.0fs", url, exc, backoff)
            time.sleep(backoff)
            backoff *= 2


def _json_field(raw: str | None) -> list:
    """Gamma encodes list fields as JSON strings ('[\"Yes\", \"No\"]')."""
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return []


def _normalize_market(m: dict) -> dict:
    """Gamma market -> normalized dict (see docs/API-VERIFICATION.md §1)."""
    prices = _json_field(m.get("outcomePrices"))
    tokens = _json_field(m.get("clobTokenIds"))
    # outcomePrices ["1","0"] => first outcome (Yes) won. Anything else
    # (unresolved, 50/50 invalid resolution) => outcome None.
    outcome: int | None = None
    if prices == ["1", "0"]:
        outcome = 1
    elif prices == ["0", "1"]:
        outcome = 0
    return {
        "market_id": str(m.get("id")),
        "condition_id": m.get("conditionId"),
        "question": m.get("question"),
        "slug": m.get("slug"),
        "outcomes": _json_field(m.get("outcomes")),
        "token_yes": tokens[0] if len(tokens) > 0 else None,
        "token_no": tokens[1] if len(tokens) > 1 else None,
        "outcome": outcome,
        "created_at": m.get("createdAt"),
        "start_date": m.get("startDate"),
        "end_date": m.get("endDate"),
        "closed_time": m.get("closedTime"),
        "volume": m.get("volumeNum"),
        "liquidity": m.get("liquidityNum"),
        "closed": m.get("closed"),
    }


def _fetch_markets_page(params: dict[str, Any]) -> list[dict]:
    data = _get(f"{GAMMA_BASE}/markets", params)
    return data if isinstance(data, list) else []


def iter_resolved_markets(
    tag_id: int,
    end_date_min: date,
    end_date_max: date,
    window_days: int = 7,
    min_volume: float | None = None,
) -> Iterator[dict]:
    """Enumerate resolved (closed) markets for a tag, windowed by endDate.

    Windowing works around the ~2,100-row offset cap; if a single window still
    hits OFFSET_SAFE_MAX rows it is split in half recursively. Markets whose
    endDate sits exactly on a window boundary can appear twice — dedupe here.
    """
    seen: set[str] = set()

    def _window(lo: date, hi: date) -> Iterator[dict]:
        offset = 0
        while True:
            params: dict[str, Any] = {
                "closed": "true",
                "tag_id": tag_id,
                "limit": PAGE_LIMIT,
                "offset": offset,
                "end_date_min": lo.isoformat(),
                "end_date_max": hi.isoformat(),
                "order": "endDate",
                "ascending": "true",
            }
            if min_volume is not None:
                params["volume_num_min"] = min_volume
            page = _fetch_markets_page(params)
            for m in page:
                norm = _normalize_market(m)
                if norm["market_id"] not in seen:
                    seen.add(norm["market_id"])
                    yield norm
            if len(page) < PAGE_LIMIT:
                return
            offset += PAGE_LIMIT
            if offset >= OFFSET_SAFE_MAX:
                if (hi - lo).days <= 1:
                    log.warning(
                        "window %s..%s exceeds %d rows at 1 day; results may be incomplete",
                        lo, hi, OFFSET_SAFE_MAX,
                    )
                    return
                mid = lo + (hi - lo) / 2
                yield from _window(lo, mid)
                yield from _window(mid, hi)
                return

    lo = end_date_min
    while lo < end_date_max:
        hi = min(lo + timedelta(days=window_days), end_date_max)
        yield from _window(lo, hi)
        lo = hi


def get_market_by_slug(slug: str) -> dict | None:
    page = _fetch_markets_page({"slug": slug})
    return _normalize_market(page[0]) if page else None


def get_price_history(token_id: str, fidelity_minutes: int = 10) -> list[dict]:
    """Full-life price series for one CLOB token at ~10-minute resolution.

    fidelity below 10 is silently floored by the API when interval=max —
    use get_price_history_window for 1-minute data.
    Returns [{"ts": epoch_ms, "price": float}, ...] sorted by ts.
    """
    data = _get(
        f"{CLOB_BASE}/prices-history",
        {"market": token_id, "interval": "max", "fidelity": fidelity_minutes},
    )
    return [{"ts": p["t"] * 1000, "price": p["p"]} for p in data.get("history", [])]


def get_price_history_window(
    token_id: str, start_ts: int, end_ts: int, fidelity_minutes: int = 1
) -> list[dict]:
    """Price series in an explicit window; supports true 1-minute fidelity.

    start_ts / end_ts are epoch SECONDS (API convention); output ts is epoch ms.
    """
    data = _get(
        f"{CLOB_BASE}/prices-history",
        {
            "market": token_id,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity_minutes,
        },
    )
    return [{"ts": p["t"] * 1000, "price": p["p"]} for p in data.get("history", [])]


def get_order_book(token_id: str) -> dict:
    """Live order book snapshot (F2 collector). Live-only — never historical."""
    d = _get(f"{CLOB_BASE}/book", {"token_id": token_id})
    return {
        "token_id": d.get("asset_id"),
        "ts": int(d["timestamp"]) if d.get("timestamp") else None,
        "bids": [{"price": float(x["price"]), "size": float(x["size"])} for x in d.get("bids", [])],
        "asks": [{"price": float(x["price"]), "size": float(x["size"])} for x in d.get("asks", [])],
        "tick_size": d.get("tick_size"),
        "min_order_size": d.get("min_order_size"),
    }


if __name__ == "__main__":
    # Smoke test against the live API: one week of resolved BTC markets,
    # then price history for the first market with usable volume.
    logging.basicConfig(level=logging.INFO)
    end = date(2026, 7, 13)
    start = end - timedelta(days=7)
    markets = list(iter_resolved_markets(TAG_BITCOIN, start, end, min_volume=1000))
    resolved = [m for m in markets if m["outcome"] is not None]
    print(f"markets fetched: {len(markets)} | with resolution: {len(resolved)}")
    sample = next(m for m in resolved if m["volume"] and m["volume"] > 10000)
    print("sample:", sample["question"], "| outcome:", sample["outcome"])
    hist = get_price_history(sample["token_yes"])
    print(f"history points: {len(hist)} | first: {hist[0]} | last: {hist[-1]}")
