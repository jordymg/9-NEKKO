"""F1 — Backtest histórico: sesgo de Polymarket vs. modelo de referencia.

Pipeline:
  1. Enumera mercados cripto resueltos (Gamma, ventanas de fecha).
  2. Dos familias entran al análisis:
     - binarias europeas "¿ASSET above/below $K on FECHA?" → valuadas con lognormal
     - "Up or Down" de 5-15 min → GRUPO DE CONTROL (PRD §6): solo calibración
       implícita vs. resultado, sin modelo. Barrera ('reach/dip') se cuenta y se
       saltea (ADR-0006).
  3. Persistencia INCREMENTAL en SQLite (mercado a mercado, append-only): un corte
     a mitad de corrida no pierde lo procesado.
  4. Tabla de sesgos segmentada por duración del mercado y banda de volumen.
     Con --gross los números son BRUTOS (sin fee ni spread) y se rotulan así.

Uso:
  python -m backtest.historical --start 2026-06-01 --end 2026-07-13 \
      [--max-markets 350] [--control-max 120] [--gross]
"""
from __future__ import annotations

import argparse
import bisect
import logging
import re
import time
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import yaml
from pathlib import Path

from connectors import binance, polymarket
from models.probability_model import prob_above, tte_years_from_hours
from storage import sqlite as store

log = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"

SAMPLE_TTES_H = [72.0, 48.0, 24.0, 12.0, 6.0, 2.0]
MATCH_TOL_MS = 30 * 60 * 1000
CONTROL_TARGET_BEFORE_END_MS = 3 * 60 * 1000   # muestreo del control: ~3 min antes del cierre
CONTROL_TOL_MS = 2 * 60 * 1000
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
RE_UPDOWN = re.compile(
    r"(?P<asset>bitcoin|btc|ethereum|eth|solana|sol|xrp|dogecoin|doge)\s+up or down",
    re.IGNORECASE,
)


def parse_market(question: str) -> dict | None:
    """Clasifica una pregunta. kind: euro_above/euro_below/control_updown/None."""
    q = question or ""
    m = RE_EURO.search(q)
    if m:
        strike = float(m.group("strike").replace(",", ""))
        if m.group("kilo"):
            strike *= 1000
        return {
            "asset": ASSET_SYMBOL[m.group("asset").lower()],
            "kind": f"euro_{m.group('direction').lower()}",
            "strike": strike,
        }
    m = RE_UPDOWN.search(q)
    if m:
        return {"asset": ASSET_SYMBOL[m.group("asset").lower()],
                "kind": "control_updown", "strike": None}
    return None


def _iso_to_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _duration_hours(m: dict) -> float | None:
    try:
        start = m.get("created_at") or m.get("start_date")
        return round((_iso_to_ms(m["end_date"]) - _iso_to_ms(start)) / 3_600_000, 2)
    except (KeyError, TypeError, ValueError):
        return None


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


def trade_ev(model_p: float, mid: float, half_spread: float, fee_rate: float) -> tuple[str, float]:
    """(lado, EV por share) del mejor lado según el modelo. Con hs=fee=0 es BRUTO."""
    def _ev(p_win: float, price: float) -> float:
        price = min(max(price, 0.0), 1.0)
        return p_win - price - fee_rate * price * (1.0 - price)

    ev_yes = _ev(model_p, mid + half_spread)
    ev_no = _ev(1.0 - model_p, (1.0 - mid) + half_spread)
    return ("yes", ev_yes) if ev_yes >= ev_no else ("no", ev_no)


def realized_pnl(side: str, outcome: int, mid: float, half_spread: float, fee_rate: float) -> float:
    price = (mid if side == "yes" else 1.0 - mid) + half_spread
    price = min(max(price, 0.0), 1.0)
    win = outcome if side == "yes" else 1 - outcome
    return win - price - fee_rate * price * (1.0 - price)


