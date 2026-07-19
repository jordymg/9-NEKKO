"""F1 — Backtest histórico: sesgo de Polymarket vs. modelo de referencia.

Pipeline:
  1. Enumera mercados cripto resueltos (Gamma, ventanas de fecha).
  2. Filtra los parseables tipo "¿ASSET above/below $K on FECHA?" (binaria europea —
     única familia que el modelo lognormal baseline sabe valuar; 'reach'/'dip' son
     barrera y quedan para una iteración posterior; 'Up or Down' es grupo de control).
  3. Por mercado: historial de precios (CLOB) muestreado a varios TTE + spot/vol de
     Binance al mismo timestamp (klines 1h cacheadas) → prob del modelo.
  4. Persiste snapshots append-only en SQLite y produce la tabla de sesgos,
     con edge NETO de costos (config/settings.yaml). Nunca reporta bruto.

Uso:  python -m backtest.historical --start 2026-06-01 --end 2026-07-13 [--max-markets N]
"""
from __future__ import annotations

import argparse
import bisect
import logging
import math
import re
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from connectors import binance, polymarket
from models.probability_model import prob_above, tte_years_from_hours
from storage import sqlite as store

log = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

# TTE (horas antes del cierre) en los que se muestrea cada mercado
SAMPLE_TTES_H = [72.0, 48.0, 24.0, 12.0, 6.0, 2.0]
# tolerancia para matchear un punto del historial al ts objetivo
MATCH_TOL_MS = 30 * 60 * 1000

VOL_LOOKBACK_CANDLES = 168  # 7d de velas 1h

ASSET_SYMBOL = {
    "bitcoin": "BTCUSDT", "btc": "BTCUSDT",
    "ethereum": "ETHUSDT", "eth": "ETHUSDT",
    "solana": "SOLUSDT", "sol": "SOLUSDT",
    "xrp": "XRPUSDT",
    "dogecoin": "DOGEUSDT", "doge": "DOGEUSDT",
}

RE_EURO = re.compile(
    r"will (?:the price of )?(?P<asset>bitcoin|btc|ethereum|eth|solana|sol|xrp|dogecoin|doge)"
    r" be (?P<direction>above|below) \$?(?P<strike>[\d,]+(?:\.\d+)?)(?P<kilo>k)? on ",
    re.IGNORECASE,
)


def parse_market(question: str) -> dict | None:
    """Clasifica una pregunta; None si no es binaria europea parseable."""
    m = RE_EURO.search(question or "")
    if not m:
        return None
    strike = float(m.group("strike").replace(",", ""))
    if m.group("kilo"):
        strike *= 1000
    return {
        "asset": ASSET_SYMBOL[m.group("asset").lower()],
        "direction": m.group("direction").lower(),
        "strike": strike,
    }


def _iso_to_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


class KlineCache:
    """Velas 1h de un símbolo en memoria: spot y vol realizada as-of cualquier ts."""

    def __init__(self, symbol: str, start_ms: int, end_ms: int):
        lookback_ms = (VOL_LOOKBACK_CANDLES + 2) * 3_600_000
        self.symbol = symbol
        kl = list(binance.iter_klines(symbol, "1h", start_ms - lookback_ms, end_ms))
        if not kl:
            raise RuntimeError(f"sin klines para {symbol}")
        self.close_times = [k["close_time"] for k in kl]
        self.closes = [k["close"] for k in kl]

    def _idx_at(self, ts_ms: int) -> int:
        i = bisect.bisect_right(self.close_times, ts_ms) - 1
        if i < 0:
            raise ValueError(f"{self.symbol}: ts {ts_ms} anterior a la cache")
        return i

    def spot_at(self, ts_ms: int) -> float:
        return self.closes[self._idx_at(ts_ms)]

    def vol_at(self, ts_ms: int) -> float:
        i = self._idx_at(ts_ms)
        closes = self.closes[max(0, i - VOL_LOOKBACK_CANDLES): i + 1]
        return binance.realized_vol(closes, "1h")


