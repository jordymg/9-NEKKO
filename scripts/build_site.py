"""Genera el sitio público estático de NEKKO (GitHub Pages).

Corre en CI (GitHub Actions), no en la máquina de nadie. Lee docs/ + config +
(si existe) la DB del paper engine, y escribe HTML estático en build/.
Sin dependencias externas: renderer de Markdown y charts SVG son stdlib puro.

Diseño y garantías:
- Guard epistémico (ADR-0008): TODO KPI de reglas `draft_` se renderiza dentro de
  un bloque `.guard` rotulado como NO válido para gates. No existe camino de código
  que emita un KPI draft fuera del guard.
- Estado del colector: PLACEHOLDER honesto ("sin acceso a la VM"), con últimos
  valores conocidos y su timestamp. Nunca se fabrican números en vivo.

Uso:  python scripts/build_site.py [--out build] [--db nekko.sqlite]
"""
from __future__ import annotations

import argparse
import html
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# ---------------------------------------------------------------- navegación
# (out_name, label, nav_key). Orden = orden en la barra.
NAV = [
    ("index.html", "Inicio", "inicio"),
    ("estado.html", "Estado", "estado"),
    ("roadmap.html", "Roadmap", "roadmap"),
    ("decisiones.html", "Decisiones", "decisiones"),
    ("hallazgos.html", "Hallazgos F1", "hallazgos"),
    ("producto.html", "Producto", "producto"),
    ("arquitectura.html", "Arquitectura", "arquitectura"),
    ("api.html", "API", "api"),
    ("validacion.html", "Validación", "validacion"),
]

# Últimos valores conocidos del colector (STATUS s6, VM ahora inalcanzable).
# NO son datos en vivo — se muestran como "última lectura" con su timestamp.
COLLECTOR_LAST_KNOWN = {
    "timestamp": "2026-07-20 15:21 UTC",
    "verdict": "OK",
    "markets": "72",
    "snapshots_today": "996",
    "events_today": "143",
    "gaps": "0",
    "ram_free": "538 MB / 954 MB",
    "window_start": "2026-07-20 ~14:31 UTC",
}

# F1 — sesgo por mes (puntos, sesgo = implícita − frecuencia real).
# Fuente canónica: docs/results/f1-gross-2026-07-19.md (hallazgo negativo, settled).
F1_CONTROL = [("Mar", -1.57, 60), ("Abr", 1.15, 36), ("May", -5.81, 37), ("Jun", 0.62, 29)]
F1_EURO = [("Mar", 14.48, 98), ("Abr", -18.15, 100), ("May", 1.23, 116), ("Jun", -6.32, 81)]

# Umbrales del gate Fase 2→3 (VALIDATION.md) — referencia para el panel paper.
GATE_THRESHOLDS = {"pf": "> 1.2", "sharpe_op": "> 1", "max_dd": "< 10%", "expectancy": "> 0 neto"}


# ================================================================ Markdown
_TOKEN = "\x00%d\x00"


def _inline(text: str) -> str:
    """Markdown inline → HTML. Protege spans de código antes de formatear."""
    stash: list[str] = []

    def keep(m: re.Match) -> str:
        stash.append("<code>" + html.escape(m.group(1)) + "</code>")
        return _TOKEN % (len(stash) - 1)

    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    text = re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"<em>\1</em>", text)
    text = re.sub(r"(?<![_\w])_([^_\n]+)_(?![_\w])", r"<em>\1</em>", text)
    for i, val in enumerate(stash):
        text = text.replace(_TOKEN % i, val)
    return text


