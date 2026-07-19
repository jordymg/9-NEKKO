# Bitácora — NEKKO

> Diario del proyecto en palabras simples, para cualquier persona sin conocimientos de
> trading ni de programación. Una entrada por sesión de trabajo.

## 2026-07-12 — Arranque del proyecto

Definimos qué queremos averiguar: si en Polymarket (un sitio donde la gente apuesta dinero
a si va a pasar algo, por ejemplo "¿el Bitcoin va a subir esta semana?") hay apuestas mal
cotizadas — es decir, precios que no reflejan la probabilidad real — y si eso se puede
aprovechar de forma repetible. Armamos un plan por etapas: primero medir con datos si esa
ventaja existe, y recién después, si existe, construir algo que la use. Pusimos una fecha
límite: el 12 de agosto. Si para entonces los datos no muestran nada prometedor, el proyecto
se archiva y no pasa nada — averiguar que no hay ventaja también es un buen resultado.

## 2026-07-19 (noche) — La máquina completa funcionó por primera vez de punta a punta

Por primera vez todo el circuito anduvo junto y sin caerse: bajó 470 apuestas ya terminadas,
calculó cuánto debería haber valido cada una, comparó eso con lo que pasó de verdad y guardó
todo ordenado. Los primeros números parecen decir que la gente paga de más por estas
apuestas, pero todavía no nos los creemos: casi todas las apuestas revisadas son de la misma
semana de junio, y si esa semana el mercado anduvo mal, todas se equivocan juntas — sería
como juzgar a un heladero mirando solo una semana de lluvia. La próxima sesión revisamos
apuestas repartidas en varios meses distintos y verificamos a mano que estamos leyendo bien
quién ganó cada apuesta, antes de sacar cualquier conclusión.

## 2026-07-19 — Construimos la máquina de medir y la pusimos a trabajar

Armamos las tres piezas que faltaban: un programa que baja de internet los datos de miles de
apuestas ya terminadas, una fórmula que calcula cuánto *debería* valer cada apuesta según
cómo se venía moviendo el Bitcoin, y un comparador que cruza las dos cosas contra lo que
realmente pasó. También averiguamos con precisión cuánto cuesta operar (la comisión del
sitio más la diferencia entre precio de compra y de venta) para descontarlo siempre: una
"ventaja" que no cubre esos costos no sirve de nada. La primera prueba chica funcionó bien;
la revisión grande de seis meses arrancó pero se cortó a mitad de camino por una falla de
internet, así que la próxima sesión empieza por hacer la máquina más resistente a cortes y
volver a correrla.

## 2026-07-13 — Luz verde: los datos que necesitamos existen y son gratis

Comprobamos que Polymarket deja bajar gratis, sin pedir permiso ni cuenta, el historial de
miles de apuestas ya terminadas: cómo fue cambiando el precio de cada una y cómo terminó
(si pasó o no pasó lo que se apostaba). Esto es clave porque nos permite probar nuestras
teorías con datos del pasado en cuestión de días, en vez de esperar semanas juntando datos
nuevos. También anotamos las trampas del camino (por ejemplo, hay un dato — cuánto cuesta
realmente entrar y salir de una apuesta — que el historial no guarda, así que vamos a tener
que estimarlo). Conclusión: luz verde para el siguiente paso.