def load_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def net_ev(model_p: float, mid: float, half_spread: float, fee_rate: float) -> tuple[str, float]:
    """(lado, EV neto por share) del mejor lado según el modelo, tras spread + fee.

    Compra YES a mid+hs: EV = model_p - precio - fee(precio)
    Compra NO  a (1-mid)+hs: EV = (1-model_p) - precio - fee(precio)
    fee(p) = fee_rate * p * (1-p)  (taker; docs.polymarket.com/trading/fees)
    """
    def _ev(p_win: float, price: float) -> float:
        price = min(max(price, 0.0), 1.0)
        return p_win - price - fee_rate * price * (1.0 - price)

    ev_yes = _ev(model_p, mid + half_spread)
    ev_no = _ev(1.0 - model_p, (1.0 - mid) + half_spread)
    return ("yes", ev_yes) if ev_yes >= ev_no else ("no", ev_no)


def realized_pnl(side: str, outcome: int, mid: float, half_spread: float, fee_rate: float) -> float:
    """PnL realizado por share si se hubiera tomado `side` a precios con costos."""
    price = (mid if side == "yes" else 1.0 - mid) + half_spread
    price = min(max(price, 0.0), 1.0)
    win = outcome if side == "yes" else 1 - outcome
    return win - price - fee_rate * price * (1.0 - price)


def collect_snapshots(
    start: date, end: date, settings: dict, max_markets: int | None = None
) -> tuple[list[dict], dict]:
    """Recorre mercados resueltos y produce filas de snapshot. Devuelve (filas, stats)."""
    tag = settings["markets"]["tag_crypto"]
    stats = {"markets_seen": 0, "parseable": 0, "no_resolution": 0,
             "no_history": 0, "sampled": 0, "skipped_kinds": {}}
    parsed_markets: list[dict] = []

    for m in polymarket.iter_resolved_markets(tag, start, end, min_volume=1000):
        stats["markets_seen"] += 1
        q = m["question"] or ""
        spec = parse_market(q)
        if spec is None:
            key = ("updown" if "up or down" in q.lower()
                   else "barrier" if re.search(r"\b(reach|dip|hit)\b", q, re.I)
                   else "other")
            stats["skipped_kinds"][key] = stats["skipped_kinds"].get(key, 0) + 1
            continue
        if m["outcome"] is None or not m["token_yes"] or not m["end_date"]:
            stats["no_resolution"] += 1
            continue
        stats["parseable"] += 1
        parsed_markets.append({**m, **spec})
        if max_markets and len(parsed_markets) >= max_markets:
            break

    if not parsed_markets:
        return [], stats

    # cache de klines por símbolo cubriendo todo el rango muestreado
    caches: dict[str, KlineCache] = {}
    all_end_ms = [_iso_to_ms(m["end_date"]) for m in parsed_markets]
    lo = min(all_end_ms) - int(max(SAMPLE_TTES_H) * 3_600_000)
    hi = max(all_end_ms)
    for sym in {m["asset"] for m in parsed_markets}:
        log.info("cargando klines %s", sym)
        caches[sym] = KlineCache(sym, lo, hi)

    run_id = uuid.uuid4().hex[:12]
    rows: list[dict] = []
    for i, m in enumerate(parsed_markets):
        end_ms = _iso_to_ms(m["end_date"])
        try:
            hist = polymarket.get_price_history(m["token_yes"])
        except Exception as exc:
            log.warning("sin historial %s (%s)", m["slug"], exc)
            stats["no_history"] += 1
            continue
        if not hist:
            stats["no_history"] += 1
            continue
        times = [p["ts"] for p in hist]
        for tte_h in SAMPLE_TTES_H:
            target = end_ms - int(tte_h * 3_600_000)
            j = bisect.bisect_left(times, target)
            cand = [k for k in (j - 1, j) if 0 <= k < len(times)]
            if not cand:
                continue
            k = min(cand, key=lambda x: abs(times[x] - target))
            if abs(times[k] - target) > MATCH_TOL_MS:
                continue
            ts = times[k]
            implied_yes = hist[k]["price"]
            cache = caches[m["asset"]]
            try:
                spot, vol = cache.spot_at(ts), cache.vol_at(ts)
            except ValueError:
                continue
            tte_hours = (end_ms - ts) / 3_600_000
            p_above = prob_above(spot, m["strike"], vol,
                                 tte_years_from_hours(tte_hours))
            model_p = p_above if m["direction"] == "above" else 1.0 - p_above
            rows.append({
                "run_id": run_id,
                "market_id": m["market_id"],
                "question": m["question"],
                "asset": m["asset"],
                "kind": f"euro_{m['direction']}",
                "strike": m["strike"],
                "ts": ts,
                "tte_hours": round(tte_hours, 2),
                "implied_mid": implied_yes,
                "ref_spot": spot,
                "ref_vol": vol,
                "model_prob": model_p,
                "market_volume": m["volume"],
                "outcome": m["outcome"],
            })
            stats["sampled"] += 1
        if (i + 1) % 100 == 0:
            log.info("procesados %d/%d mercados", i + 1, len(parsed_markets))
    return rows, stats


