# ADR-0010 — Gate F2 por consistencia de signo (reemplaza la vara formal al 95%)

- **Estado:** Aceptado
- **Fecha:** 2026-07-26
- **Decisión tomada en:** chat DECISIONES
- **Modifica:** Camino C (framework de decisión del gate F2→F3), definido en el chat
  DECISIONES. **Al momento de este ADR, Camino C no está versionado como ADR en el repo**
  (no existe un 00YY al que referenciar; su fuente es el chat DECISIONES). Este ADR
  **deroga** de Camino C la vara formal al 95% del stage 1 (test de existencia formal +
  default-KILL-ante-ambigüedad + extensión única de 14 días) y **conserva** su estructura
  de dos etapas (existencia → explotabilidad, con stage 2 obligatorio) y su filosofía de
  default-KILL (KILL ante signo inconsistente o zona gris; sin pivote automático).
- **Relacionado:** ADR-0008 (guard epistémico del paper engine), hallazgo F1
  (sesgo por mes / artefacto de régimen; `docs/results/f1-gross-2026-07-19.md`).

---

## Contexto

El gate F2→F3 de Camino C se definió como un test de existencia en dos etapas
(stage 1 existencia, stage 2 explotabilidad), con default KILL ante ambigüedad o
análisis incompleto, y una única extensión de 14 días permitida solo si stage 1
pasaba y stage 2 fallaba exclusivamente por tamaño de muestra insuficiente.

El 2026-07-26 se corrió el cálculo de poder estadístico del stage 1 contra la
muestra que la ventana F2 va a producir (~230 mercados resueltos proyectados;
181 recuperados y en aumento al momento del cálculo). Resultado: **ningún test de
existencia formal al 95% tiene poder con esa muestra.** Tanto el test de proporción
por mercado como la variante de calibración agregada (chi-cuadrado de bondad de
ajuste) coinciden en orden de magnitud:

| Efecto a detectar | Mercados necesarios (95% poder) | Poder con n≈230 |
|---|---|---|
| 10 pts (edge enorme, improbable por F1) | ~320–355 | ~80% |
| 8 pts | ~500–555 | ~57% |
| 5 pts | ~1.300–1.420 | ~23% |
| 3 pts | ~3.600–3.940 | ~10% |
| 2 pts | ~8.100–8.900 | ~7% |

La muestra corta **no** proviene de la falla de backfill (ya reparada; ver ADR de
backfill de resoluciones). Proviene estructuralmente de que 14 días de ventana
producen ~230 mercados resueltos. Y F1 ya estableció que el edge, de existir en
crypto líquido, es chico (correlación implícita-vs-modelo = 0.956) — justo el
régimen que exige miles de mercados.

Consecuencia: aplicar la vara formal al 95% con default-KILL-ante-ambigüedad
produciría, casi por construcción, un veredicto "no concluyente" → KILL. Eso sería
un KILL **por falta de muestra, no por ausencia de edge** — precisamente el KILL
mal fundado que el proyecto quiere evitar.

## Decisión

Se **reemplaza** la vara formal al 95% del stage 1 por un criterio de
**consistencia de signo** de la brecha implícita-vs-real, estratificada en 4
segmentos temporales de la ventana:

**CONTINUE a F3** si:
- La brecha implícita-vs-real apunta en dirección consistente across segmentos:
  **≥3 de 4 segmentos temporales del mismo signo**, y el segmento disidente (si lo
  hay) es de **magnitud chica**.
- La magnitud del edge la evalúa Jordi **a criterio en el momento** — este ADR
  fija el criterio de *dirección/consistencia*, no un umbral de magnitud.

**KILL** si:
- Signo **inconsistente** entre segmentos (partición 2-2, o segmento disidente de
  magnitud grande), **o**
- **Zona gris**: ni claramente señal ni claramente ruido.

**Zona gris = KILL, NO extensión.** La extensión de 14 días contemplada en Camino C
queda **inaplicable en F2**: 2026-08-03 + 14 días = 2026-08-17, que se pasa del kill
date del 2026-08-12. No se extiende la ventana ni se mueve el kill date.