def _sample_euro(m: dict, run_id: str, caches: dict[str, KlineCache]) -> list[dict]:
    end_ms = _iso_to_ms(m["end_date"])
    # interval=max devuelve vacío en mercados resueltos viejos (~>1 mes): siempre
    # ventana explícita creación→cierre. La respuesta se trunca en ~1000 puntos,
    # así que la fidelity se adapta a la duración para quedar por debajo.
    start_iso = m.get("created_at") or m.get("start_date")
    start_ms = _iso_to_ms(start_iso) if start_iso else end_ms - int(80 * 3_600_000)
    dur_min = max(1.0, (end_ms - start_ms) / 60_000)
    fidelity = max(10, int(dur_min / 700) + 1)
    hist = polymarket.get_price_history_window(
        m["token_yes"], start_ms // 1000, end_ms // 1000, fidelity_minutes=fidelity
    )
    if len(hist) >= 1000:
        log.warning("historial truncado en 1000 puntos: %s", m["slug"])
    if not hist:
        return []
    times = [p["ts"] for p in hist]
    rows = []
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
        cache = caches[m["asset"]]
        try:
            spot, vol = cache.spot_at(ts), cache.vol_at(ts)
        except ValueError:
            continue
        tte_hours = (end_ms - ts) / 3_600_000
        p_above = prob_above(spot, m["strike"], vol, tte_years_from_hours(tte_hours))
        model_p = p_above if m["kind"] == "euro_above" else 1.0 - p_above
        rows.append({
            "run_id": run_id, "market_id": m["market_id"], "question": m["question"],
            "asset": m["asset"], "kind": m["kind"], "strike": m["strike"],
            "ts": ts, "tte_hours": round(tte_hours, 2),
            "duration_hours": _duration_hours(m),
            "implied_mid": hist[k]["price"], "ref_spot": spot, "ref_vol": vol,
            "model_prob": model_p, "market_volume": m["volume"], "outcome": m["outcome"],
        })
    return rows


def _sample_control(m: dict, run_id: str) -> list[dict]:
    """Un snapshot por mercado de control, ~3 min antes del cierre, granularidad 1 min."""
    end_ms = _iso_to_ms(m["end_date"])
    hist = polymarket.get_price_history_window(
        m["token_yes"], (end_ms - 8 * 60_000) // 1000, end_ms // 1000, fidelity_minutes=1
    )
    if not hist:
        return []
    target = end_ms - CONTROL_TARGET_BEFORE_END_MS
    p = min(hist, key=lambda x: abs(x["ts"] - target))
    if abs(p["ts"] - target) > CONTROL_TOL_MS:
        return []
    return [{
        "run_id": run_id, "market_id": m["market_id"], "question": m["question"],
        "asset": m["asset"], "kind": "control_updown", "strike": None,
        "ts": p["ts"], "tte_hours": round((end_ms - p["ts"]) / 3_600_000, 4),
        "duration_hours": _duration_hours(m),
        "implied_mid": p["price"], "ref_spot": None, "ref_vol": None,
        "model_prob": None, "market_volume": m["volume"], "outcome": m["outcome"],
    }]


def _enumerate_window(start, end, settings: dict, stats: dict,
                      euro_cap: int, control_cap: int) -> tuple[list[dict], list[dict]]:
    """Enumera una ventana con cupos; corta apenas ambos cupos se llenan."""
    tag = settings["markets"]["tag_crypto"]
    euro: list[dict] = []
    control: list[dict] = []
    for m in polymarket.iter_resolved_markets(tag, start, end, min_volume=1000):
        stats["markets_seen"] += 1
        spec = parse_market(m["question"])
        if spec is None:
            if re.search(r"\b(reach|dip|hit)\b", m["question"] or "", re.I):
                stats["skipped_barrier"] += 1
            else:
                stats["skipped_other"] += 1
            continue
        if m["outcome"] is None or not m["token_yes"] or not m["end_date"]:
            continue
        mm = {**m, **spec}
        if spec["kind"] == "control_updown":
            if len(control) < control_cap:
                control.append(mm)
        elif len(euro) < euro_cap:
            euro.append(mm)
        if len(euro) >= euro_cap and len(control) >= control_cap:
            break
    return euro, control


def _month_weeks(month: str) -> list[tuple[date, date]]:
    """'2026-03' → sub-ventanas semanales que cubren el mes."""
    y, mo = (int(x) for x in month.split("-"))
    first = date(y, mo, 1)
    nxt = date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)
    weeks, lo = [], first
    while lo < nxt:
        hi = min(lo + timedelta(days=7), nxt)
        weeks.append((lo, hi))
        lo = hi
    return weeks


