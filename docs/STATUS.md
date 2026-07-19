# Status — NEKKO

> AI agents: read this FIRST. It's the live state of the project. Update it at the end of every session (see session-close prompt).

**Last updated:** 2026-07-19 (session 3) — Decorrelated 4-month resample done: **the apparent biases did not survive** (both were regime artifacts; per-month tables in `docs/results/f1-gross-2026-07-19.md`). Historical GROSS evidence for theses A/B: **weak-to-null**. Pivot to F2 live collector — time-critical (needs ≥14 days uptime before kill date 2026-08-12).
**Current phase:** Phase 0 — Edge Discovery (kill date **2026-08-12**)

## Done (recent)
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

## Next up — F2 live collector (theses C/D/E need what history cannot provide)
Rationale: historical GROSS evidence for A/B is weak-to-null (`docs/results/f1-gross-2026-07-19.md`; gross ≈ 0 in liquid segments ⇒ net < 0 after ADR-0005 costs, no NET re-run needed to conclude weakness). Theses C/D/E require order-book depth and fine timestamps — live-only data.
1. **Build + launch F2 collector (`collector/live_collector.py`) — TIME-CRITICAL**: PRD requires ≥14 consecutive days on ≥50 active markets before kill date 2026-08-12 ⇒ collector must be running unattended by **~2026-07-28**. Poll interval + Binance-move-triggered snapshots per PRD F2; schema `snapshots` per ARCHITECTURE §3; reuse `get_order_book` (already live-tested).
2. While it collects: F3 analysis groundwork over `nekko.sqlite` (formal thesis verdicts supported/rejected/insufficient in VALIDATION.md format — A/B verdicts can largely be written from the F1 evidence).
3. Icebox (only if a thesis needs it): barrier-market family (ADR-0006 lever); low-liquidity euro residual (−8.5pt, underpowered, correlated snapshots — needs more months of data, not a candidate).

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
