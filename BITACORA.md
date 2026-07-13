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

## 2026-07-13 — Luz verde: los datos que necesitamos existen y son gratis

Comprobamos que Polymarket deja bajar gratis, sin pedir permiso ni cuenta, el historial de
miles de apuestas ya terminadas: cómo fue cambiando el precio de cada una y cómo terminó
(si pasó o no pasó lo que se apostaba). Esto es clave porque nos permite probar nuestras
teorías con datos del pasado en cuestión de días, en vez de esperar semanas juntando datos
nuevos. También anotamos las trampas del camino (por ejemplo, hay un dato — cuánto cuesta
realmente entrar y salir de una apuesta — que el historial no guarda, así que vamos a tener
que estimarlo). Conclusión: luz verde para el siguiente paso.
