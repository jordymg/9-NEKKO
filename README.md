# NEKKO

Quantitative R&D project: does a repeatable, exploitable edge exist on Polymarket?

**AI agents: read `/docs` before doing anything.** Start with `docs/STATUS.md`.

## Cómo ver que está funcionando

Con el colector corriendo (`python -m collector.live_collector`), un solo comando dice si está vivo:

```
python -m analysis.status
```

Qué significa cada línea:

- **ultimo snapshot** — fecha y hora de la última foto de datos que guardó el colector, y hace cuánto fue.
- **veredicto** — `OK` = está vivo (guardó algo en los últimos 5 minutos); `STALE` = hace más de 5 minutos que no guarda nada, algo anda lento; `DOWN` = más de 30 minutos sin guardar, está caído y hay que revisarlo.
- **mercados trackeados** — cuántas apuestas distintas está siguiendo ahora mismo (el objetivo es 50 o más).
- **snapshots hoy / total** — cuántas fotos de datos guardó hoy y cuántas lleva acumuladas desde el principio.
- **hoy por grilla / evento** — de las fotos de hoy, cuántas fueron por rutina (una cada 5 minutos) y cuántas extra porque el precio del Bitcoin/Ethereum se movió fuerte de golpe.
- **gaps abiertos** — baches: períodos en los que el colector no pudo guardar datos, con el motivo. `0` es lo ideal; si hay uno abierto, el colector está teniendo problemas ahora.
- **resoluciones guardadas** — cuántas apuestas que seguíamos ya terminaron y les anotamos el resultado final.
