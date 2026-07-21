"""Exporta el estado del colector a archivos JSON versionados que lee el sitio.

Corre en la VM (por cron). Escribe docs/data/collector_status.json y
docs/data/paper_kpis.json — números reales que build_site.py renderiza en
GitHub Pages sin que nadie corra nada. NUNCA toca la DB salvo lectura.

Uso:  python -m analysis.export_metrics --db nekko.sqlite --out docs/data
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from analysis.status import collect_status


def _num(x):
    """JSON no admite inf/nan → None (el sitio los muestra como ∞/—)."""
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return None
    return x


def _iso(ms: int | None) -> str | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def build_payloads(db_path: str) -> tuple[dict, dict]:
    s = collect_status(db_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    collector = {
        "generated_at": now_iso,
        "verdict": s["verdict"],
        "last_snapshot": _iso(s["last_snapshot_ms"]),
        "age_min": round(s["age_s"] / 60, 1) if s["age_s"] is not None else None,
        "markets_tracked": s["markets_tracked"],
        "snapshots_today": s["snapshots_today"], "snapshots_total": s["snapshots_total"],
        "grid_today": s["grid_today"], "events_today": s["events_today"],
        "gaps_open": s["gaps_open"], "gaps_closed_today": s["gaps_closed_today"],
        "resolutions_collector": s["resolutions_collector"],
        "process_starts": s["process_starts"], "last_start": _iso(s["last_start_ms"]),
        "systemd": s["systemd"] or None,
        "ram_free_mb": s["mem"].get("free_mb") if s["mem"] else None,
        "ram_total_mb": s["mem"].get("total_mb") if s["mem"] else None,
    }
    paper = {"generated_at": now_iso,
             "strategies": {name: {k: _num(v) for k, v in kp.items()}
                            for name, kp in s["paper"].items()}}
    return collector, paper


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="nekko.sqlite")
    ap.add_argument("--out", default="docs/data")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    collector, paper = build_payloads(args.db)
    (out / "collector_status.json").write_text(
        json.dumps(collector, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "paper_kpis.json").write_text(
        json.dumps(paper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK — {out}/collector_status.json + paper_kpis.json (verdict {collector['verdict']})")


if __name__ == "__main__":
    main()
