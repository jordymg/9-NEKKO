# ADR-0009: Backfill one-shot de resoluciones vía Gamma (excepción aprobada al no-touch)

**Date:** 2026-07-26
**Status:** Accepted

## Context
El power check (s9) encontró un fallo silencioso: **0 resoluciones registradas** pese a
**157 mercados trackeados ya vencidos** (de 231 distintos). Sin outcomes, la data F2 no
sirve para medir edge. Diagnóstico read-only (s9):

- **Causa raíz del backfill vivo (compuesta):** el backfill de `refresh_universe` solo
  chequea, UNA vez, los mercados que salieron del universo en ese ciclo. Los mercados
  salen del universo top-80 mayormente por **churn de volumen/ranking mientras siguen
  activos** (no por resolverse) → al chequearlos `closed=False`/`outcome=None` → se
  descartan y **nunca se reintenta** (`self.universe = new`). Además, aun los que salen por
  vencimiento no están **UMA-final** en ese instante (lag de horas). No hay set persistente
  de "pendientes de resolución". El journal confirma: cero backfills exitosos y cero
  errores — la rama corre pero su condición nunca se cumple.
- **Recuperabilidad (recon):** 10/10 mercados de muestra resolvieron limpio vía Gamma
  `/markets/{market_id}` (el `market_id` guardado ES el id numérico de Gamma). Stale-safe
  indefinido (Gamma devuelve mercados resueltos de años atrás por id; el lookup directo no
  sufre el cap de paginación por offset).

## Decision
Implementar `analysis/backfill_resolutions.py`: lee `market_id` distintos de `snapshots`,
consulta Gamma `/markets/{id}` vía el connector (path probado, no urllib), parsea
`outcomePrices`+`closed` → outcome ∈ {0,1}; si aún no es UMA-final (`outcome=None`) lo
**loguea como pending y no escribe** (no es error). Escribe **additive** a `resolutions`
con `source='backfill'`, **idempotente** (`INSERT OR IGNORE`, `market_id` es PK). **Nunca**
escribe `snapshots` ni toca el proceso del colector. Fail-closed: si Gamma es inalcanzable,
loguea y sale ≠0 sin escritura parcial (fase de lectura y escritura separadas: la escritura
es una única transacción breve al final, para no bloquear los writes del colector).
Se instala como **cron diario separado** del push de métricas → captura interina de outcomes
hasta 08-03 sin tocar el colector.

**Excepción aprobada al "no tocar el colector":** dirección aprobó esta escritura additive a
`resolutions` bajo el principio "tocar lo roto, no lo sano". La tabla de precios
(`snapshots`) y el proceso del colector no se tocan.

## Scope / deferred
Este ADR cubre **solo** el backfill one-shot/diario. El **fix del path de captura del
colector** (set persistente de pendientes + re-poll con retry por UMA lag, independiente de
la membresía en el universo) queda **DIFERIDO/abierto**, pendiente de una decisión de
dirección separada. El cron diario es el puente interino, no el arreglo definitivo.

## Alternatives considered
- Arreglar el path del colector ahora — rechazado en este paso: toca el proceso sano; es una
  decisión separada que sigue pendiente.
- `source='collector'` para las backfilled — rechazado: borraría la señal diagnóstica (el
  live capture seguiría pareciendo que funciona). Con `source='backfill'`, `source='collector'`
  quedando en ~0 muestra que el path vivo sigue roto.

## Consequences
La data F2 recupera outcomes → utilizable por F3. El panel/sitio cuenta
`resoluciones (colector)` por `source='collector'` → sigue en 0 (honesto: captura viva rota);
las recuperadas son `source='backfill'`. `power_check.py` cuenta por pertenencia a snapshots
(cualquier source) → su alerta de integridad se apaga tras el backfill. Follow-up abierto:
exponer las backfilled en el panel/sitio, y el fix del colector.