def bias_table(df: pd.DataFrame, settings: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tabla de sesgos por segmento: implícita vs. modelo vs. frecuencia real, edge neto."""
    fee = settings["fees"]["taker_fee_rate_crypto"]
    hs = settings["spread"]["assumed_spread"] / 2.0
    lo, hi = settings["markets"]["price_band_analysis"]

    d = df[(df["implied_mid"] >= lo) & (df["implied_mid"] <= hi)].copy()
    d["tte_bucket"] = pd.cut(
        d["tte_hours"], [0, 4, 9, 18, 36, 60, 1e9],
        labels=["2h", "6h", "12h", "24h", "48h", "72h"],
    )
    d["liq_band"] = pd.cut(
        d["market_volume"].fillna(0), [0, 10_000, 100_000, float("inf")],
        labels=["<10k", "10k-100k", ">100k"],
    )
    sides_evs = [net_ev(r.model_prob, r.implied_mid, hs, fee) for r in d.itertuples()]
    d["side"] = [s for s, _ in sides_evs]
    d["ev_net_expected"] = [e for _, e in sides_evs]
    d["pnl_net"] = [
        realized_pnl(r.side, r.outcome, r.implied_mid, hs, fee) for r in d.itertuples()
    ]
    d["traded"] = d["ev_net_expected"] > 0

    def _agg(g: pd.DataFrame) -> pd.Series:
        t = g[g["traded"]]
        return pd.Series({
            "n": len(g),
            "implied": g["implied_mid"].mean(),
            "model": g["model_prob"].mean(),
            "freq_real": g["outcome"].mean(),
            "sesgo_implied": g["implied_mid"].mean() - g["outcome"].mean(),
            "n_señales": len(t),
            "pnl_neto_medio": t["pnl_net"].mean() if len(t) else float("nan"),
        })

    out = (
        d.groupby(["asset", "tte_bucket"], observed=True)
        .apply(_agg, include_groups=False)
        .round(4)
    )
    return out, d


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=date.fromisoformat)
    ap.add_argument("--end", required=True, type=date.fromisoformat)
    ap.add_argument("--max-markets", type=int, default=None)
    ap.add_argument("--db", default=store.DEFAULT_DB)
    args = ap.parse_args()

    settings = load_settings()
    t0 = time.time()
    rows, stats = collect_snapshots(args.start, args.end, settings, args.max_markets)
    log.info("stats: %s | %.0fs", stats, time.time() - t0)
    if not rows:
        print("Sin snapshots — nada que analizar.")
        return

    conn = store.connect(args.db)
    store.insert_snapshots(conn, rows)
    for r in {row["market_id"]: row for row in rows}.values():
        store.upsert_resolution(conn, r["market_id"], r["outcome"], None)
    log.info("guardados %d snapshots en %s (run %s)", len(rows), args.db, rows[0]["run_id"])

    df = pd.DataFrame(rows)
    table, detail = bias_table(df, settings)
    pd.set_option("display.width", 160)
    print("\n=== Tabla de sesgos (banda de precio 0.05-0.95, edge NETO de costos) ===")
    print(table.to_string())
    print("\n=== Por banda de liquidez ===")
    liq = (
        detail.groupby("liq_band", observed=True)
        .agg(n=("outcome", "size"), implied=("implied_mid", "mean"),
             freq_real=("outcome", "mean"))
        .round(4)
    )
    liq["sesgo_implied"] = (liq["implied"] - liq["freq_real"]).round(4)
    print(liq.to_string())


if __name__ == "__main__":
    main()
