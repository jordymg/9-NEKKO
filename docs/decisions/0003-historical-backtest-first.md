# ADR-0003: Historical backtest before live collection

**Date:** 2026-07-12
**Status:** Accepted

## Context
Original Phase 0 plan was weeks of live data collection before any thesis test. Polymarket
exposes historical data (resolved markets, price history) via public APIs/subgraph, which
can test theses A (retail bias) and B (locked capital) retroactively over thousands of
markets in days.

## Decision
Phase 0 runs two tracks: (1) historical backtest FIRST — cheap, fast, can kill or prioritize
theses within roughly a week; (2) live collector in parallel, only for what history can't
reconstruct (order book depth, fine latency → theses C, D, E).

## Alternatives considered
- Live collection only — rejected: weeks of waiting for answers history already contains.
- Historical only — rejected: microstructure/latency theses need live book snapshots.

## Consequences
Fast kill signal: if history shows no bias anywhere, that's strong evidence before the
collector is even finished. Constraint: first task is verifying the historical API actually
has the needed granularity (PRD risk #1).
