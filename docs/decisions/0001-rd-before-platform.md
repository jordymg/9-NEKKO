# ADR-0001: R&D project before trading platform

**Date:** 2026-07-12
**Status:** Accepted

## Context
Original spec described a full automated +EV trading system (9-layer architecture); a later
proposal expanded it to a "Trading OS" with 13 engines and a plugin system. Neither is
justified until the core financial hypothesis — an exploitable, repeatable edge exists on
Polymarket — is proven.

## Decision
The project is structured as R&D with validation gates (Phases 0–4). The software's goal is
to prove or refute a quantitative hypothesis, not to "have a bot running". No execution
infrastructure is built before Phase 0's thesis gate passes.

## Alternatives considered
- Build the full Trading OS first — rejected: classic quant failure mode; months of infrastructure for a strategy with no proven statistical advantage.
- Build a quick monolithic bot and iterate — rejected: couples everything to Polymarket and to one strategy; also skips edge validation.

## Consequences
Enables killing the project cheaply (kill date 2026-08-12). Constrains Phase 0 to
measurement-only software. Accepted tradeoff: if the edge is real, live trading starts later
than a "just build the bot" approach.
