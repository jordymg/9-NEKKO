"""F2 — Colector en vivo (PRD F2): snapshots de libro + spot/vol de referencia.

- Grilla fija cada `grid_interval_s` sobre el universo de mercados trackeados.
- Snapshots EXTRA disparados por evento: si el spot de Binance se movió más de
  `event_move_pct`% desde el último snapshot de ese activo (trigger='event').
- Universo: binarias europeas cripto activas con volumen 24h suficiente,
  refrescado cada `universe_refresh_s`; al refrescar, backfillea resoluciones
  de mercados que cerraron.
- Robustez: retry+backoff vive en los conectores; acá, error de un mercado se
  saltea y se cuenta; ciclo entero fallido abre un gap en la tabla `gaps` con
  el motivo, y la recuperación lo cierra. Append-only salvo gaps.ts_end.

Uso:  python -m collector.live_collector [--db nekko.sqlite]
Parar: Ctrl+C (cierra el gap "shutdown" limpio... no abre gap: apagado
intencional queda como último snapshot sin más).
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from connectors import binance, polymarket
from models.probability_model import prob_above, tte_years_from_hours
from storage import sqlite as store

log = logging.getLogger("collector")

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

import re

RE_EURO = re.compile(
    r"will (?:the price of )?(?P<asset>bitcoin|btc|ethereum|eth|solana|sol|xrp|dogecoin|doge)"
    r" be (?P<direction>above|below) \$?(?P<strike>[\d,]+(?:\.\d+)?)(?P<kilo>k)? on ",
    re.IGNORECASE,
)
ASSET_SYMBOL = {
    "bitcoin": "BTCUSDT", "btc": "BTCUSDT", "ethereum": "ETHUSDT", "eth": "ETHUSDT",
    "solana": "SOLUSDT", "sol": "SOLUSDT", "xrp": "XRPUSDT",
    "dogecoin": "DOGEUSDT", "doge": "DOGEUSDT",
}


def _iso_to_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def load_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Collector:
    def __init__(self, conn, settings: dict):
        self.conn = conn
        self.cfg = settings["collector"]
        self.tag = settings["markets"]["tag_crypto"]
        self.universe: dict[str, dict] = {}      # market_id -> market info
        self.klines: dict[str, list[float]] = {} # symbol -> últimos closes 1h
        self.last_snap_spot: dict[str, float] = {}
        self.next_universe = 0.0
        self.next_klines = 0.0
        self.next_grid = 0.0
        self.open_gap_id: int | None = None
        self.consec_failures = 0

    # ---------- universo ----------
    def refresh_universe(self) -> None:
        cfg = self.cfg
        markets = []
        for offset in (0, 100, 200):  # hasta 300 candidatos por volumen desc
            page = polymarket._get(f"{polymarket.GAMMA_BASE}/markets", {
                "active": "true", "closed": "false", "tag_id": self.tag,
                "limit": 100, "offset": offset,
                "order": "volume24hr", "ascending": "false",
                "volume_num_min": cfg["min_volume_24h"],
            })
            markets.extend(page)
            if len(page) < 100:
                break
        new: dict[str, dict] = {}
        for m in markets:
            norm = polymarket._normalize_market(m)
            mm = RE_EURO.search(norm["question"] or "")
            if not mm or not norm["token_yes"] or not norm["end_date"]:
                continue
            strike = float(mm.group("strike").replace(",", ""))
            if mm.group("kilo"):
                strike *= 1000
            new[norm["market_id"]] = {
                **norm,
                "asset": ASSET_SYMBOL[mm.group("asset").lower()],
                "direction": mm.group("direction").lower(),
                "strike": strike,
                "end_ms": _iso_to_ms(norm["end_date"]),
                "volume24h": m.get("volume24hr"),
            }
            if len(new) >= cfg["max_markets"]:
                break
        # backfill de resoluciones: mercados que salieron del universo por cierre
        for mid, old in self.universe.items():
            if mid not in new:
                try:
                    fresh = polymarket.get_market_by_slug(old["slug"])
                    if fresh and fresh["closed"] and fresh["outcome"] is not None:
                        store.upsert_resolution(self.conn, mid, fresh["outcome"],
                                                fresh.get("closed_time"), source="collector")
                        log.info("resolucion backfilleada %s -> %s", old["slug"], fresh["outcome"])
                except Exception as exc:
                    log.warning("backfill fallo %s (%s)", mid, exc)
        self.universe = new
        log.info("universo: %d mercados trackeados", len(new))

    def refresh_klines(self) -> None:
        for sym in {m["asset"] for m in self.universe.values()}:
            kl = binance.get_klines(sym, "1h", limit=170)
            self.klines[sym] = [k["close"] for k in kl]

    # ---------- snapshots ----------
    def snapshot(self, market_ids: list[str], trigger: str) -> int:
        now_ms = int(time.time() * 1000)
        rows, spots = [], {}
        band = self.cfg["depth_band_pct"] / 100.0
        for sym in {self.universe[mid]["asset"] for mid in market_ids}:
            spots[sym] = binance.get_spot(sym)["price"]
        for mid in market_ids:
            m = self.universe[mid]
            try:
                book = polymarket.get_order_book(m["token_yes"])
            except Exception as exc:
                log.warning("libro fallo %s (%s)", m["slug"], exc)
                continue
            bids, asks = book["bids"], book["asks"]
            bid = max((x["price"] for x in bids), default=None)
            ask = min((x["price"] for x in asks), default=None)
            mid_p = (bid + ask) / 2 if bid is not None and ask is not None else None
            spread = (ask - bid) if bid is not None and ask is not None else None
            depth_bid = depth_ask = None
            if mid_p:
                depth_bid = sum(x["price"] * x["size"] for x in bids
                                if x["price"] >= mid_p * (1 - band))
                depth_ask = sum(x["price"] * x["size"] for x in asks
                                if x["price"] <= mid_p * (1 + band))
            sym = m["asset"]
            spot = spots.get(sym)
            vol = model_p = None
            closes = self.klines.get(sym)
            if spot and closes and len(closes) > 10:
                vol = binance.realized_vol(closes[-169:], "1h")
                tte_h = (m["end_ms"] - now_ms) / 3_600_000
                if tte_h > 0:
                    pa = prob_above(spot, m["strike"], vol, tte_years_from_hours(tte_h))
                    model_p = pa if m["direction"] == "above" else 1.0 - pa
            rows.append({
                "market_id": mid, "condition_id": m["condition_id"],
                "token_id": m["token_yes"], "ts": now_ms,
                "implied_bid": bid, "implied_ask": ask, "implied_mid": mid_p,
                "spread": spread, "depth_bid": depth_bid, "depth_ask": depth_ask,
                "volume_24h": m.get("volume24h"),
                "tte_hours": round((m["end_ms"] - now_ms) / 3_600_000, 3),
                "ref_spot": spot, "ref_vol": vol, "model_prob": model_p,
                "trigger": trigger,
            })
        if rows:
            store.insert_live_snapshots(self.conn, rows)
            for sym, p in spots.items():
                self.last_snap_spot[sym] = p
        log.info("snapshot %s: %d/%d mercados", trigger, len(rows), len(market_ids))
        return len(rows)

    # ---------- loop ----------
    def run(self) -> None:
        cfg = self.cfg
        while True:
            try:
                now = time.time()
                if now >= self.next_universe:
                    self.refresh_universe()
                    self.next_universe = now + cfg["universe_refresh_s"]
                if now >= self.next_klines:
                    self.refresh_klines()
                    self.next_klines = now + 3600
                if not self.universe:
                    time.sleep(cfg["spot_check_s"])
                    continue

                if now >= self.next_grid:
                    self.snapshot(list(self.universe), "grid")
                    self.next_grid = now + cfg["grid_interval_s"]
                else:
                    moved = []
                    for sym in {m["asset"] for m in self.universe.values()}:
                        last = self.last_snap_spot.get(sym)
                        if last is None:
                            continue
                        cur = binance.get_spot(sym)["price"]
                        if abs(cur / last - 1) * 100 >= cfg["event_move_pct"]:
                            moved.append(sym)
                    if moved:
                        ids = [mid for mid, m in self.universe.items() if m["asset"] in moved]
                        log.info("evento: %s se movio >%s%%", moved, cfg["event_move_pct"])
                        self.snapshot(ids, "event")

                # ciclo sano: cerrar gap si habia uno abierto
                if self.open_gap_id is not None:
                    store.close_gap(self.conn, self.open_gap_id, int(time.time() * 1000))
                    log.info("gap %d cerrado", self.open_gap_id)
                    self.open_gap_id = None
                self.consec_failures = 0
                time.sleep(cfg["spot_check_s"])

            except KeyboardInterrupt:
                log.info("apagado limpio")
                return
            except Exception as exc:
                self.consec_failures += 1
                if self.open_gap_id is None:
                    self.open_gap_id = store.open_gap(
                        self.conn, int(time.time() * 1000), f"{type(exc).__name__}: {exc}"[:200]
                    )
                    log.error("ciclo fallo, gap %d abierto: %s", self.open_gap_id, exc)
                time.sleep(min(60, 5 * self.consec_failures))


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--note", default="", help="etiqueta de la corrida; 'test-*' excluye sus eventos del análisis")
    args = ap.parse_args()
    conn = store.connect(args.db)
    settings = load_settings()
    run_id = store.insert_collector_run(conn, int(time.time() * 1000),
                                        settings["collector"], args.note)
    log.info("collector_run %d registrada (note=%r)", run_id, args.note)
    Collector(conn, settings).run()


if __name__ == "__main__":
    main()
