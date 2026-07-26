"""F2 power check — proyección de mercados resueltos a la fecha de cierre.

READ-ONLY (mode=ro, WAL permite lectura concurrente sin molestar al colector).
No escribe la DB, no toca el servicio, no reinicia nada. Stdlib + sqlite3.

Uso:  python -m analysis.power_check --db nekko.sqlite

Auto-inspecciona el schema y se adapta. Si no encuentra la tabla de mercados o
la marca de resolución, NO adivina: imprime el schema real y sale con código 2
(un column equivocado contando cero es peor que un fallo honesto).

Sobre el umbral (BAR): este script NO inventa un número. Reporta la proyección
contra las barras que los docs SÍ definen, rotulando la procedencia de cada una
y su unidad — porque ninguna barra del proyecto gatea específicamente el conteo
de mercados resueltos de F2 (ver la sección GATE en la salida). La decisión de
qué barra aplica es humana.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone

# Cierre de la ventana F2: 14 días desde el arranque 2026-07-20 ~14:31 UTC.
CLOSE = datetime(2026, 8, 3, 14, 31, tzinfo=timezone.utc)
DAY_MS = 86_400_000

# Barras que los docs DEFINEN (con procedencia y unidad). Ninguna gatea el
# conteo de mercados resueltos de F2 específicamente — ver GATE en la salida.
BARS = [
    ("PRD §3 / §5-F3: ≥300 observaciones (soporte de tesis, neto de costos)", 300, "observaciones"),
    ("PRD §7 DONE: ≥1000 mercados resueltos", 1000, "mercados resueltos (F1 histórico, NO F2)"),
]


def _tables(conn) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({name})")}
        out[name] = cols
    return out


def _fail_schema(schema: dict[str, set[str]], missing: str) -> None:
    print(f"NO SE PUDO CORRER: {missing}")
    print("Schema real (tablas / columnas):")
    for t, cols in sorted(schema.items()):
        print(f"  {t}: {', '.join(sorted(cols))}")
    sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="nekko.sqlite")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # salida UTF-8 aunque la consola no lo sea
    except (AttributeError, ValueError):
        pass

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    schema = _tables(conn)

    # --- auto-inspección: tablas/columnas requeridas ---
    if "snapshots" not in schema:
        _fail_schema(schema, "no existe la tabla de snapshots ('snapshots')")
    snap_cols = schema["snapshots"]
    for c in ("market_id", "ts", "tte_hours"):
        if c not in snap_cols:
            _fail_schema(schema, f"la tabla snapshots no tiene la columna '{c}'")
    if "resolutions" not in schema:
        _fail_schema(schema, "no existe la tabla de resoluciones ('resolutions')")
    res_cols = schema["resolutions"]
    for c in ("market_id", "outcome"):
        if c not in res_cols:
            _fail_schema(schema, f"la tabla resolutions no tiene la columna '{c}'")
    has_source = "source" in res_cols

    q = conn.execute
    # --- conteos base ---
    total_tracked = q("SELECT COUNT(DISTINCT market_id) FROM snapshots").fetchone()[0]
    total_snapshots = q("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    min_ts, max_ts = q("SELECT MIN(ts), MAX(ts) FROM snapshots").fetchone()
    if not min_ts or total_tracked == 0:
        print("Sin snapshots todavía — nada que proyectar.")
        sys.exit(0)

    # resueltos-a-la-fecha ENTRE mercados trackeados por el colector (no los del
    # backtest F1). Se cuenta por pertenencia a snapshots, no por la etiqueta source.
    resolved_tracked = q(
        "SELECT COUNT(DISTINCT r.market_id) FROM resolutions r "
        "WHERE r.outcome IS NOT NULL AND r.market_id IN (SELECT DISTINCT market_id FROM snapshots)"
    ).fetchone()[0]
    resolved_src = (q("SELECT COUNT(*) FROM resolutions WHERE source='collector' AND outcome IS NOT NULL")
                    .fetchone()[0] if has_source else None)

    elapsed_days = (max_ts - min_ts) / DAY_MS
    now = datetime.fromtimestamp(max_ts / 1000, timezone.utc)
    remaining_days = (CLOSE - now).total_seconds() / 86_400

    # --- Método A: extrapolación lineal de la tasa de resolución (lo pedido) ---
    rate_per_day = resolved_tracked / elapsed_days if elapsed_days > 0 else 0.0
    proj_add_A = rate_per_day * max(0.0, remaining_days)
    proj_total_A = resolved_tracked + proj_add_A

    # --- Método B: por vencimiento estimado de cada mercado trackeado ---
    # end_est = último snapshot del mercado (ts + tte_hours). Cuenta cuántos
    # mercados YA trackeados vencen antes del cierre. No incluye mercados que
    # se abran de acá al cierre → también es un piso para el total.
    # Join contra el MAX(ts) por mercado (una pasada por idx_snap_market): O(n),
    # no correlacionado. El GROUP BY interno colapsa cualquier ts duplicado.
    close_ms = int(CLOSE.timestamp() * 1000)
    expire_by_close = q("""
        SELECT COUNT(*) FROM (
            SELECT s.ts + CAST(s.tte_hours*3600000 AS INTEGER) AS end_est
            FROM snapshots s
            JOIN (SELECT market_id AS mid, MAX(ts) AS mts FROM snapshots GROUP BY market_id) m
              ON s.market_id = m.mid AND s.ts = m.mts
            GROUP BY s.market_id
        ) WHERE end_est IS NOT NULL AND end_est <= ?
    """, (close_ms,)).fetchone()[0]

    def _fmt(ms):
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("=" * 64)
    print("NEKKO F2 — POWER CHECK (mercados resueltos proyectados)")
    print("=" * 64)
    print(f"DB (read-only)          {args.db}")
    print(f"ventana de datos        {_fmt(min_ts)}  →  {_fmt(max_ts)}  ({elapsed_days:.2f} d)")
    print(f"cierre F2 (objetivo)    {_fmt(close_ms)}  (faltan {remaining_days:.2f} d)")
    print("-" * 64)
    print(f"mercados trackeados (distintos)   {total_tracked}")
    print(f"snapshots totales                 {total_snapshots}  (observaciones crudas; correlacionadas dentro de cada mercado)")
    print(f"resueltos a la fecha (trackeados) {resolved_tracked}")
    if has_source:
        print(f"  · de esos, source='collector'   {resolved_src}")
    print("-" * 64)
    print("MÉTODO A — extrapolación lineal de la tasa de resolución:")
    print(f"  tasa = {resolved_tracked} resueltos / {elapsed_days:.2f} d = {rate_per_day:.3f} /d")
    print(f"  proyección = {resolved_tracked} + {rate_per_day:.3f}/d × {max(0.0,remaining_days):.2f} d")
    print(f"             = {proj_total_A:.0f} mercados resueltos al cierre")
    print("  CAVEAT: las resoluciones se agrupan cerca del vencimiento (los binarios")
    print("  europeos vencen en su end_date, no de a poco). Si aún no venció casi")
    print("  ninguno, la tasa observada ≈ 0 y la extrapolación lineal es un PISO, no un techo.")
    print("-" * 64)
    print("MÉTODO B — por vencimiento estimado (mejor estimador del cohorte actual):")
    print(f"  end_est(mercado) = último snapshot: ts + tte_hours")
    print(f"  mercados ya trackeados que vencen ≤ cierre = {expire_by_close}")
    print("  (no incluye mercados que se abran de acá al cierre → también piso del total)")
    print("-" * 64)
    print("GATE — el proyecto NO define una barra de 'mercados resueltos' para F2:")
    for label, val, unit in BARS:
        best = max(proj_total_A, expire_by_close)
        verdict = "≥ barra" if best >= val else "< barra"
        print(f"  [{verdict}] {label}")
        print(f"           barra={val} {unit}  vs  proyección≈{best:.0f} (mejor de A/B)")
    print("  · VALIDATION.md NO define barra de mercados resueltos para F2: su gate")
    print("    de Fase 0 es cualitativo y su ≥1000 es de operaciones simuladas (Fase 2→3).")
    print("  · Unidades distintas: ≥300 es OBSERVACIONES (no mercados); ≥1000 es de F1")
    print("    HISTÓRICO. Cuál gatea F2 es una decisión humana — ver reporte.")
    print("=" * 64)


if __name__ == "__main__":
    main()
