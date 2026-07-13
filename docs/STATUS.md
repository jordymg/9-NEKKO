# Status — NEKKO

> AI agents: read this FIRST. It's the live state of the project. Update it at the end of every session (see session-close prompt).

**Last updated:** 2026-07-12 — Kickoff: theses defined, docs generated, Phase 0 scoped, kill date set.
**Current phase:** Phase 0 — Edge Discovery (kill date **2026-08-12**)

## Done (recent)
- 2026-07-12 Project renamed QUANT-EDGE → NEKKO (pre-commit, no history impact)
- 2026-07-12 Kickoff complete: VALIDATION.md (5 candidate theses + gates), PRD (graded B), architecture, roadmap, 4 ADRs

## Next up
1. Verify Polymarket public API (Gamma / CLOB / subgraph): can we get resolved markets with price history and resolution outcomes at usable granularity? This determines how strong the F1 historical track can be. **Do this before writing any other code.**
2. Build read-only Polymarket + Binance connectors
3. Lognormal reference model → run F1 historical backtest

## Blocked / waiting
- Weekly time budget undefined (only the kill date constrains scope) — Jordi to define
- Open from PRD: fee model parameters (Polymarket fee schedule + spread assumption) need to be pinned in config

## Session log
| Date | Tool used | What happened | Decisions made (→ ADR#) |
|------|-----------|---------------|-------------------------|
| 2026-07-12 | Claude (chat) | Kickoff: spec reviewed, Trading OS descoped to R&D project, theses A–E defined, docs generated | 0001, 0002, 0003, 0004 |
