# Roadmap — NEKKO

> AI agents: work only on the CURRENT phase. Do not start future phases without an explicit instruction.

## Phase 0 — Edge Discovery (CURRENT) — kill date 2026-08-12
Goal: produce a data-backed falsifiable thesis, or kill the project.
- [x] Verify Polymarket historical API fields (granularity, resolved markets, price history) — done 2026-07-13, see [API-VERIFICATION.md](API-VERIFICATION.md)
- [x] Connector: Polymarket (read-only) — done 2026-07-18, [connectors/polymarket.py](../connectors/polymarket.py)
- [x] Connector: Binance (spot, klines, realized vol) — done 2026-07-18, [connectors/binance.py](../connectors/binance.py)
- [x] Reference probability model (lognormal baseline) — done 2026-07-19, [models/probability_model.py](../models/probability_model.py)
- [x] F1 historical backtest → bias table — done 2026-07-19 (GROSS): decorrelated 4-month stratified run, 710 markets / 2,640 snapshots, convention verified; results in [f1-gross-2026-07-19.md](results/f1-gross-2026-07-19.md). Note: <1000 markets in the clean run (390 euro + 320 control) — deemed sufficient because the finding is null and costs only strengthen it
- [~] Decision checkpoint: **A/B historical evidence weak-to-null** (biases were regime artifacts) → C/D/E need F2 live data; formal verdicts land in F3/THESIS.md
- [ ] F2 live collector running ≥14 days — **running on the VPS since 2026-07-20 ~14:31 UTC** (day 0 of ≥14; completes ~2026-08-03). Collector: [collector/live_collector.py](../collector/live_collector.py), panel: [analysis/status.py](../analysis/status.py), deploy: ADR-0007
- [ ] F3 analysis → THESIS.md or KILL.md — depends on: F1 + F2

Exit criterion: THESIS.md (VALIDATION.md format, ≥300 supporting observations, edge net of costs) or KILL.md exists.

## Phase 1+2 — Detector + Paper Trading (FUSED, ADR-0008 — construction started 2026-07-20 in parallel with F2)
Goal: one module (`/paper`) detects signals AND runs the full simulated loop (detect → virtual buy → virtual sell → KPIs). No orders, shadow only.
Status: engine live in shadow on the VPS with `draft_*` rules. **Epistemic guard: KPIs from draft rules are NOT gate-valid; the gate requires rules derived from a data-backed thesis (F3).**
Exit criterion (unchanged from old Phase 2): 1000 simulated operations with thesis-derived rules; Phase 2 → 3 gate in VALIDATION.md passes.

## Phase 3 — Minimum capital (USD 100)
Goal: validate execution reality — slippage, fills, latency, model degradation.
Exit criterion: live metrics within tolerance of paper metrics.

## Phase 4 — Scaling
More markets, more strategies, risk/portfolio engines. Only here does the "platform" grow.

## Later / icebox
Everything in PRD §6: execution engine, risk engine, dashboards, other exchanges (Kalshi/Deribit/dYdX...), LLM probability models, strategy plugin system, Trading OS vision.
