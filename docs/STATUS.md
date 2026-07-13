# Status — NEKKO

> AI agents: read this FIRST. It's the live state of the project. Update it at the end of every session (see session-close prompt).

**Last updated:** 2026-07-13 — Polymarket API verification complete: **GO for F1**. Findings in `docs/API-VERIFICATION.md`.
**Current phase:** Phase 0 — Edge Discovery (kill date **2026-08-12**)

## Done (recent)
- 2026-07-13 Polymarket API verified (GO): resolved markets + outcomes via Gamma, price history via CLOB (10-min full-life, 1-min with windowed `startTs/endTs`), order book live-only. Full findings + caveats in `docs/API-VERIFICATION.md`
- 2026-07-12 Project renamed QUANT-EDGE → NEKKO (pre-commit, no history impact)
- 2026-07-12 Kickoff complete: VALIDATION.md (5 candidate theses + gates), PRD (graded B), architecture, roadmap, 4 ADRs

## Next up
1. Build read-only Polymarket connector (`connectors/polymarket.py`). Shape is fully determined by `docs/API-VERIFICATION.md`: enumerate resolved markets via Gamma `/markets` with `end_date_min/max` windows (plain offset paging caps at ~2,100 rows), pull price history via CLOB `/prices-history`. Filter/segment out the 5-minute "Up or Down" markets (control group per PRD §6) so they don't dominate the sample.
2. Build read-only Binance connector (spot, klines, realized vol) — independent, can be done in either order.
3. Pin fee model params in `config/settings.yaml` — **historical data has no spread/depth** (book is live-only), so F1 must use an assumed spread cost; net-edge reporting is blocked on this.
4. Lognormal reference model → run F1 historical backtest.

## Blocked / waiting
- Weekly time budget undefined (only the kill date constrains scope) — Jordi to define
- Fee model parameters (Polymarket fee schedule + **assumed** spread cost — API verification confirmed spread is not reconstructable from history) — needs Jordi's sign-off on the assumption before F1 reports net edge

## Session log
| Date | Tool used | What happened | Decisions made (→ ADR#) |
|------|-----------|---------------|-------------------------|
| 2026-07-12 | Claude (chat) | Kickoff: spec reviewed, Trading OS descoped to R&D project, theses A–E defined, docs generated | 0001, 0002, 0003, 0004 |
| 2026-07-13 | Claude Code | Verified Polymarket Gamma + CLOB APIs live: GO for F1. Wrote `docs/API-VERIFICATION.md` (fields, granularity, pagination workaround, caveats). No new ADRs — findings, not decisions | — |
