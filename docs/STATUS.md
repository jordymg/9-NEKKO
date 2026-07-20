# Status — NEKKO

> AI agents: read this FIRST. It's the live state of the project. Update it at the end of every session (see session-close prompt).

**Last updated:** 2026-07-19 (session 4, intermediate close) — F2 collector built + verified live (53 markets, grid + event triggers, gaps table, status panel). **VPS deployment mid-flight**: Oracle Cloud account + network ready; instance creation blocked tonight by "Out of capacity" — retry tomorrow. Local collector deliberately stopped; the official 14-day window starts when the VPS collector is green.
**Current phase:** Phase 0 — Edge Discovery (kill date **2026-08-12**)

## Done (recent)
- 2026-07-19 (s4) F2 collector built + live-verified: grid 5 min sobre 53 mercados (≥50 PRD), event triggers por movimiento de spot (ejercitado: 318 test + eventos reales a 0.3%), backfill de resoluciones, tabla `gaps`. Panel `python -m analysis.status` (veredicto OK/STALE/DOWN) + README en español
- 2026-07-19 (s4) Data hygiene ANTES de la corrida oficial: `collector_runs` + vista `snapshots_valid` cercan los 318 snapshots de evento con umbral de prueba; `resolutions.source` separa backfills del colector vs backtest (panel cuenta solo colector)
- 2026-07-19 (s4) ADR-0007 (deploy) + assets: `deploy/nekko-collector.service` (systemd Restart=always), clave SSH dedicada generada, README con panel vía SSH y pull de DB con `sqlite3 .backup` (nunca git)
- 2026-07-19 (s4) Oracle Cloud: cuenta creada y verificada (Always Free, home region PHX, AD-1). Red armada y verificada a mano: VCN `nekko-vcn`, `public-subnet` (10.0.0.0/24, regional), internet gateway `nekko-igw`, ruta 0.0.0.0/0 en la tabla default. Security list default sin tocar (SSH 22 in, egress all out)
- 2026-07-19 (s3) **Up/Down convention verified 6/6** against Binance 1m klines (mandatory step 1) — bias signs trustworthy; recorded with market ids in `docs/API-VERIFICATION.md` §4. Bonus findings: resolution source is Chainlink; `eventStartTime` gives window open directly
- 2026-07-19 (s3) Enumeration truncation FIXED: Gamma accepts datetime bounds → recursive sub-day window splitting down to 1h; stratified multi-month sampling with per-week quotas (`collect_stratified`)
- 2026-07-19 (s3) Stratified 4-month run (mar-jun): 390 euro + 320 control, 2,640 snapshots, zero data failures. **Negative finding**: +9pt control bias and +22pt euro bias both vanished under decorrelation (per-month sign flips; control pooled −2pt; euro pooled −1pt; corr(implied,model)=0.956). No Thesis A candidate. Evidence tables persisted in `docs/results/f1-gross-2026-07-19.md`
- 2026-07-19 (night) Vertical slice end-to-end: incremental persistence (per-market), patient retries (multi-minute outages), Up/Down **control group** sampled (~3 min pre-close, 1-min fidelity), duration segmentation, `--gross` mode with explicit exploratory labeling. Run Jun 1→Jul 13: 350 euro + 120 control → 2,186 snapshots, zero data failures
- 2026-07-19 (night) API finding (documented in `docs/API-VERIFICATION.md`): `interval=max` returns EMPTY history for older resolved markets; responses truncate at ~1,000 points → sampling now uses explicit `startTs/endTs` windows with duration-adaptive fidelity
- 2026-07-19 (night) First bias table produced — **GROSS/exploratory, not evidence**: apparent +22pt euro bias and +9pt control bias are both confounded by temporal clustering (nearly all markets from a single June week → outcomes correlated via market regime; model ≈ implied supports the regime explanation). Do NOT cite these numbers as findings
- 2026-07-19 F1 pipeline complete (`backtest/historical.py`): parses European binaries, samples 6 TTE points/market, bias table net of costs. Dry-run OK (30 markets → 180 snapshots; model ≈ implied, sane). Full Jan→Jul run **FAILED mid-way** (transient DNS outage at ~April; retry window only ~30s at the time — since fixed) — nothing persisted
- 2026-07-19 Lognormal reference model (`models/probability_model.py`) + append-only SQLite storage
- 2026-07-18 Cost model pinned in `config/settings.yaml` (ADR-0005): taker fee 7%×p(1−p) verified vs official docs; spread 0.02/0.01 measured live on 42 active books
- 2026-07-18 Read-only connectors live-tested: Polymarket Gamma+CLOB (date-window enumeration, price history, book) and Binance (spot, paginated klines, realized vol)
- 2026-07-13 Polymarket API verified (GO): resolved markets + outcomes via Gamma, price history via CLOB (10-min full-life, 1-min with windowed `startTs/endTs`), order book live-only. Full findings + caveats in `docs/API-VERIFICATION.md`
- 2026-07-12 Project renamed QUANT-EDGE → NEKKO (pre-commit, no history impact)
- 2026-07-12 Kickoff complete: VALIDATION.md (5 candidate theses + gates), PRD (graded B), architecture, roadmap, 4 ADRs

