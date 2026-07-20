# Polymarket API verification — 2026-07-13

> Result of STATUS.md "Next up #1". Verified live against public endpoints on 2026-07-13.
> **Verdict: GO for F1.** Resolved markets, resolution outcomes, and price history are all
> available at usable granularity via public read-only APIs. No keys needed.

## 1. Gamma API — market metadata + resolutions

Base: `https://gamma-api.polymarket.com`

### `GET /markets` — the workhorse
Useful params (all verified): `closed=true`, `active`, `tag_id`, `limit` (**max 100/page**),
`offset`, `order` + `ascending`, `volume_num_min`, `end_date_min` / `end_date_max`, `slug`.

Fields we need, all present per market:
| Need | Field | Notes |
|------|-------|-------|
| Identifiers | `id`, `conditionId`, `clobTokenIds` | `clobTokenIds` is a JSON-encoded string array `[yesToken, noToken]` |
| Resolution outcome | `outcomePrices` | JSON-encoded string, e.g. `["0", "1"]` = second outcome won. Populated on resolved markets |
| Lifecycle | `createdAt`, `startDate`, `endDate`, `closedTime` | `closedTime` ≈ resolution time |
| Volume/liquidity | `volumeNum`, `volume24hr`, `liquidityNum` | occasionally `None` on tiny markets |
| Classification | `tag_id` filter, `question`, `slug`, `events` | |

### Tags (verified by slug lookup `GET /tags/slug/{slug}`)
- `21` = Crypto, `235` = Bitcoin. Macro tags exist (`102000` macro-indicators etc.).

### Pagination caveat (important)
Plain `offset` paging stops returning data at **offset ≈ 2,100** for `closed=true&tag_id=21`
(returns a residual 2 rows beyond that). This is an API cap, not the true total.
**Workaround (verified):** window by `end_date_min`/`end_date_max` and page within each
window. This is how the connector must enumerate ≥1000 resolved markets.

## 2. CLOB API — price history + order book

Base: `https://clob.polymarket.com`

### `GET /prices-history?market={clobTokenId}`
- **CAVEAT (found 2026-07-19)**: `interval=max` returns an EMPTY history for older
  resolved markets (observed on early-June markets queried mid-July) while explicit
  `startTs/endTs` windows still return full data for the same token. Always use
  explicit windows for historical work. Responses also truncate at **~1,000 points**
  — pick fidelity so the window stays under that.
- `interval=max&fidelity=10` → full market life at **~10-minute steps** (verified: 552
  points spanning a 4-day market, first point ~23 min after market creation) — but see
  caveat above: only reliable for recently-closed markets.
- `fidelity=1` with `interval=max` is silently floored to ~10-min steps.
- **1-minute granularity works with explicit windows:** `startTs={epoch}&endTs={epoch}&fidelity=1`
  → verified 60-second steps. So fine granularity = iterate windows.
- Point format: `{"t": epochSeconds, "p": price}`. Price = last/mid in [0,1].

### `GET /book?token_id={clobTokenId}` (for F2 live collector)
Returns `bids`/`asks` arrays of `{price, size}`, ms `timestamp`, `tick_size`,
`min_order_size`, `neg_risk`, `last_trade_price`. Verified on an active market.
Book is **live-only** — depth is not preserved historically, confirming ADR-0003's
split (theses C/D/E need the live collector).

## 3. Implications for F1

- ≥1000 resolved crypto markets: **feasible** — ~2,100 reachable via offset alone on tag 21;
  date-windowing unlocks the rest. Note the population is heavily diluted by 5-minute
  "Bitcoin Up or Down" markets (thousands; treat as the control group per PRD §6, or filter
  by question pattern / duration).
- Reference-model inputs per snapshot (implied prob at time t, TTE) are reconstructable from
  `prices-history` + `endDate`.
- What history does NOT give: bid/ask spread and depth (book is live-only). F1's fee model
  must therefore **assume** a spread cost — pin it in `config/settings.yaml` (open item in
  STATUS.md stands).
- Rate limits: not hit during verification (~30 requests). Unknown ceiling — connector still
  needs retry + backoff per PRD F2.

## 4. Up/Down outcome-convention verification (2026-07-19, session 3)

Manual check of the `control_updown` outcome parsing (`outcome=1` ⇔ first outcome "Up"
won ⇔ price rose over the market window). Method: `eventStartTime`→`endDate` window from
Gamma, Binance BTCUSDT 1m klines over that window, direction = close(last candle) ≥
open(first candle), compared against stored outcome. **Result: 6/6 MATCH — convention
verified, prior bias signs are valid.**

| market_id | window (UTC) | Binance Δ | dir | stored |
|-----------|--------------|-----------|-----|--------|
| 2399127 | 2026-06-01 01:50–01:55 | −193.74 | 0 | 0 ✓ |
| 2399200 | 2026-06-01 02:00–02:05 | +77.09 | 1 | 1 ✓ |
| 2398870 | 2026-06-01 00:30–00:35 | −42.57 | 0 | 0 ✓ |
| 2399110 | 2026-06-01 01:45–01:50 | +65.73 | 1 | 1 ✓ |
| 2399032 | 2026-06-01 01:20–01:25 | +1.50 | 1 | 1 ✓ |
| 2399095 | 2026-06-01 01:35–01:40 | −12.09 | 0 | 0 ✓ |

Notes: (a) official resolution source is the **Chainlink BTC/USD data stream**, not
Binance — Binance direction agreed 6/6 anyway, incl. clear moves; borderline ties
(rule: "Up" if end ≥ start) could still diverge between sources. (b) `eventStartTime`
field on Gamma markets gives the window open directly — no need to parse question text.

## 5. Binance desde IP de EE.UU. (found 2026-07-20, deploy VPS)
`api.binance.com` responde **HTTP 451** (geo-block) desde la IP de Oracle Phoenix.
El mirror oficial de market data **`data-api.binance.vision`** sirve los mismos
endpoints públicos (`/api/v3/ping`, `/ticker/price`, `/klines`) sin bloqueo —
verificado desde el VPS. El conector usa la env var `NEKKO_BINANCE_BASE` (seteada
en el unit de systemd); local sigue en `api.binance.com`.

## 6. Not verified (deliberately)
- Binance REST/klines — well-documented public API, no verification needed before use.
- Polymarket subgraph — not needed; Gamma + CLOB cover F1's requirements.