def _table(rows: list[str]) -> str:
    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]]
    out = ['<div class="table-scroll"><table><thead><tr>']
    out += [f"<th>{_inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def md_to_html(md: str) -> str:
    """Renderer de bloques (stdlib). Cubre el subconjunto que usan los docs."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # fenced code
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        # blank
        if not stripped:
            i += 1
            continue
        # heading
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue
        # hr
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            out.append("<hr>")
            i += 1
            continue
        # table (header + |---| separator)
        if "|" in line and i + 1 < n and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            tbl = [lines[i], lines[i + 1]]
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                tbl.append(lines[i])
                i += 1
            out.append(_table(tbl))
            continue
        # blockquote
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            out.append("<blockquote><p>" + "<br>".join(_inline(b) for b in buf) + "</p></blockquote>")
            continue
        # list
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = bool(re.match(r"\d+\.", m.group(2)))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < n:
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if mm:
                    items.append(_inline(mm.group(3).strip()))
                    i += 1
                elif lines[i].strip() and not lines[i].lstrip().startswith(("#", ">", "```")) \
                        and lines[i].startswith((" ", "\t")):
                    items[-1] += " " + _inline(lines[i].strip())  # continuación
                    i += 1
                else:
                    break
            out.append(f"<{tag}>" + "".join(f"<li>{it}</li>" for it in items) + f"</{tag}>")
            continue
        # paragraph
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^\s*(#{1,6}\s|[-*]\s|\d+\.\s|>|```|-{3,}$)", lines[i]) and "|" not in lines[i]:
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + "<br>".join(_inline(b) for b in buf) + "</p>")
    return "\n".join(out)


# ================================================================ layout
def _stamps() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    ar = now - timedelta(hours=3)  # Argentina UTC-3 todo el año
    return now.strftime("%Y-%m-%d %H:%M UTC"), ar.strftime("%Y-%m-%d %H:%M (AR)")


def _nav(active: str) -> str:
    items = "".join(
        f'<a href="{out}"{" class=\"active\"" if key == active else ""}>{label}</a>'
        for out, label, key in NAV)
    return f'<nav class="tabs">{items}</nav>'


def page(active: str, title: str, body: str) -> str:
    utc, ar = _stamps()
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="robots" content="noindex">
<title>{html.escape(title)} · NEKKO</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="site-head">
  <div class="brand">
    <span class="brand__mark">NE<b>KK</b>O</span>
    <span class="brand__tag">¿existe una ventaja repetible en Polymarket?</span>
  </div>
  {_nav(active)}
</header>
<main class="wrap">
{body}
</main>
<footer>
  <span>NEKKO · proyecto de I+D con fecha de muerte 2026-08-12</span>
  <span class="clock">generado {utc} · {ar}</span>
</footer>
</body>
</html>
"""


def doc_page(active: str, title: str, md_path: Path) -> str:
    body = f'<article class="doc">{md_to_html(md_path.read_text(encoding="utf-8"))}</article>'
    return page(active, title, body)


# ================================================================ dashboard
def f1_chart_svg() -> str:
    """Barras agrupadas por mes: sesgo control vs euro. Muestra los flips de signo."""
    W, H = 720, 300
    pad_l, pad_r, pad_t, pad_b = 20, 20, 30, 44
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    zero_y = pad_t + plot_h / 2
    vmax = 20.0
    months = [m for m, _, _ in F1_EURO]
    group_w = plot_w / len(months)
    bar_w = group_w * 0.28
    C_CTRL, C_EURO = "#5ad1c8", "#8b7fe8"

    def bar(cx, val, color):
        h = abs(val) / vmax * (plot_h / 2)
        y = zero_y - h if val >= 0 else zero_y
        return (f'<rect x="{cx - bar_w/2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{h:.1f}" rx="2" fill="{color}"/>')

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="Sesgo por mes, control y euro">']
    # gridlines ±10, ±20
    for gv in (-20, -10, 10, 20):
        gy = zero_y - gv / vmax * (plot_h / 2)
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W-pad_r}" y2="{gy:.1f}" '
                     f'stroke="#1e2632" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l}" y="{gy-3:.1f}" fill="#6b7889" font-size="10" '
                     f'font-family="monospace">{gv:+d}pt</text>')
    parts.append(f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{W-pad_r}" y2="{zero_y:.1f}" '
                 f'stroke="#3a4557" stroke-width="1.5"/>')
    for idx, month in enumerate(months):
        gx = pad_l + group_w * (idx + 0.5)
        ctrl = F1_CONTROL[idx][1]
        euro = F1_EURO[idx][1]
        parts.append(bar(gx - bar_w * 0.62, ctrl, C_CTRL))
        parts.append(bar(gx + bar_w * 0.62, euro, C_EURO))
        parts.append(f'<text x="{gx:.1f}" y="{H-pad_b+22:.1f}" fill="#93a1b5" '
                     f'font-size="12" text-anchor="middle" font-family="monospace">{month}</text>')
    parts.append("</svg>")
    return "".join(parts)


