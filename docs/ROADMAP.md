# Roadmap — NEKKO

> AI agents: work only on the CURRENT phase. Do not start future phases without an explicit instruction.

## Phase 0 — Edge Discovery (CURRENT) — kill date 2026-08-12
Goal: produce a data-backed falsifiable thesis, or kill the project.
- [ ] Verify Polymarket historical API fields (granularity, resolved markets, price history) — depends on: —
- [ ] Connector: Polymarket (read-only) — depends on: API verification
- [ ] Connector: Binance (spot, klines, realized vol) — depends on: —
- [ ] Reference probability model (lognormal baseline) — depends on: Binance connector
- [ ] F1 historical backtest → bias table over ≥1000 resolved markets — depends on: connectors + model
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