def _process(euro: list[dict], control: list[dict], conn,
             stats: dict) -> list[dict]:
    stats["euro"], stats["control"] = len(euro), len(control)

    caches: dict[str, KlineCache] = {}
    if euro:
        all_end = [_iso_to_ms(m["end_date"]) for m in euro]
        lo = min(all_end) - int(max(SAMPLE_TTES_H) * 3_600_000)
        hi = max(all_end)
        for sym in {m["asset"] for m in euro}:
            log.info("cargando klines %s", sym)
            caches[sym] = KlineCache(sym, lo, hi)

    run_id = uuid.uuid4().hex[:12]
    all_rows: list[dict] = []
    todo = [("euro", m) for m in euro] + [("control", m) for m in control]
    for i, (fam, m) in enumerate(todo):
        try:
            rows = _sample_euro(m, run_id, caches) if fam == "euro" else _sample_control(m, run_id)
        except Exception as exc:
            log.warning("sin datos %s (%s)", m["slug"], exc)
            stats["no_data"] += 1
            continue
        if not rows:
            stats["no_data"] += 1
            continue
        # persistencia incremental: un corte no pierde lo ya procesado
        store.insert_snapshots(conn, rows)
        store.upsert_resolution(conn, m["market_id"], m["outcome"], m.get("closed_time"))
        all_rows.extend(rows)
        stats["sampled"] += len(rows)
        if (i + 1) % 50 == 0:
            log.info("procesados %d/%d mercados (%d snapshots)", i + 1, len(todo), len(all_rows))
    return all_rows


def collect(start: date, end: date, settings: dict, conn,
            max_markets: int, control_max: int) -> tuple[list[dict], dict]:
    """Modo simple: una sola ventana start..end con cupos globales."""
    stats = _new_stats()
    euro, control = _enumerate_window(start, end, settings, stats, max_markets, control_max)
    return _process(euro, control, conn, stats), stats


