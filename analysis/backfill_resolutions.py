"""Backfill one-shot / diario de resoluciones vía Gamma (ADR-0009).

Escritura ADITIVA a `resolutions` solamente. NUNCA escribe `snapshots` ni toca
el proceso del colector. Idempotente (INSERT OR IGNORE, market_id es PK): re-correr
no duplica y solo consulta los mercados que aún no tienen resolución.

Diseño para no molestar al colector: fase de LECTURA (Gamma, sin lock de escritura)
y luego una ÚNICA transacción de escritura breve al final. Fail-closed: si Gamma es
inalcanzable, loguea y sale ≠0 SIN escritura parcial.

Uso:  python -m analysis.backfill_resolutions --db nekko.sqlite [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys

import requests

from connectors import polymarket as pm

log = logging.getLogger("backfill")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="nekko.sqlite")
    ap.add_argument("--limit", type=int, default=None, help="tope de mercados a consultar (test)")
    args = ap.parse_args()

    # RW pero SOLO para resolutions; busy_timeout para convivir con el colector (WAL)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA busy_timeout=10000")

    done = {r[0] for r in conn.execute(
        "SELECT market_id FROM resolutions WHERE outcome IS NOT NULL")}
    tracked = [r[0] for r in conn.execute("SELECT DISTINCT market_id FROM snapshots")]
    todo = [m for m in tracked if m not in done]
    if args.limit:
        todo = todo[:args.limit]

    log.info("trackeados=%d ya_resueltos=%d a_consultar=%d", len(tracked), len(done), len(todo))

    results: list[tuple] = []
    pending = skipped = 0
    for mid in todo:
        try:
            d = pm._get(f"{pm.GAMMA_BASE}/markets/{mid}")
        except requests.HTTPError as exc:
            skipped += 1
            log.warning("market %s HTTP %s — skip", mid,
                        getattr(exc.response, "status_code", "?"))
            continue
        except (requests.RequestException, ValueError) as exc:
            # Gamma inalcanzable / respuesta ilegible → fail closed, sin escribir nada
            log.error("Gamma inaccesible en market %s (%s) — FAIL CLOSED, sin escritura", mid, exc)
            sys.exit(1)
        page = d if isinstance(d, list) else [d]
        if not page:
            skipped += 1
            continue
        m = pm._normalize_market(page[0])
        if m["outcome"] is None:
            pending += 1
            log.info("pending (sin outcome UMA-final): %s", mid)
            continue
        results.append((mid, m["outcome"], m.get("closed_time")))

    # escritura ÚNICA y breve (el colector escribe snapshots en los huecos)
    if results:
        conn.executemany(
            "INSERT OR IGNORE INTO resolutions (market_id, outcome, resolved_at, source) "
            "VALUES (?, ?, ?, 'backfill')", results)
        conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0]
    print(f"backfill: escritas={len(results)} pending={pending} skip={skipped} "
          f"| consultados={len(todo)} de {len(tracked)} trackeados "
          f"| resoluciones totales ahora={total}")


if __name__ == "__main__":
    main()
