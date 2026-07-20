"""Panel de estado del colector F2 — solo lectura, solo stdlib.

Uso:  python -m analysis.status [--db nekko.sqlite]

Un vistazo y sabés si el colector está vivo: frescura del último snapshot con
veredicto OK/STALE/DOWN, mercados trackeados, snapshots de hoy (grilla vs.
evento), gaps abiertos con motivo y resoluciones backfilleadas.
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from datetime import datetime

STALE_S = 5 * 60
DOWN_S = 30 * 60
TRACKED_WINDOW_S = 15 * 60


def _fmt_ts(ms: int | None) -> str:
    if not ms:
        return "-"
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_age(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.1f}min"
    return f"{seconds / 3600:.1f}h"


def build_panel(db_path: str) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    q = conn.execute
    now_ms = int(time.time() * 1000)
    midnight_ms = int(datetime.now().replace(hour=0, minute=0, second=0,
                                             microsecond=0).timestamp() * 1000)

    last_ts = q("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    if last_ts is None:
        verdict, age_txt = "DOWN (sin snapshots)", "-"
    else:
        age = (now_ms - last_ts) / 1000
        age_txt = _fmt_age(age)
        verdict = ("OK" if age <= STALE_S
                   else f"STALE (>{STALE_S // 60}min)" if age <= DOWN_S
                   else f"DOWN (>{DOWN_S // 60}min)")

    tracked = q("SELECT COUNT(DISTINCT market_id) FROM snapshots WHERE ts >= ?",
                (now_ms - TRACKED_WINDOW_S * 1000,)).fetchone()[0]
    total = q("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    today = q("SELECT COUNT(*) FROM snapshots WHERE ts >= ?", (midnight_ms,)).fetchone()[0]
    today_evt = q("SELECT COUNT(*) FROM snapshots WHERE ts >= ? AND trigger = 'event'",
                  (midnight_ms,)).fetchone()[0]
    today_grid = today - today_evt

    open_gaps = q("SELECT ts_start, reason FROM gaps WHERE ts_end IS NULL "
                  "ORDER BY id DESC").fetchall()
    closed_today = q("SELECT COUNT(*) FROM gaps WHERE ts_end IS NOT NULL AND ts_start >= ?",
                     (midnight_ms,)).fetchone()[0]
    resolutions = q("SELECT COUNT(*) FROM resolutions").fetchone()[0]

    lines = [
        "=== NEKKO — estado del colector F2 ===",
        f"{'ultimo snapshot':<26}{_fmt_ts(last_ts)}  (hace {age_txt})",
        f"{'veredicto':<26}{verdict}",
        f"{'mercados trackeados':<26}{tracked}  (con snapshot en los ultimos 15 min)",
        f"{'snapshots hoy / total':<26}{today} / {total}",
        f"{'hoy por grilla / evento':<26}{today_grid} / {today_evt}",
        f"{'gaps abiertos':<26}{len(open_gaps)}   (cerrados hoy: {closed_today})",
    ]
    for ts_start, reason in open_gaps[:5]:
        lines.append(f"{'':<4}gap desde {_fmt_ts(ts_start)}  motivo: {reason or '-'}")
    lines.append(f"{'resoluciones guardadas':<26}{resolutions}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="nekko.sqlite")
    args = ap.parse_args()
    print(build_panel(args.db))


if __name__ == "__main__":
    main()