def collector_placeholder() -> str:
    lk = COLLECTOR_LAST_KNOWN
    tiles = [
        ("veredicto", lk["verdict"]), ("mercados", lk["markets"]),
        ("snapshots (día)", lk["snapshots_today"]), ("eventos (día)", lk["events_today"]),
        ("gaps", lk["gaps"]), ("ram libre", lk["ram_free"]),
    ]
    grid = "".join(f'<div class="metric"><div class="k">{k}</div>'
                   f'<div class="v">{html.escape(v)}</div></div>' for k, v in tiles)
    return f"""<div class="placeholder">
  <span class="placeholder__tag"><span class="dot"></span>sin acceso a la VM — se completa cuando se recupere SSH</span>
  <h3>Estado del colector F2</h3>
  <p>La VM de Oracle sigue recolectando, pero se perdió la clave SSH: no podemos leer su
     estado en vivo. Abajo, la <strong>última lectura conocida</strong> (no es tiempo real).
     El slot queda listo para enchufar datos reales apenas se recupere el acceso.</p>
  <div class="lastknown">{grid}</div>
  <p class="stamp">última lectura: {lk['timestamp']} · ventana de 14 días iniciada {lk['window_start']}</p>
</div>"""


def _read_kpis(db_path: Path) -> dict:
    if not db_path.exists():
        return {}
    try:
        import sys
        sys.path.insert(0, str(ROOT))
        from paper.engine import kpis
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        return kpis(conn)
    except Exception:
        return {}


def _draft_strategies() -> list[str]:
    txt = (ROOT / "config" / "settings.yaml").read_text(encoding="utf-8")
    return re.findall(r"^\s{4}(draft_\w+):", txt, re.M)


def paper_panel(db_path: Path) -> str:
    """Panel de KPIs del paper engine — SIEMPRE dentro del guard para reglas draft.
    Si no hay datos, se rotula igual; nunca se fabrican números."""
    stats = _read_kpis(db_path)
    strategies = sorted(set(_draft_strategies()) | set(stats))
    kpi_defs = [("PF", "pf", GATE_THRESHOLDS["pf"]),
                ("Expectancy", "expectancy", GATE_THRESHOLDS["expectancy"]),
                ("Sharpe/op", "sharpe_op", GATE_THRESHOLDS["sharpe_op"]),
                ("Max DD", "max_dd", GATE_THRESHOLDS["max_dd"]),
                ("Ops", "n_cerradas", "—")]
    blocks = []
    for strat in strategies:
        k = stats.get(strat, {})
        tiles = []
        for label, key, gate in kpi_defs:
            if key in k:
                val = k[key]
                shown = f"{val:.2f}" if isinstance(val, float) and val != float("inf") \
                    else ("∞" if val == float("inf") else str(val))
            else:
                shown = "—"
            tiles.append(f'<div class="kpi"><div class="k">{label}</div>'
                         f'<div class="v">{shown}</div><div class="gate">gate {gate}</div></div>')
        blocks.append(f'<div class="strat-name">{html.escape(strat)}</div>'
                      f'<div class="kpi-grid">{"".join(tiles)}</div>')
    empty = "" if stats else (
        '<p class="guard__note" style="margin-top:16px">Aún sin operaciones legibles: '
        'la DB en vivo está en la VM inalcanzable. Las celdas muestran <b>—</b> hasta '
        'poder leerla; el guard y la estructura ya están listos para los números reales.</p>')
    return f"""<div class="guard">
  <div class="guard__banner"><span class="ico">⚠</span>Reglas BORRADOR — KPIs NO válidos para ningún gate</div>
  <div class="guard__body">
    <p class="guard__note">Estas estrategias (<code>draft_*</code>) se escribieron para
      probar el motor <b>antes</b> de tener una tesis validada por datos. Por
      <b>ADR-0008</b>, sus KPIs <b>no cuentan como evidencia</b> ni habilitan el gate
      Fase 2→3 (VALIDATION.md). Se muestran solo para verificar la mecánica del engine.</p>
    {"".join(blocks)}
    {empty}
  </div>
</div>"""


