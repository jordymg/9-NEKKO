# ADR-0005: Modelo de costos — fee oficial verificada + spread asumido medido en vivo

**Date:** 2026-07-18
**Status:** Accepted

## Context
El PRD prohíbe reportar edge bruto, pero el historial de Polymarket no conserva bid/ask ni
profundidad (el libro es live-only, ver `docs/API-VERIFICATION.md`). El costo de ejecución
histórico es inobservable y debe asumirse; una suposición mal elegida invalida todo F1.

## Decision
Fijado en `config/settings.yaml` (fuente y fecha en cada número):
- **Fee**: taker cripto `fee = shares × 0.07 × p × (1−p)` según docs oficiales de Polymarket
  (verificado 2026-07-18); makers pagan 0. Se aplica el esquema ACTUAL también a mercados
  anteriores a la introducción de fees (fines de 2025), porque la pregunta es si la ventaja
  sería explotable HOY.
- **Spread**: asumido `0.02` (escenario base) y `0.01` (optimista, solo sensibilidad),
  basado en muestreo en vivo 2026-07-18 de 42 libros cripto activos con mid en [0.05, 0.95]:
  mediana 0.01, p75 0.02, estable entre bandas de volumen.
- **Convención de ejecución**: la serie histórica se trata como mid; entrada taker a
  mid + spread/2.

## Alternatives considered
- Asumir fee cero — rechazado: las fees existen desde fines de 2025 y en p=0.50 son ~1.75%
  del notional; ignorarlas infla el edge.
- Elegir el spread "a ojo" — rechazado: medible en vivo hoy con el conector; se midió.
- Modelar fills maker (sin fee, sin cruzar spread) — rechazado para F1: supone ejecución
  pasiva garantizada, que es exactamente el tipo de optimismo que el PRD quiere evitar.

## Consequences
Umbral concreto de explotabilidad: comprando a 0.50 y aguantando a resolución, el costo
total es ~2.75c/share — cualquier "edge" menor es ruido no operable. Riesgo aceptado: el
spread de hoy puede no representar el histórico; se mitiga con el escenario optimista y,
más adelante, con los spreads reales que junte el colector F2.
