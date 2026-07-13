# Validation — NEKKO

> This is an R&D project, not a SaaS. The "customer" is the market; validation = a proven edge.
> The gate below replaces the standard 4-question SaaS validation gate.

## Core hypothesis (to be refined into a falsifiable thesis in Phase 0)

Persistent mispricing exists in some subset of Polymarket's quantifiable markets, in sizes
too small or too capital-inefficient for large arbitrageurs to correct, but large enough to
be exploitable net of fees, slippage and operational cost.

## Candidate theses (Phase 0 evaluates these against data)

| ID | Thesis | Mechanism | Testable with historical data? |
|----|--------|-----------|-------------------------------|
| A | Retail flow bias | Users buy YES on news/emotion → systematic overpricing of certain outcomes | **Yes** — resolved markets vs. reference model |
| B | Locked capital | Funds can't immobilize capital until resolution → small inefficiencies persist (0.8–2%) | **Yes** — edge size vs. time-to-resolution |
| C | Liquidity shocks | Large orders move thin books; price stays misaligned for seconds/minutes | No — needs live order book collection |
| D | Latency | Binance reflects information seconds before Polymarket reprices | Partially — needs high-frequency timestamps |
| E | Microstructure | Mispositioned resting orders (near-arbitrage) | No — needs live order book collection |

## What is NOT a thesis
- "Polymarket is wrong" / "Binance has the right price" / "AI will find opportunities"

## Phase 0 gate (project kill/continue criterion)

The project continues past Phase 0 **only if** we can write a thesis of this form, backed by data:

> Inefficiency X exists because Y. It persists because Z. We measure it via A, B, C.
> Expected average edge: D%, **net of fees, slippage and operational cost.**

## Phase 2 → Phase 3 gate (paper trading → real money)

ALL of the following on ≥1000 simulated operations:
- Profit Factor > 1.2
- Sharpe Ratio > 1
- Max drawdown < 10%
- Positive expectancy net of fees + estimated slippage
- Consistent across walk-forward periods
- Not dependent on a single extraordinary event

## Kill date

**2026-08-12.** If no promising bias has appeared in the data by this date, the project is
archived without guilt. An R&D project without a kill date is an infinite hobby.
