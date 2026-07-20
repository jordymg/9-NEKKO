"""Motor detector + paper trading (ADR-0008) — modo SHADOW exclusivamente.

Lee snapshots (vista snapshots_valid), alimenta estrategias plugin, simula
fills contra el libro REGISTRADO y persiste operaciones virtuales en paper_ops.
No coloca órdenes en ningún lado; no existe camino de código hacia dinero real.

Supuestos de fill (deliberadamente conservadores, ver también config `paper:`):
  - Entrada/salida siempre TAKER: comprar YES paga el ask registrado; comprar
    NO paga (1 - bid del YES). Nunca asumimos fills pasivos.
  - Tamaño: min(stake_usdc, max_fill_fraction × profundidad visible del lado
    tomado dentro de ±5% del mid). Profundidad < min_depth_usdc → NO hay fill.
  - Spread registrado > max_spread → mercado intocable (sin fill).
  - Fee taker de Polymarket: fee_rate × p × (1-p) por share (ADR-0005).
  - Settle por resolución: shares × outcome, sin fee (el redeem es gratis).
KPIs: sobre posiciones CERRADAS, por estrategia: n, win rate, profit factor,
expectancy por operación, Sharpe por-operación (no anualizado), max drawdown.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field

from storage import sqlite as store

log = logging.getLogger("paper")

HISTORY_WINDOW_S = 1800  # historial por mercado que ven las estrategias


@dataclass
class Snap:
    """Snapshot normalizado que reciben las estrategias."""
    market_id: str
    token_id: str
    ts: int
    bid: float | None
    ask: float | None
    mid: float | None
    spread: float | None
    depth_bid: float | None
    depth_ask: float | None
    tte_hours: float | None
    ref_spot: float | None
    model_prob: float | None
    trigger: str


@dataclass
class Signal:
    action: str                    # 'open' | 'close'
    side: str | None = None        # open: 'yes' | 'no'
    position_id: str | None = None # close
    reason: str = ""


@dataclass
class Position:
    position_id: str
    strategy: str
    market_id: str
    token_id: str
    side: str
    shares: float
    entry_price: float
    entry_fee: float
    opened_ts: int


@dataclass
class Context:
    history: deque                 # Snaps previos del mercado (ts asc, sin el actual)
    open_positions: list[Position] # de ESTA estrategia en ESTE mercado
    params: dict


class Engine:
    def __init__(self, conn, settings: dict):
        self.conn = conn
        self.cfg = settings["paper"]
        self.fee_rate = settings["fees"]["taker_fee_rate_crypto"]
        self.strategies: list = []
        self.history: dict[str, deque] = defaultdict(deque)
        self.positions: dict[str, Position] = {}   # position_id -> Position
        self._load_open_positions()

    # ---------- estado ----------
    def _load_open_positions(self) -> None:
        rows = self.conn.execute("""
            SELECT o.ts, o.strategy, o.market_id, o.token_id, o.position_id,
                   o.side, o.shares, o.price, o.fee
            FROM paper_ops o WHERE o.action = 'open' AND NOT EXISTS (
                SELECT 1 FROM paper_ops c WHERE c.position_id = o.position_id
                  AND c.action IN ('close', 'settle'))
        """).fetchall()
        for ts, strat, mid, tok, pid, side, sh, px, fee in rows:
            self.positions[pid] = Position(pid, strat, mid, tok, side, sh, px, fee, ts)
        if rows:
            log.info("posiciones abiertas recuperadas: %d", len(rows))

    def _open_by(self, strategy: str, market_id: str | None = None) -> list[Position]:
        return [p for p in self.positions.values()
                if p.strategy == strategy and (market_id is None or p.market_id == market_id)]

    # ---------- fills ----------
    def _entry(self, snap: Snap, side: str) -> tuple[float, float, float] | None:
        """(precio, shares, fee) para abrir, o None si no hay fill honesto."""
        if snap.bid is None or snap.ask is None or snap.spread is None:
            return None
        if snap.spread > self.cfg["max_spread"]:
            return None
        if side == "yes":
            price, depth = snap.ask, snap.depth_ask
        else:
            price, depth = 1.0 - snap.bid, snap.depth_bid
        if price <= 0 or price >= 1 or depth is None or depth < self.cfg["min_depth_usdc"]:
            return None
        usdc = min(self.cfg["stake_usdc"], self.cfg["max_fill_fraction"] * depth)
        shares = usdc / price
        fee = self.fee_rate * price * (1 - price) * shares
        return price, shares, fee

    def _exit_price(self, snap: Snap, side: str) -> float | None:
        if snap.bid is None or snap.ask is None:
            return None
        price = snap.bid if side == "yes" else 1.0 - snap.ask
        return price if 0 < price < 1 else None

    # ---------- procesamiento ----------
    def process(self, upto_ts: int | None = None) -> int:
        """Procesa snapshots nuevos desde el cursor. Devuelve ops generadas."""
        cursor = int(store.get_state(self.conn, "paper_cursor_ts", "0"))
        rows = self.conn.execute("""
            SELECT market_id, token_id, ts, implied_bid, implied_ask, implied_mid,
                   spread, depth_bid, depth_ask, tte_hours, ref_spot, model_prob, trigger
            FROM snapshots_valid WHERE ts > ? ORDER BY ts ASC
        """, (cursor,)).fetchall()
        n_ops = 0
        last_ts = cursor
        for r in rows:
            snap = Snap(*r)
            if upto_ts and snap.ts > upto_ts:
                break
            n_ops += self._feed(snap)
            last_ts = max(last_ts, snap.ts)
        n_ops += self._settle_resolved()
        if last_ts != cursor:
            store.set_state(self.conn, "paper_cursor_ts", str(last_ts))
        return n_ops

    def _feed(self, snap: Snap) -> int:
        hist = self.history[snap.market_id]
        ops: list[dict] = []
        for strat in self.strategies:
            ctx = Context(history=hist,
                          open_positions=self._open_by(strat.name, snap.market_id),
                          params=self.cfg["strategies"][strat.name])
            try:
                signals = strat.on_snapshot(snap, ctx)
            except Exception:
                log.exception("estrategia %s fallo en snapshot", strat.name)
                continue
            for sig in signals:
                op = self._execute(strat.name, snap, sig)
                if op:
                    ops.extend(op)
        # timeout de posiciones viejas de este mercado (regla del engine, no del plugin)
        for p in list(self._market_positions(snap.market_id)):
            max_hold = self.cfg["strategies"][p.strategy].get("max_hold_s") \
                or self.cfg["strategies"][p.strategy].get("hold_s")
            if max_hold and snap.ts - p.opened_ts >= max_hold * 1000:
                closed = self._execute(p.strategy, snap,
                                       Signal("close", position_id=p.position_id,
                                              reason="max_hold"))
                if closed:
                    ops.extend(closed)
        if ops:
            store.insert_paper_ops(self.conn, ops)
        hist.append(snap)
        cutoff = snap.ts - HISTORY_WINDOW_S * 1000
        while hist and hist[0].ts < cutoff:
            hist.popleft()
        return len(ops)

    def _market_positions(self, market_id: str) -> list[Position]:
        return [p for p in self.positions.values() if p.market_id == market_id]

    def _execute(self, strategy: str, snap: Snap, sig: Signal) -> list[dict] | None:
        if sig.action == "open":
            if len(self._open_by(strategy)) >= self.cfg["max_open_per_strategy"]:
                return None
            if self._open_by(strategy, snap.market_id):
                return None  # una posición por mercado por estrategia
            fill = self._entry(snap, sig.side)
            if fill is None:
                return None
            price, shares, fee = fill
            pid = uuid.uuid4().hex[:12]
            self.positions[pid] = Position(pid, strategy, snap.market_id, snap.token_id,
                                           sig.side, shares, price, fee, snap.ts)
            return [{"ts": snap.ts, "strategy": strategy, "market_id": snap.market_id,
                     "token_id": snap.token_id, "position_id": pid, "action": "open",
                     "side": sig.side, "shares": shares, "price": price, "fee": fee,
                     "snapshot_ts": snap.ts, "reason": sig.reason}]
        if sig.action == "close":
            p = self.positions.get(sig.position_id)
            if p is None:
                return None
            price = self._exit_price(snap, p.side)
            if price is None:
                return None
            fee = self.fee_rate * price * (1 - price) * p.shares
            del self.positions[p.position_id]
            return [{"ts": snap.ts, "strategy": p.strategy, "market_id": p.market_id,
                     "token_id": p.token_id, "position_id": p.position_id,
                     "action": "close", "side": p.side, "shares": p.shares,
                     "price": price, "fee": fee, "snapshot_ts": snap.ts,
                     "reason": sig.reason}]
        return None

    def _settle_resolved(self) -> int:
        """Cierra por resolución las posiciones cuyos mercados ya resolvieron."""
        if not self.positions:
            return 0
        ops = []
        for p in list(self.positions.values()):
            row = self.conn.execute(
                "SELECT outcome FROM resolutions WHERE market_id = ? AND outcome IS NOT NULL",
                (p.market_id,)).fetchone()
            if row is None:
                continue
            outcome = row[0]
            win = outcome if p.side == "yes" else 1 - outcome
            ops.append({"ts": int(time.time() * 1000), "strategy": p.strategy,
                        "market_id": p.market_id, "token_id": p.token_id,
                        "position_id": p.position_id, "action": "settle",
                        "side": p.side, "shares": p.shares, "price": float(win),
                        "fee": 0.0, "snapshot_ts": None, "reason": f"resolved={outcome}"})
            del self.positions[p.position_id]
        if ops:
            store.insert_paper_ops(self.conn, ops)
        return len(ops)


def kpis(conn, strategy: str | None = None) -> dict[str, dict]:
    """KPIs por estrategia sobre posiciones cerradas. PnL por posición:
    shares×(precio_salida) - shares×(precio_entrada) - fees de ambas patas."""
    where = "WHERE strategy = ?" if strategy else ""
    args = (strategy,) if strategy else ()
    rows = conn.execute(f"""
        SELECT strategy, position_id, action, shares, price, fee
        FROM paper_ops {where} ORDER BY id ASC
    """, args).fetchall()
    open_leg: dict[str, tuple] = {}
    pnls: dict[str, list[float]] = defaultdict(list)
    n_open: dict[str, int] = defaultdict(int)
    for strat, pid, action, shares, price, fee in rows:
        if action == "open":
            open_leg[pid] = (strat, shares, price, fee)
            n_open[strat] += 1
        elif pid in open_leg:
            s, sh, px_in, fee_in = open_leg.pop(pid)
            n_open[s] -= 1
            pnls[s].append(sh * price - fee - sh * px_in - fee_in)
    out = {}
    for strat, pl in pnls.items():
        wins = [x for x in pl if x > 0]
        losses = [x for x in pl if x <= 0]
        mean = sum(pl) / len(pl)
        var = sum((x - mean) ** 2 for x in pl) / (len(pl) - 1) if len(pl) > 1 else 0.0
        cum = peak = dd = 0.0
        for x in pl:
            cum += x
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        out[strat] = {
            "n_cerradas": len(pl), "n_abiertas": n_open.get(strat, 0),
            "win_rate": len(wins) / len(pl),
            "pf": (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0
                  else float("inf") if wins else 0.0,
            "expectancy": mean,
            "sharpe_op": (mean / var ** 0.5) if var > 0 else 0.0,
            "max_dd": dd, "pnl_total": sum(pl),
        }
    for strat, n in n_open.items():
        if strat not in out and n > 0:
            out[strat] = {"n_cerradas": 0, "n_abiertas": n, "win_rate": 0.0, "pf": 0.0,
                          "expectancy": 0.0, "sharpe_op": 0.0, "max_dd": 0.0, "pnl_total": 0.0}
    return out