def collect_stratified(months: list[str], settings: dict, conn,
                       euro_per_month: int, control_per_month: int) -> tuple[list[dict], dict]:
    """Muestreo DECORRELACIONADO: cupos por semana dentro de cada mes, para que
    ninguna semana (ni ningún régimen puntual de mercado) domine la muestra.
    Motivación: la corrida 2026-07-19 quedó agrupada en una sola semana de junio
    y sus sesgos aparentes quedaron confundidos con la deriva del régimen.
    """
    stats = _new_stats()
    euro: list[dict] = []
    control: list[dict] = []
    for month in months:
        weeks = _month_weeks(month)
        e_wc = -(-euro_per_month // len(weeks))      # ceil
        c_wc = -(-control_per_month // len(weeks))
        got_e = got_c = 0
        for lo, hi in weeks:
            e, c = _enumerate_window(
                lo, hi, settings, stats,
                min(e_wc, euro_per_month - got_e),
                min(c_wc, control_per_month - got_c),
            )
            euro.extend(e); control.extend(c)
            got_e += len(e); got_c += len(c)
        log.info("mes %s: %d euro, %d control", month, got_e, got_c)
    return _process(euro, control, conn, stats), stats


def _new_stats() -> dict:
    return {"markets_seen": 0, "euro": 0, "control": 0, "skipped_barrier": 0,
            "skipped_other": 0, "no_data": 0, "sampled": 0}


def bias_tables(df: pd.DataFrame, settings: dict, gross: bool) -> dict[str, pd.DataFrame]:
    # ADVERTENCIA DE INTERPRETACIÓN (corrida 2026-07-19): la muestra estaba
    # temporalmente agrupada (una sola semana de junio) → los resultados de los
    # mercados están correlacionados vía régimen de mercado. El +22pt de sesgo en
    # europeas y el +9pt del control quedaron confundidos con la deriva del régimen
    # (modelo ≈ implícita apoya esa lectura). Los mercados de control son
    # independientes entre sí pero NO del período muestreado. El fix de
    # decorrelación es muestrear ≥4 meses calendario distintos, estratificado
    # para que ninguna semana domine.
    fee = 0.0 if gross else settings["fees"]["taker_fee_rate_crypto"]
    hs = 0.0 if gross else settings["spread"]["assumed_spread"] / 2.0
    lo, hi = settings["markets"]["price_band_analysis"]

    df = df.copy()
    df["dur_bucket"] = pd.cut(
        df["duration_hours"].fillna(-1), [-2, 0, 1, 30, 100, 1e9],
        labels=["?", "<=1h", "~1d", "2-4d", ">4d"],
    )
    df["liq_band"] = pd.cut(
        df["market_volume"].fillna(0), [0, 10_000, 100_000, float("inf")],
        labels=["<10k", "10k-100k", ">100k"],
    )

    e = df[df["kind"].str.startswith("euro") & df["implied_mid"].between(lo, hi)].copy()
    out: dict[str, pd.DataFrame] = {}
    if len(e):
        sides = [trade_ev(r.model_prob, r.implied_mid, hs, fee) for r in e.itertuples()]
        e["side"] = [s for s, _ in sides]
        e["ev"] = [v for _, v in sides]
        e["pnl"] = [realized_pnl(r.side, r.outcome, r.implied_mid, hs, fee) for r in e.itertuples()]
        e["traded"] = e["ev"] > 0

        def _agg(g: pd.DataFrame) -> pd.Series:
            t = g[g["traded"]]
            return pd.Series({
                "n": len(g), "implied": g["implied_mid"].mean(),
                "model": g["model_prob"].mean(), "freq_real": g["outcome"].mean(),
                "sesgo_impl": g["implied_mid"].mean() - g["outcome"].mean(),
                "n_señal": len(t), "pnl_medio": t["pnl"].mean() if len(t) else float("nan"),
            })

        for name, keys in [("duracion", ["dur_bucket"]), ("liquidez", ["liq_band"]),
                           ("duracion_x_liquidez", ["dur_bucket", "liq_band"])]:
            out[name] = (e.groupby(keys, observed=True)
                         .apply(_agg, include_groups=False).round(4))

    c = df[(df["kind"] == "control_updown") & df["implied_mid"].between(lo, hi)].copy()
    if len(c):
        ctrl = (c.groupby("liq_band", observed=True)
                .agg(n=("outcome", "size"), implied=("implied_mid", "mean"),
                     freq_real=("outcome", "mean")).round(4))
        ctrl["sesgo_impl"] = (ctrl["implied"] - ctrl["freq_real"]).round(4)
        out["control_updown"] = ctrl
        # calibración del control POR MES: si el sesgo pooled no reaparece mes a
        # mes, era artefacto del período y no una propiedad del mercado
        c["mes"] = pd.to_datetime(c["ts"], unit="ms").dt.strftime("%Y-%m")
        pm = (c.groupby("mes")
              .agg(n=("outcome", "size"), implied=("implied_mid", "mean"),
                   freq_real=("outcome", "mean")).round(4))
        pm["sesgo_impl"] = (pm["implied"] - pm["freq_real"]).round(4)
        pooled = pd.DataFrame({
            "n": [len(c)], "implied": [c["implied_mid"].mean()],
            "freq_real": [c["outcome"].mean()],
        }, index=["POOLED"]).round(4)
        pooled["sesgo_impl"] = (pooled["implied"] - pooled["freq_real"]).round(4)
        out["control_updown_por_mes"] = pd.concat([pm, pooled])
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=date.fromisoformat)
    ap.add_argument("--end", type=date.fromisoformat)
    ap.add_argument("--months", help="modo estratificado: ej. 2026-03,2026-04,2026-05,2026-06")
    ap.add_argument("--euro-per-month", type=int, default=100)
    ap.add_argument("--control-per-month", type=int, default=80)
    ap.add_argument("--max-markets", type=int, default=350)
    ap.add_argument("--control-max", type=int, default=120)
    ap.add_argument("--gross", action="store_true",
                    help="números BRUTOS sin fee/spread (solo exploración)")
    ap.add_argument("--db", default=store.DEFAULT_DB)
    args = ap.parse_args()
    if not args.months and not (args.start and args.end):
        ap.error("hace falta --months o --start/--end")

    settings = load_settings()
    conn = store.connect(args.db)
    t0 = time.time()
    if args.months:
        rows, stats = collect_stratified(args.months.split(","), settings, conn,
                                         args.euro_per_month, args.control_per_month)
    else:
        rows, stats = collect(args.start, args.end, settings, conn,
                              args.max_markets, args.control_max)
    log.info("stats: %s | %.0fs", stats, time.time() - t0)
    if not rows:
        print("Sin snapshots — nada que analizar.")
        return
    log.info("%d snapshots persistidos en %s (run %s)", len(rows), args.db, rows[0]["run_id"])

    label = ("GROSS / EXPLORATORIA — SIN fee ni spread; NO usar para decidir tesis"
             if args.gross else "NETA de costos (config/settings.yaml)")
    tables = bias_tables(pd.DataFrame(rows), settings, args.gross)
    pd.set_option("display.width", 160)
    print(f"\n===== TABLA DE SESGOS [{label}] — banda de precio 0.05-0.95 =====")
    for name, t in tables.items():
        print(f"\n--- {name} ---")
        print(t.to_string())


if __name__ == "__main__":
    main()
