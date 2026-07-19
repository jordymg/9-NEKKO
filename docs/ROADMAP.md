# Roadmap — NEKKO

> AI agents: work only on the CURRENT phase. Do not start future phases without an explicit instruction.

## Phase 0 — Edge Discovery (CURRENT) — kill date 2026-08-12
Goal: produce a data-backed falsifiable thesis, or kill the project.
- [x] Verify Polymarket historical API fields (granularity, resolved markets, price history) — done 2026-07-13, see [API-VERIFICATION.md](API-VERIFICATION.md)
- [x] Connector: Polymarket (read-only) — done 2026-07-18, [connectors/polymarket.py](../connectors/polymarket.py)
- [x] Connector: Binance (spot, klines, realized vol) — done 2026-07-18, [connectors/binance.py](../connectors/binance.py)
- [x] Reference probability model (lognormal baseline) — done 2026-07-19, [models/probability_model.py](../models/probability_model.py)
- [ ] F1 historical backtest → bias table over ≥1000 resolved markets — pipeline runs end-to-end ([backtest/historical.py](../backtest/historical.py), 2,186 snapshots, GROSS table); pending: decorrelated multi-month resample + Up/Down convention check before any conclusion; scope v1 = European binaries + Up/Down control (ADR-0006)
- [ ] Decision checkpoint: which theses survive the historical test? — depends on: F1
- [ ] F2 live collector running ≥14 days — depends on: connectors (can start in parallel with F1 analysis)
- [ ] F3 analysis → THESIS.md or KILL.md — depends on: F1 + F2

Exit criterion: THESIS.md (VALIDATION.md format, ≥300 supporting observations, edge net of costs) or KILL.md exists.

## Phase 1 — Detector
Goal: the thesis strategy computes edges in real time and logs would-be trades. No orders.
Exit criterion: N weeks of logged opportunities; realized outcomes match predicted edge within tolerance.

## Phase 2 — Paper Trading
Goal: full simulated loop (detect → virtual buy → virtual sell → KPIs), 1000 operations.
Exit criterion: Phase 2 → 3 gate in VALIDATION.md passes.

## Phase 3 — Minimum capital (USD 100)
Goal: validate execution reality — slippage, fills, latency, model degradation.
Exit criterion: live metrics within tolerance of paper metrics.

## Phase 4 — Scaling
More markets, more strategies, risk/portfolio engines. Only here does the "platform" grow.

## Later / icebox
Everything in PRD §6: execution engine, risk engine, dashboards, other exchanges (Kalshi/Deribit/dYdX...), LLM probability models, strategy plugin system, Trading OS vision.
