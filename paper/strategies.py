"""Reglas plugin del paper engine — TODAS DRAFT (ADR-0008).

Escritas antes de tener una tesis validada: sus KPIs no valen para ningún gate.
Interfaz: objeto con `.name` y `.on_snapshot(snap, ctx) -> list[Signal]`.
Parámetros SIEMPRE desde config (ctx.params), nunca hardcodeados.
"""
from __future__ import annotations

from paper.engine import Context, Signal, Snap


def _prev_in_window(ctx: Context, snap: Snap, lo_s: float, hi_s: float) -> Snap | None:
    """Snapshot previo más viejo dentro de [lo_s, hi_s] segundos atrás."""
    lo_ms, hi_ms = lo_s * 1000, hi_s * 1000
    for old in ctx.history:  # ts ascendente: el primero que cae en ventana es el más viejo
        age = snap.ts - old.ts
        if lo_ms <= age <= hi_ms:
            return old
    return None


def _model_side(snap: Snap, edge_min: float) -> tuple[str, float] | None:
    """Lado que favorece el modelo si el gap contra el precio de entrada supera edge_min."""
    if snap.model_prob is None or snap.bid is None or snap.ask is None:
        return None
    edge_yes = snap.model_prob - snap.ask
    edge_no = (1.0 - snap.model_prob) - (1.0 - snap.bid)
    side, edge = ("yes", edge_yes) if edge_yes >= edge_no else ("no", edge_no)
    return (side, edge) if edge >= edge_min else None


class DraftThesisC:
    """Reversión por shock de liquidez: Binance se movió fuerte, el libro de
    Polymarket quedó quieto → el modelo se despegó del precio → tomar el lado
    del modelo y salir cuando converge (o por max_hold_s, que aplica el engine).
    """
    name = "draft_thesis_C"

    def on_snapshot(self, snap: Snap, ctx: Context) -> list[Signal]:
        p = ctx.params
        signals: list[Signal] = []
        # salidas por convergencia
        for pos in ctx.open_positions:
            if snap.mid is not None and snap.model_prob is not None \
                    and abs(snap.model_prob - snap.mid) <= p["exit_eps"]:
                signals.append(Signal("close", position_id=pos.position_id,
                                      reason="convergencia"))
        if ctx.open_positions:
            return signals
        # entrada: spot movido + mid quieto + gap de modelo
        prev = _prev_in_window(ctx, snap, p["lookback_s_min"], p["lookback_s_max"])
        if prev is None or prev.ref_spot in (None, 0) or snap.ref_spot is None \
                or prev.mid is None or snap.mid is None:
            return signals
        spot_move = abs(snap.ref_spot / prev.ref_spot - 1) * 100
        mid_move = abs(snap.mid - prev.mid)
        if spot_move >= p["spot_move_pct"] and mid_move <= p["stale_mid_eps"]:
            pick = _model_side(snap, p["edge_min"])
            if pick:
                side, edge = pick
                signals.append(Signal(
                    "open", side=side,
                    reason=f"spot {spot_move:.2f}% / mid quieto {mid_move:.4f} / edge {edge:.3f}"))
        return signals


class DraftThesisD:
    """Seguir la latencia: ante movimiento fuerte del spot, entrar de inmediato
    del lado que el modelo favorece; salida por tiempo fijo (hold_s, engine).
    """
    name = "draft_thesis_D"

    def on_snapshot(self, snap: Snap, ctx: Context) -> list[Signal]:
        p = ctx.params
        if ctx.open_positions or not ctx.history:
            return []
        prev = ctx.history[-1]
        if prev.ref_spot in (None, 0) or snap.ref_spot is None:
            return []
        spot_move = abs(snap.ref_spot / prev.ref_spot - 1) * 100
        if spot_move < p["spot_move_pct"]:
            return []
        pick = _model_side(snap, p["edge_min"])
        if pick is None:
            return []
        side, edge = pick
        return [Signal("open", side=side,
                       reason=f"spot {spot_move:.2f}% seguido / edge {edge:.3f}")]


ALL = [DraftThesisC(), DraftThesisD()]