**En caso de KILL:**
- `KILL.md` preserva explícitamente qué queda **reutilizable**: infraestructura
  (colector, VM, pipeline de datos, sitio), metodología (Camino C, este framework,
  el cálculo de poder), y hallazgos (F1 sesgo-por-mes, F2 lo que haya arrojado).
- Las hipótesis alternativas ("otras aristas" del edge) se registran como
  **candidatas para un eventual ciclo nuevo**, cada una con su propio go/no-go
  decidido por separado. **NUNCA se activan automáticamente para evitar el KILL** —
  un KILL es un KILL; el pivote a otra hipótesis es una decisión nueva y explícita,
  no un escape del gate.

## Fundamento — por qué la consistencia de signo no es "bajar el estándar"

El criterio de consistencia de signo across segmentos temporales es **el mismo
discriminador que mató a tesis A en F1**. En F1, el sesgo cambiaba de signo mes a
mes; se concluyó que era artefacto de régimen, no edge, y ningún candidato a tesis
A sobrevivió. Ese fue un hallazgo empírico validado del proyecto: *si el signo no
se sostiene al estratificar por tiempo, no es señal.*

Este ADR toma ese discriminador ya validado y lo formaliza como la vara del gate
F2. No se trata de relajar un estándar estadístico porque la muestra no alcanza;
se trata de usar el test que el propio proyecto demostró que distingue señal de
régimen — un test que además **no depende del tamaño de muestra de la misma forma
que la significancia formal**, porque pregunta por la estabilidad del signo, no por
la magnitud de un p-valor. La significancia al 95% era la vara equivocada para esta
muestra; la consistencia de signo es la vara que F1 ganó con evidencia.

## Consecuencias

**Positivas:**
- El gate del 2026-08-05 no dispara un default-KILL automático por "no concluyente"
  derivado de una vara inalcanzable.
- El stage 1 pasa de test de significancia a **lectura exploratoria de dirección**,
  evaluada por Jordi con el criterio de consistencia como piso objetivo.
- El criterio está anclado en un hallazgo empírico propio (F1), no inventado ad hoc.

**Negativas / riesgos asumidos:**
- Consistencia de signo es un criterio **más débil** que la significancia formal:
  puede dar un CONTINUE sobre un edge que un test con más muestra rechazaría. Se
  asume conscientemente para no incurrir en el falso KILL por muestra.
- Introduce un componente de **juicio humano** (Jordi evalúa magnitud) en un gate
  antes automático. Es deliberado: la decisión final del rumbo el 2026-08-03 es a
  criterio, con este criterio de signo como piso objetivo, no como sentencia.
- "Magnitud chica/grande" del disidente y "zona gris" no están cuantificados aquí:
  quedan a criterio de Jordi en el momento. Trade-off aceptado a cambio de no
  falsear precisión que la muestra no soporta.

## Alcance

Este ADR aplica **solo al gate F2→F3**. No modifica el guard epistémico de ADR-0008
(los KPIs `draft_` siguen sin valer para ningún gate). No modifica la duración de
la ventana ni el kill date. No pre-aprueba ningún ciclo futuro ni ninguna hipótesis
alternativa.

### Limitación probatoria y obligatoriedad del stage 2

La consistencia de signo detecta **dirección**, no **magnitud con rigor
estadístico**. Es la vara que F1 validó como discriminador de señal-vs-régimen,
pero es de **menor poder probatorio** que la vara formal al 95% que reemplaza: un
CONTINUE bajo este criterio afirma que la brecha implícita-vs-real apunta de forma
estable en un sentido, **no** que su magnitud esté establecida ni que el edge sea
explotable neto de costos.

Por eso, un CONTINUE de stage 1 bajo este ADR **no habilita comprometer capital**.
El **stage 2 (explotabilidad) sigue siendo obligatorio** antes de cualquier
despliegue de capital en F3: dimensionamiento, costos de transacción, capacidad,
y basis risk (recordar: la resolución de Polymarket usa oráculos Chainlink/UMA, no
precios de Binance). Este ADR sustituye la vara de *existencia*; no toca ni relaja
la exigencia de *explotabilidad*. Pasar stage 1 por consistencia de signo es
condición necesaria, nunca suficiente, para F3.
