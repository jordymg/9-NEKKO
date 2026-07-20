# ADR-0007: Colector F2 en VPS mínimo descartable (Opción B)

**Date:** 2026-07-19
**Status:** Accepted

## Context
El colector F2 necesita ≥14 días consecutivos sin pérdida de datos antes del kill date
2026-08-12 — presupuesto de reinicios: cero. Dos evidencias en contra de correrlo local:
(1) hoy quedó corriendo como proceso hijo de una sesión de Claude Code — muere al cerrar
la app; (2) precedente del 2026-07-19: un corte de DNS local mató la corrida histórica
larga. ARCHITECTURE §1 ya contemplaba "collector can move to a VPS if uptime suffers".

## Decision
VPS mínimo (~5 USD/mes, Ubuntu 24.04, instancia más chica del proveedor que elija Jordi).
Colector bajo **systemd** con `Restart=always` + `RestartSec`, timezone UTC, logs a
journald. Sin secretos en el servidor (solo APIs públicas de lectura, ADR-0002); la única
credencial es la clave SSH de acceso. La DB se trae a demanda con `sqlite3 .backup` +
`scp` (nunca por git). Costo acotado: 1-2 meses; el servidor se destruye al terminar el
experimento (THESIS.md o KILL.md).

## Alternatives considered
- Seguir local (Opción A: terminal propia + máquina 24/7) — rechazado: una laptop/PC
  hogareña con Windows Update, cortes de luz/red y uso diario no da 14 días limpios; ya
  falló una vez.
- Task Scheduler de Windows con reinicio automático — rechazado: mitiga el crash del
  proceso pero no los reinicios/suspensiones del host.
- Cloud "serio" (contenedores, IaC) — rechazado: sobreingeniería para un experimento con
  fecha de muerte; un systemd unit en una VM de 5 dólares alcanza.

## Consequences
Uptime deja de depender de la compu de Jordi; el panel `analysis/status.py` corre igual
vía SSH. Nuevo paso operativo: traer la DB al local para análisis (comando único
documentado en README). Riesgo aceptado: proveedor único sin redundancia — un outage del
VPS abre un gap, que la tabla `gaps` y el panel harán visible.
