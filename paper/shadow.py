"""Runner shadow del paper engine: python -m paper.shadow [--db X] [--once]

Loop: procesar snapshots nuevos → dormir poll_s. Con --once hace una sola
pasada (útil contra una copia local de la DB) e imprime los KPIs corrientes.
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import yaml

from paper import strategies
from paper.engine import Engine, kpis
from storage import sqlite as store

log = logging.getLogger("paper")

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=store.DEFAULT_DB)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    with open(SETTINGS_PATH, encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    conn = store.connect(args.db)
    engine = Engine(conn, settings)
    engine.strategies = strategies.ALL
    log.info("shadow arrancado: estrategias %s", [s.name for s in strategies.ALL])

    if args.once:
        n = engine.process()
        print(f"ops generadas: {n}")
        for strat, k in kpis(conn).items():
            print(strat, {kk: round(vv, 4) if isinstance(vv, float) else vv
                          for kk, vv in k.items()})
        return

    while True:
        try:
            n = engine.process()
            if n:
                log.info("%d ops nuevas", n)
        except Exception:
            log.exception("ciclo shadow fallo; sigo")
        time.sleep(settings["paper"]["poll_s"])


if __name__ == "__main__":
    main()
