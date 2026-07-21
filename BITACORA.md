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

## 2026-07-21 (2) — La página ya muestra números de verdad, y blindamos la cámara

Primero una aclaración: creíamos haber perdido la llave del servidor en la nube, pero no —
estaba guardada todo el tiempo en la compu; lo que había fallado eran intentos desde otra
máquina distinta. Con acceso normal, hicimos dos cosas. Una: blindar la "cámara" que graba
los precios. Habíamos visto en su diario de a bordo que una vez el sistema la había apagado
de golpe por quedarse sin memoria, y que las actualizaciones automáticas la reiniciaban y le
cortaban internet un ratito. Le pusimos topes de memoria (para que ante un pico se frene en
vez de que la maten), le dijimos a las actualizaciones que no reinicien nada ni prendan y
apaguen la máquina sola, y dejamos anotado que el reinicio grande que quedó pendiente se hace
recién después del 3 de agosto, para no cortar la grabación de dos semanas. Dos: conectamos
la página web a los datos reales. Ahora la cámara escribe un resumen de su estado y sus
números, lo sube al proyecto, y la web se actualiza sola cada hora con datos de verdad — con
un candado que impide que se suba sin querer la base de datos completa (el proyecto es
público). Falta un solo permiso que tiene que dar Jordi para que ese envío automático arranque.

## 2026-07-21 — Una página web que se arma sola para ver todo desde el celular

Le hicimos al proyecto una página web pública, pensada para leer desde el teléfono: muestra
en qué anda todo — la fase, los hallazgos, el piloto de práctica — con un diseño oscuro y
prolijo. Lo lindo es que se arma sola: cada vez que cambiamos algo, un robot de GitHub la
vuelve a generar y publicar sin que toquemos nada. Pusimos especial cuidado en dos cosas de
honestidad: los resultados del piloto de práctica salen dentro de un recuadro amarillo bien
grande que avisa "estos números son de prueba, no cuentan", y la parte del estado en vivo,
que ese día todavía no estaba conectada, mostraba "esperando datos" en vez de inventar
números. Antes de abrirla al público revisamos que no se colara ninguna contraseña ni dato
secreto en todo el historial del proyecto: limpio. Ya está online. (Nota del día siguiente:
ese "todavía no conectado" quedó resuelto — ver la entrada del 21/07 sobre datos reales.)

## 2026-07-20 (2) — Le agregamos un piloto de práctica

Al sistema le sumamos un "piloto de práctica": un programa que opera de mentira sobre los
datos de verdad que la cámara va grabando. Ve los mismos precios, decide como si fuera en
serio, y anota cuánto habría ganado o perdido — pero no toca un solo dólar, y lo armamos
para que ni siquiera exista un camino hacia dinero real. La idea: cuando algún día juegue
con plata, que ya sepa manejar. Importante y anotado en grande: sus primeras reglas de
decisión son borradores inventados para probar el motor, así que sus resultados no
cuentan como evidencia de nada — primero los datos tienen que decirnos qué regla vale la
pena, y recién después el piloto practica esa regla en serio.

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
