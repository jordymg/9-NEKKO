# Architecture — NEKKO

> AI agents: HOW we build. Stack choices here are settled — see /decisions for rationale. Propose changes as new ADRs, don't silently deviate.

## 1. Stack
| Layer | Choice | ADR |
|-------|--------|-----|
| Language | Python 3.11+ | 0002 |
| Storage | SQLite (append-only tables) | 0002 |
| Data sources | Polymarket Gamma API + CLOB API; Binance REST/WebSocket | 0002 |
| Analysis | pandas + notebook/scripts | 0002 |
| Hosting | Local (Windows) for Phase 0; collector can move to a VPS if uptime suffers | 0002 |
| Execution / wallets | **None in Phase 0** | 0001 |

## 2. System overview (Phase 0)
```
/nekko
  /connectors        # thin, replaceable adapters
      binance.py
      polymarket.py
  /models
      probability_model.py   # lognormal baseline: spot + realized vol + TTE
  /collector
      live_collector.py      # F2: snapshot loop → SQLite
  /backtest
      historical.py          # F1: resolved markets → bias table
  /analysis
      metrics.py             # F3: edge stats, segments, net-of-cost
  /storage
      sqlite.py
  /config
      settings.yaml          # market filters, poll interval, fee model
```
Modular-minimal: platform-shaped interfaces (connectors are adapters, model is swappable)
but only the folders Phase 0 needs. Execution/risk/strategy folders get created **only if**
Phase 0 validates a thesis (ADR-0001, ADR-0002).

## 3. Data model
### snapshots
| Field | Type | Notes |
|-------|------|-------|
| id | int PK | |
| market_id / condition_id / token_id | text | Polymarket identifiers |
| ts | int | epoch ms |
| implied_bid / implied_ask / implied_mid | real | |
| spread | real | |
| depth_bid / depth_ask | real | USDC within N% of mid |
| volume_24h | real | |
| tte_hours | real | time to expiry |
| ref_spot | real | Binance spot at ts |
| ref_vol | real | realized vol at ts |
| model_prob | real | reference probability |

### resolutions
| Field | Type | Notes |
|-------|------|-------|
| market_id | text PK | |
| outcome | int | 0/1 |
| resolved_at | int | epoch ms |

Relations: snapshots N—1 resolutions (by market_id).

## 4. API surface
None. Phase 0 is scripts + SQLite. No server.

## 5. Environments & secrets
- Local: `python -m collector.live_collector` / `python -m backtest.historical`
- Phase 0 uses only **public read APIs — no keys, no wallet, no secrets in the repo**
- If keys ever become necessary: `.env`, never committed

## 6. Conventions
- Python, type hints, one module = one responsibility
- Connectors return normalized dicts — nothing outside `/connectors` knows API shapes
- All money-adjacent numbers net of costs; never report gross edge
- Every table append-only; analysis never mutates collected data
