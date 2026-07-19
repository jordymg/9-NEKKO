# ADR-0006: F1 v1 valúa solo binarias europeas; barrera después; Up/Down excluido

**Date:** 2026-07-19
**Status:** Accepted

## Context
Los mercados cripto resueltos de Polymarket se reparten en tres familias (dry-run de una
semana: 2.680 mercados): "Up or Down" de 5-15 min (~93%), barrera ("reach/dip/hit $K",
~3%) y binarias europeas ("above/below $K on FECHA", ~1%; el resto no parseable). El
baseline lognormal (ADR-0002/0003) valúa la europea con fórmula cerrada trivial; la
barrera exige probabilidad de primer cruce (más supuestos, más riesgo de modelo).

## Decision
El backtest F1 v1 valúa **solo binarias europeas** (BTC/ETH/SOL/XRP/DOGE). Los mercados de
barrera se cuentan pero no se valúan. Los "Up or Down" quedan fuera del análisis como grupo
de control (ya lo fijaba el PRD §6).

## Alternatives considered
- Implementar primer cruce para barrera ya — rechazado: duplica el riesgo de modelo justo
  donde los edges "fantasma" son más probables, y la kill date presiona por lo mínimo.
- Incluir los Up/Down en la tabla de sesgos — rechazado: PRD §6 los define como segmento
  probablemente más eficiente / grupo de control, no como objetivo.

## Consequences
Muestra por semana más chica (~30-100 mercados europeos); si la corrida ene→jul no llega a
n suficiente por segmento, la siguiente palanca es agregar la familia barrera (nueva
fórmula = nuevo ADR). Limitación conocida de la enumeración: en días inundados por Up/Down
(~2.800/día) la ventana de 1 día se trunca en ~1.500 filas y pueden perderse europeas —
fix pendiente (ventanas sub-día), anotado en STATUS.
