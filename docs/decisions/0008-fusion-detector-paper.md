# ADR-0008: Fases 1 y 2 fusionadas (detector + paper trading), construcción inmediata

**Date:** 2026-07-20
**Status:** Accepted

## Context
El roadmap original serializa: Fase 1 (detector loguea oportunidades) → Fase 2 (paper
trading simula el ciclo completo). Ambas consumen los mismos snapshots y comparten el 90%
del código: la diferencia es agregar la simulación de fill y el PnL virtual — "el mismo
módulo, dos columnas más". Esperar al final de la ventana F2 (≥2026-08-03) para empezar a
construir regala dos semanas en las que podrían acumularse operaciones simuladas.

## Decision
1. **Fusión**: un solo módulo `/paper` hace detector + paper trading (detectar señal,
   simular fill contra el libro registrado, mantener posiciones virtuales, KPIs corrientes).
2. **Arranque inmediato**: se construye y corre en shadow AHORA, en paralelo a la
   recolección F2 — opera de mentira sobre los datos reales que el colector va guardando.
3. **Guard epistémico**: las reglas iniciales son BORRADORES (`draft_*`), escritas antes de
   tener una tesis validada. Los KPIs que produzcan **NO son válidos para ningún gate** de
   VALIDATION.md hasta que las reglas deriven de una tesis respaldada por datos (F3). El
   gate de Fase 2→3 queda sin cambios; esto solo adelanta infraestructura y acumula
   histórico de simulación descartable.

## Alternatives considered
- Mantener fases separadas y secuenciales — rechazado: duplica plumbing y desperdicia la
  ventana de recolección; el riesgo que la separación protegía (creerle a KPIs de reglas
  inventadas) se mitiga con el guard explícito, no con el calendario.
- Detector sin simulación de fill (solo log de oportunidades) — rechazado: el costo
  marginal de simular el fill contra el libro ya registrado es bajo y es lo que convierte
  "oportunidad" en "expectativa neta".

## Consequences
Al cerrar la ventana F2 habrá semanas de operaciones simuladas listas para comparar contra
las reglas que salgan de la tesis real. Riesgo aceptado y mitigado: tentación de leer los
KPIs de reglas draft como evidencia — están rotulados `draft_` en DB, config y panel.
