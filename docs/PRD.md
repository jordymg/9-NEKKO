# PRD — NEKKO (Phase 0: Edge Discovery Engine)

> AI agents: this is the source of truth for WHAT we're building and WHY. Read ARCHITECTURE.md for HOW, STATUS.md for current state, /decisions for settled choices. Do not re-open decisions recorded in /decisions.

## 1. Problem
Jordi wants to build an automated +EV trading system for Polymarket, but the foundational
hypothesis — *that an exploitable, repeatable edge exists* — is unproven. Building trading
infrastructure before proving the edge is the classic quant failure mode: months of
platform work for a strategy with no statistical advantage. Today there is no data-backed
answer to "where, if anywhere, is Polymarket systematically mispriced?"

## 2. Solution in one sentence
An **Edge Discovery Engine** that measures the gap between Polymarket implied probabilities
and a reference probability model across many markets, producing a data-backed, falsifiable
thesis (or a justified project kill).

**It does not trade. It does not place orders. It only measures.**

## 3. Success metric
By **2026-08-12**: either (a) a written thesis per the VALIDATION.md format, supported by
≥300 observations showing positive edge net of estimated costs, or (b) a documented kill
decision. Both outcomes count as success — the failure mode is neither.

## 4. Users & roles
| Role | Description | Key need |
|------|-------------|----------|
| Jordi (researcher) | Sole user | Query collected data, see edge statistics per market segment |

## 5. MVP features

### F1 — Historical backtest track
- **Why:** Theses A and B are testable against already-resolved markets — days of work instead of weeks of live collection. Cheapest possible kill/prioritize signal (§1).
- **Acceptance criteria:**
  - [ ] Fetches resolved Polymarket crypto/macro markets via public API (Gamma API / subgraph): price history, volume, resolution outcome
  - [ ] Reconstructs a reference probability at multiple points in each market's life (spot + realized vol + time-to-expiry, lognormal baseline)
  - [ ] Outputs per-segment bias table: implied prob vs. reference prob vs. actual outcome frequency, segmented by time-to-expiry, liquidity band, asset
  - [ ] Includes fee model (Polymarket fees + estimated spread cost) so reported edge is NET

### F2 — Live collector
- **Why:** Theses C, D, E need order book depth and fine timestamps that historical data doesn't preserve.
- **Acceptance criteria:**
  - [ ] Polls active quantifiable markets on a fixed interval; also snapshots on Binance price moves > threshold
  - [ ] Stores per snapshot: market id, timestamp, implied prob (bid/ask/mid), spread, book depth, volume, time-to-expiry, Binance spot/vol at same timestamp, and later the resolution outcome
  - [ ] Runs unattended ≥7 days without data loss (SQLite, append-only)
  - [ ] Recovers from API errors/rate limits without crashing (retry + backoff)

### F3 — Analysis notebook
- **Why:** The deliverable of Phase 0 is a thesis, which requires analyzing collected data.
- **Acceptance criteria:**
  - [ ] Reproducible script/notebook computing: mean edge, hit rate, edge by segment, edge net of costs, sample sizes
  - [ ] Can answer "is segment S mispriced by ≥X% with N≥300 observations?" directly

## 6. Explicitly OUT of scope (Phase 0)
- Order execution, wallets, keys, allowances — nothing touches money
- Strategy engine, risk engine, position sizing (Kelly etc.)
- Backtesting engine for strategies (only *bias measurement* here)
- Dashboard / UI — SQLite + scripts is enough
- More exchanges (Kalshi, Deribit, etc.) — connector interfaces allow it later
- AI/LLM probability models — baseline statistical model first
- BTC ">X on Friday" high-liquidity markets as primary target — likely most efficient segment; included in data collection only as a control group

## 7. Definition of DONE (Phase 0)
- [ ] Historical backtest ran over ≥1000 resolved markets, bias table produced
- [ ] Live collector ran ≥14 consecutive days on ≥50 active markets
- [ ] Analysis answers each thesis A–E with: supported / rejected / insufficient data
- [ ] THESIS.md written in the VALIDATION.md format, or KILL.md documenting why the project stops
- [ ] STATUS.md reflects the outcome

## 8. Risks & open questions
| Risk / question | Impact | Plan |
|-----------------|--------|------|
| Historical API lacks needed granularity | F1 weakens, more weight on live collection | Verify API fields in first session before building |
| Reference model is itself wrong → phantom edges | False positive thesis | Sanity-check model vs. Deribit implied vol where available; large edges are treated as model-error suspects first |
| Fees/spread eat all measured edge | Kill signal | Fee model built into F1/F3 from day one — never report gross edge |
| Time competes with Mc Fly / NEXO | Project stalls silently | Hard kill date 2026-08-12 (ADR-0004) |
| Polymarket API rate limits / changes | Collector gaps | Retry policy + gap logging; gaps flagged in analysis |

## 9. Grade
**B (7/8)** — 2026-07-12. Gap: weekly time budget not defined (constraint exists only as kill date). See STATUS.md open item.
