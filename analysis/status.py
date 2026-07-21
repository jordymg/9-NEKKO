"""Panel de estado del colector F2 — solo lectura, solo stdlib.

Uso:  python -m analysis.status [--db nekko.sqlite]

Un vistazo y sabés si el colector está vivo: frescura del último snapshot con
veredicto OK/STALE/DOWN, mercados trackeados, snapshots de hoy (grilla vs.
evento), gaps abiertos con motivo, resoluciones y reinicios del proceso.

`collect_status()` devuelve el estado crudo (dict) y lo reusa el exporter que
publica los números al sitio (analysis/export_metrics.py).
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
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


def _mem() -> dict:
    """RAM (solo Linux, /proc/meminfo). En la VM refleja el shape de 1GB."""
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, val = line.split(":", 1)
                info[key] = int(val.strip().split()[0])
        return {"free_mb": info["MemAvailable"] // 1024, "total_mb": info["MemTotal"] // 1024}
    except (OSError, KeyError, ValueError):
        return {}


def _systemd() -> dict:
    """NRestarts/Result del unit (best-effort; solo funciona en la VM)."""
    try:
        out = subprocess.run(
            ["systemctl", "show", "nekko-collector", "-p", "NRestarts", "-p", "Result"],
            capture_output=True, text=True, timeout=5)
        d = dict(l.split("=", 1) for l in out.stdout.strip().splitlines() if "=" in l)
        if "NRestarts" in d:
            return {"nrestarts": int(d["NRestarts"]), "result": d.get("Result", "")}
    except Exception:
        pass
    return {}


def collect_status(db_path: str) -> dict:
    """Estado crudo del colector. Fuente única para el panel y el exporter."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    q = conn.execute
    now_ms = int(time.time() * 1000)
    midnight_ms = int(datetime.now().replace(hour=0, minute=0, second=0,
                                             microsecond=0).timestamp() * 1000)

    last_ts = q("SELECT MAX(ts) FROM snapshots").fetchone()[0]
    if last_ts is None:
        verdict, age = "DOWN (sin snapshots)", None
    else:
        age = (now_ms - last_ts) / 1000
        verdict = ("OK" if age <= STALE_S
                   else f"STALE (>{STALE_S // 60}min)" if age <= DOWN_S
                   else f"DOWN (>{DOWN_S // 60}min)")

    tracked = q("SELECT COUNT(DISTINCT market_id) FROM snapshots WHERE ts >= ?",
                (now_ms - TRACKED_WINDOW_S * 1000,)).fetchone()[0]
    total = q("SELECT COUNT(*) FROM snapshots_valid").fetchone()[0]
    today = q("SELECT COUNT(*) FROM snapshots_valid WHERE ts >= ?", (midnight_ms,)).fetchone()[0]
    today_evt = q("SELECT COUNT(*) FROM snapshots_valid WHERE ts >= ? AND trigger = 'event'",
                  (midnight_ms,)).fetchone()[0]
    open_gaps = q("SELECT ts_start, reason FROM gaps WHERE ts_end IS NULL ORDER BY id DESC").fetchall()
    closed_today = q("SELECT COUNT(*) FROM gaps WHERE ts_end IS NOT NULL AND ts_start >= ?",
                     (midnight_ms,)).fetchone()[0]
    resolutions = q("SELECT COUNT(*) FROM resolutions WHERE source = 'collector'").fetchone()[0]
    starts, last_start = q("SELECT COUNT(*), MAX(ts_start) FROM collector_runs").fetchone()

    try:
        from paper.engine import kpis
        paper = kpis(conn)
    except Exception:
        paper = {}

    return {
        "generated_at_ms": now_ms,
        "last_snapshot_ms": last_ts, "age_s": age, "verdict": verdict,
        "markets_tracked": tracked,
        "snapshots_today": today, "snapshots_total": total,
        "grid_today": today - today_evt, "events_today": today_evt,
        "gaps_open": len(open_gaps), "gaps_open_detail": open_gaps, "gaps_closed_today": closed_today,
        "resolutions_collector": resolutions,
        "process_starts": starts, "last_start_ms": last_start,
        "systemd": _systemd(), "mem": _mem(), "paper": paper,
    }


def build_panel(db_path: str) -> str:
    s = collect_status(db_path)
    age_txt = _fmt_age(s["age_s"]) if s["age_s"] is not None else "-"
    lines = [
        "=== NEKKO — estado del colector F2 ===",
        f"{'ultimo snapshot':<26}{_fmt_ts(s['last_snapshot_ms'])}  (hace {age_txt})",
        f"{'veredicto':<26}{s['verdict']}",
        f"{'mercados trackeados':<26}{s['markets_tracked']}  (con snapshot en los ultimos 15 min)",
        f"{'snapshots hoy / total':<26}{s['snapshots_today']} / {s['snapshots_total']}",
        f"{'hoy por grilla / evento':<26}{s['grid_today']} / {s['events_today']}",
        f"{'gaps abiertos':<26}{s['gaps_open']}   (cerrados hoy: {s['gaps_closed_today']})",
    ]
    for ts_start, reason in s["gaps_open_detail"][:5]:
        lines.append(f"{'':<4}gap desde {_fmt_ts(ts_start)}  motivo: {reason or '-'}")
    lines.append(f"{'resoluciones (colector)':<26}{s['resolutions_collector']}")
    restart_note = f"  (ultimo: {_fmt_ts(s['last_start_ms'])})" if s["last_start_ms"] else ""
    lines.append(f"{'arranques del proceso':<26}{s['process_starts']}{restart_note}")
    if s["systemd"]:
        lines.append(f"{'  systemd':<26}NRestarts={s['systemd']['nrestarts']}, "
                     f"result={s['systemd']['result']}")
    if s["paper"]:
        lines.append("--- paper (shadow, reglas DRAFT: kpis no validos para gates) ---")
        for strat in sorted(s["paper"]):
            k = s["paper"][strat]
            pf = f"{k['pf']:.2f}" if k["pf"] != float("inf") else "inf"
            lines.append(f"{strat:<26}abiertas {k['n_abiertas']:<3} cerradas {k['n_cerradas']:<4} "
                         f"PF {pf:<6} pnl {k['pnl_total']:+.2f}")
    if s["mem"]:
        lines.append(f"{'ram disponible':<26}{s['mem']['free_mb']} MB de {s['mem']['total_mb']} MB")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="nekko.sqlite")
    args = ap.parse_args()
    print(build_panel(args.db))


if __name__ == "__main__":
    main()