def build_index(db_path: Path) -> str:
    verdict = COLLECTOR_LAST_KNOWN["verdict"]
    metrics = f"""<div class="metrics">
  <div class="metric"><div class="k">Fase</div><div class="v accent">0</div><div class="s">Edge Discovery</div></div>
  <div class="metric"><div class="k">Kill date</div><div class="v">08-12</div><div class="s">2026</div></div>
  <div class="metric"><div class="k">Ventana F2</div><div class="v">14 d</div><div class="s">desde 07-20</div></div>
  <div class="metric"><div class="k">Tesis A/B (histórico)</div><div class="v">nula</div><div class="s">débil-a-nula</div></div>
</div>"""

    chart = f"""<div class="chart-card">
  <h3>F1 — sesgo por mes (control vs. binarias europeas)</h3>
  <p class="sub">Sesgo = probabilidad implícita − frecuencia real, en puntos. GROSS / exploratorio.</p>
  {f1_chart_svg()}
  <div class="legend">
    <span><i style="background:#5ad1c8"></i>Control Up/Down</span>
    <span><i style="background:#8b7fe8"></i>Binarias europeas</span>
  </div>
  <div class="verdict">Cada mes <b>cambia de signo</b>: el sesgo que parecía existir era
    <b>artefacto de régimen</b>, no una ventaja. Pooled ≈ 0 · corr(implícita, modelo) = 0.956.
    → Ningún candidato a Tesis A sobrevive. <a href="hallazgos.html">Ver detalle</a>.</div>
</div>"""

    hero = """<section class="hero">
  <p class="eyebrow">Panel · Fase 0</p>
  <h1>Medir antes de apostar.</h1>
  <p>NEKKO no opera: mide. Busca, con datos y de forma falsable, si existe una ventaja
     repetible y explotable en Polymarket — o justifica matar el proyecto. Este sitio se
     regenera solo desde el repositorio.</p>
</section>"""

    return page("inicio", "Panel", f"""{hero}
{metrics}
<div class="section-label">Motor de práctica (paper trading · shadow)</div>
{paper_panel(db_path)}
<div class="section-label">Recolección en vivo</div>
{collector_placeholder()}
<div class="section-label">Hallazgo F1 (backtest histórico)</div>
{chart}""")


# ================================================================ ADRs
def build_adrs(out: Path) -> str:
    adr_files = sorted(DOCS.glob("decisions/*.md"))
    rows = []
    for f in adr_files:
        txt = f.read_text(encoding="utf-8")
        title = re.search(r"^#\s*(.+)$", txt, re.M)
        title = title.group(1) if title else f.stem
        status = re.search(r"\*\*Status:\*\*\s*(.+)", txt)
        status = status.group(1).strip() if status else ""
        num_m = re.search(r"ADR-(\d+)", title)
        num = num_m.group(1) if num_m else f.stem
        short = re.sub(r"^ADR-\d+:\s*", "", title)
        out_name = f"adr-{num}.html"
        (out / out_name).write_text(doc_page("decisiones", title, f), encoding="utf-8")
        rows.append(f'<a class="adr-item" href="{out_name}">'
                    f'<span class="num">ADR-{num}</span>'
                    f'<span class="ttl">{html.escape(short)}</span>'
                    f'<span class="badge">{html.escape(status)}</span></a>')
    body = f"""<article class="doc">
  <h1>Decisiones de arquitectura</h1>
  <p>Registro de decisiones (ADR): elecciones settled. Si algo se contradice, se propone
     una ADR nueva, no se reabre la vieja.</p>
  <div class="adr-list">{"".join(rows)}</div>
</article>"""
    return page("decisiones", "Decisiones", body)


# ================================================================ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build")
    ap.add_argument("--db", default="nekko.sqlite")
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    db_path = ROOT / args.db

    # assets
    (out / "style.css").write_text((ROOT / "site" / "style.css").read_text(encoding="utf-8"),
                                   encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    # dashboard
    (out / "index.html").write_text(build_index(db_path), encoding="utf-8")

    # doc pages
    doc_map = [
        ("estado.html", "Estado", "estado", DOCS / "STATUS.md"),
        ("roadmap.html", "Roadmap", "roadmap", DOCS / "ROADMAP.md"),
        ("hallazgos.html", "Hallazgos F1", "hallazgos", DOCS / "results" / "f1-gross-2026-07-19.md"),
        ("producto.html", "Producto", "producto", DOCS / "PRD.md"),
        ("arquitectura.html", "Arquitectura", "arquitectura", DOCS / "ARCHITECTURE.md"),
        ("api.html", "API", "api", DOCS / "API-VERIFICATION.md"),
        ("validacion.html", "Validación", "validacion", ROOT / "VALIDATION.md"),
    ]
    for out_name, title, key, path in doc_map:
        (out / out_name).write_text(doc_page(key, title, path), encoding="utf-8")

    # ADR index + pages
    (out / "decisiones.html").write_text(build_adrs(out), encoding="utf-8")

    pages = len(list(out.glob("*.html")))
    print(f"OK — {pages} páginas en {out}/")


if __name__ == "__main__":
    main()