## Next up — TOMORROW: create the Oracle instance and go live (TIME-CRITICAL)
State: account + network done (see Done s4). Instance creation blocked tonight by **"Out of capacity"** on `VM.Standard.A1.Flex` in AD-1 (PHX). The 14-day window needs the collector green by **~2026-07-28**.
1. Create instance: **retry A1** (1 OCPU / 6GB config already validated end-to-end incl. SSH key + public IP assignment) → fallback **`VM.Standard.E2.1.Micro`** (x86, 1GB RAM — collector must stay lean; it is: stdlib + requests + pyyaml, no pandas in the collector path).
2. Then execute the pending VPS handoff: SSH in → `apt install python3-venv sqlite3` → clone repo → venv + `pip install -r requirements.txt` (+ pyyaml) → timezone UTC → install `deploy/nekko-collector.service` → `systemctl enable --now`.
3. **Kill/restart verification**: kill the process, confirm systemd revives it, panel returns to OK, threshold at production 0.3%.
4. Leave the long run going — official 14-day window starts there (local collector already stopped on purpose; no gap accounting before the VPS start).
5. ~48h later: data-quality check (grid completeness, event counts at real threshold, gap review, first C/D/E sanity peek).

While it collects: F3 groundwork over `nekko.sqlite` (A/B verdicts writable from F1 evidence). Icebox: barrier family; low-liquidity euro residual (underpowered).

## Evidence pointers
- Negative finding + per-month tables: `docs/results/f1-gross-2026-07-19.md` (run `76188a8592e2` in `nekko.sqlite`)
- Convention verification: `docs/API-VERIFICATION.md` §4

## Blocked / waiting
- Weekly time budget undefined (only the kill date constrains scope) — Jordi to define

## Session log
| Date | Tool used | What happened | Decisions made (→ ADR#) |
|------|-----------|---------------|-------------------------|
| 2026-07-12 | Claude (chat) | Kickoff: spec reviewed, Trading OS descoped to R&D project, theses A–E defined, docs generated | 0001, 0002, 0003, 0004 |
| 2026-07-13 | Claude Code | Verified Polymarket Gamma + CLOB APIs live: GO for F1. Wrote `docs/API-VERIFICATION.md` (fields, granularity, pagination workaround, caveats). No new ADRs — findings, not decisions | — |
| 2026-07-18/19 | Claude Code | Built + live-tested both connectors; pinned cost model (fee verified, spread measured); built lognormal model, SQLite storage, F1 backtest pipeline; dry-run sane; full Jan→Jul run launched (in progress at close); opened [PR #1](https://github.com/jordymg/9-NEKKO/pull/1) | 0005, 0006 |
| 2026-07-19 (2) | Claude Code | Vertical slice end-to-end: control group, duration segments, incremental persistence, patient retries; found + fixed `interval=max` empty-history API caveat (documented); run Jun→Jul: 2,186 snapshots into `nekko.sqlite`; first GROSS bias table — confounded by temporal clustering, NOT validated | — |
| 2026-07-19 (3) | Claude Code | Convention check 6/6 (API-VERIFICATION §4); sub-day enumeration fix + stratified sampling; 4-month run (710 markets, 2,640 snapshots): biases did NOT survive decorrelation → no Thesis A candidate, A/B evidence weak-to-null (`docs/results/f1-gross-2026-07-19.md`); pivot to F2 per pre-agreed decision logic | — |
| 2026-07-19 (4) | Claude Code + Jordi | F2 collector + status panel built and live-verified; data hygiene (test fence, resolution sources); deploy prep (systemd unit, SSH key, README ops). Oracle Cloud account + VCN/subnet/IGW/route built by hand; instance blocked by A1 "Out of capacity" → retry mañana. Local collector stopped on purpose; 14-day clock starts on VPS | 0007 |
