# Status — NEKKO

> AI agents: read this FIRST. It's the live state of the project. Update it at the end of every session (see session-close prompt).

**Last updated:** 2026-07-19 (night) — Vertical slice ran **end-to-end for the first time**: 2,186 snapshots (350 euro + 120 control) persisted in `nekko.sqlite`; first bias table produced — **GROSS/exploratory, NOT validated** (sample temporally clustered). Next session has a single goal: decorrelated resample + convention check (see Next up).
**Current phase:** Phase 0 — Edge Discovery (kill date **2026-08-12**)

## Done (recent)
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

## Next up — SINGLE GOAL: "Decorrelated resample + convention check"
1. **MANDATORY FIRST STEP (blocks everything else)**: manually verify the Up/Down outcome-parsing convention on 2-3 resolved `control_updown` markets. For each: pull the market's window open/close timestamps, fetch Binance BTCUSDT 1m klines for that window, compute actual direction, compare against the stored `outcome`. If mismatch → the convention bug inverts bias signs across ALL tables; fix parser, invalidate prior control stats, document in `docs/API-VERIFICATION.md`. If match → record the verification (market ids + timestamps) in `docs/API-VERIFICATION.md`.
2. Fix date-window enumeration (known truncation bug: 1-day windows cap at ~1,500 rows on days flooded by ~2,800 Up/Down markets — try sub-day windows / datetime params). Windows must yield complete coverage. Then resample across **≥4 distinct calendar months** (e.g., Mar/Apr/May/Jun 2026), stratified so no single week dominates. Target: ~300-500 euro binaries + ≥300 `control_updown` snapshots spread across months.
3. Preserve the rationale in analysis code comments: the current sample is temporally clustered (single week of June) → outcomes correlated via market regime; both the +22pt euro bias and the +9pt control bias are confounded by regime drift. Control markets are independent of each other but NOT of the sampling period. Multi-month sampling is the decorrelation fix.
4. Re-run bias tables (still GROSS mode, keep exploratory labeling). Report control calibration **per month** as well as pooled — if the +9pt control bias survives multi-month sampling AND verified convention, flag it as the first real Thesis A candidate (still pre-fees).
5. Standard session close (STATUS, ROADMAP ticks with doc links, BITACORA in plain Spanish, ADR only for real alternative-choice decisions). Commit + push.

## Blocked / waiting
- Weekly time budget undefined (only the kill date constrains scope) — Jordi to define

## Session log
| Date | Tool used | What happened | Decisions made (→ ADR#) |
|------|-----------|---------------|-------------------------|
| 2026-07-12 | Claude (chat) | Kickoff: spec reviewed, Trading OS descoped to R&D project, theses A–E defined, docs generated | 0001, 0002, 0003, 0004 |
| 2026-07-13 | Claude Code | Verified Polymarket Gamma + CLOB APIs live: GO for F1. Wrote `docs/API-VERIFICATION.md` (fields, granularity, pagination workaround, caveats). No new ADRs — findings, not decisions | — |
| 2026-07-18/19 | Claude Code | Built + live-tested both connectors; pinned cost model (fee verified, spread measured); built lognormal model, SQLite storage, F1 backtest pipeline; dry-run sane; full Jan→Jul run launched (in progress at close); opened [PR #1](https://github.com/jordymg/9-NEKKO/pull/1) | 0005, 0006 |
| 2026-07-19 (2) | Claude Code | Vertical slice end-to-end: control group, duration segments, incremental persistence, patient retries; found + fixed `interval=max` empty-history API caveat (documented); run Jun→Jul: 2,186 snapshots into `nekko.sqlite`; first GROSS bias table — confounded by temporal clustering, NOT validated | — |
