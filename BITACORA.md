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

## 2026-07-20 — La cámara quedó encendida en la nube

Hoy sí: conseguimos la computadora en la nube (la chica, porque la grande seguía agotada) y
dejamos la cámara grabando. Hubo un obstáculo curioso: Binance no atiende visitas desde
Estados Unidos, donde vive nuestro servidor — pero tiene una puerta oficial solo-para-mirar
que funciona perfecto, y por ahí entramos. Antes de irnos la probamos a lo bruto: matamos el
programa a propósito y el servidor lo revivió solo en segundos, que es exactamente lo que
tiene que pasar si algo falla a las 3 de la mañana. El reloj de las dos semanas de filmación
arrancó hoy; en dos días le hacemos el primer control de calidad a lo grabado.

## 2026-07-19 (noche 2) — Alquilamos una computadora en la nube; nos quedamos en la puerta

Construimos la "cámara" que va a filmar los precios en vivo durante dos semanas (y un
tablero de control: un solo comando dice si está grabando o se cayó). Como no puede
depender de nuestra compu de casa — que se apaga, se suspende y se corta — alquilamos una
computadora en la nube (gratis, en Oracle) y armamos su conexión a internet pieza por
pieza. Nos quedamos en la puerta: no había máquinas disponibles esta noche. Mañana
reintentamos — la cámara arranca a filmar sus dos semanas apenas encienda.

## 2026-07-19 (tarde-noche 2) — Probamos con cuatro meses distintos para que una mala semana no nos engañe

Primero verificamos a mano, apuesta por apuesta contra los precios reales del Bitcoin, que
estábamos leyendo bien quién ganó cada una: perfecto, seis de seis. Después repetimos la
medición pero repartiendo las apuestas entre marzo, abril, mayo y junio, para que ninguna
semana rara domine el resultado. Y la señal que nos había entusiasmado desapareció: el
"pagan de más" que veíamos era espejismo — cada mes da un numerito distinto que cambia de
signo, como el clima, y en promedio no hay nada aprovechable. Esto no es un fracaso: es la
máquina funcionando bien y evitándonos apostar plata a un espejismo. Lo que sigue es medir
lo que el pasado no guarda — los precios de compra y venta en vivo — que es donde todavía
pueden esconderse las otras teorías.

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
