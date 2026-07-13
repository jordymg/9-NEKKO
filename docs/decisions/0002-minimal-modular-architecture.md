# ADR-0002: Minimal modular architecture (vertical slice), Python + SQLite

**Date:** 2026-07-12
**Status:** Accepted

## Context
Two extremes were on the table: a monolithic bot (coupled, hard to evolve) and a Trading OS
(13 engines, premature). Phase 0 needs to move fast but leave clean seams for growth.

## Decision
Platform-shaped interfaces, minimal footprint: `/connectors`, `/models`, `/collector`,
`/backtest`, `/analysis`, `/storage`, `/config`. Python 3.11+, SQLite append-only, public
read-only APIs (Polymarket Gamma/CLOB, Binance). Connectors are thin adapters; nothing
outside them knows API shapes. New folders (execution, risk, strategies) are created only
when their phase begins.

## Alternatives considered
- Full Trading OS module tree from day one — rejected: premature (ADR-0001).
- Postgres / cloud infra — rejected: SQLite is enough for single-user append-only collection; zero ops.
- Node/TypeScript — rejected: Python has the quant ecosystem (pandas, scipy) Phase 0 analysis needs.

## Consequences
v1 is small enough to build within the kill window. Swapping the probability model or adding
an exchange later means adding a module, not a rewrite. Accepted tradeoff: SQLite may need
migration if data volume explodes (unlikely in Phase 0).
