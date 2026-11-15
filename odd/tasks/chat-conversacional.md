# Chat conversacional con partidas abiertas

El chat deja de ser "una partida" y pasa a ser un asistente que conoce las
partidas anteriores: responde consultas sobre ellas, arranca partidas nuevas
por instrucción y permite retomar una partida abierta en el mismo chat.

## Specs

- S1: "que el chat sea un chat como tal y que se le puedan preguntas cosas de
  las partidas anteriores" — el chat responde preguntas sobre partidas
  anteriores consultando sus JSON guardados.
- S2: "mediantes una instruccion pueda empezar una nueva partida" — la
  historia no arranca porque sí al escribir cualquier cosa; arranca solo por
  instrucción explícita (comando `/nueva` o pedido en lenguaje natural).
- S3 (reescrito, L8): "Cada vez que retomo una partida, sea de donde sea, se
  tiene que retomar un chat nuevo" — retomar SIEMPRE abre un chat nuevo con
  esa partida (conversación reconstruida desde el JSON), nunca continúa en el
  chat actual. El listado de abiertas es solo con /partidas (últimas 3).
- S4: "Partidas abiertas son las que no llegaron a un final" — criterio:
  `finalizada=False` en el JSON de la partida.
- S5: "tiene que poder responder a la consulta sin salir de la partida activa.
  Luego al final de la respuesta tiene que volver a hacer las preguntas para
  que tomemos las decisiones de la patida actual" — las meta-consultas no
  avanzan ni cerrran la partida activa; al final se vuelven a ofrecer las
  opciones pendientes del capítulo en curso.
- S6 (reescrito, L8): "Hay dos comandos ambiguos: /retomar y /partidas. Yo
  dejaria solamente /partidas" — comandos: `/nueva`, `/partidas`, `/ayuda`;
  `/retomar` se elimina. Los comandos los resuelve la app sin LLM; el resto
  va a un único agente con tools de meta-consulta.
- S7: "hay un chat que es una partida nueva y escribas lo que escribas arranca
  la partida igual" (comportamiento a eliminar) — la partida no se crea al
  cargar la app ni arranca con cualquier mensaje.

- S8: "me tira este error cuando pongo /retomar o /partidas" — el listado de
  partidas abiertas no debe romper: se reprodujo con datos reales un
  `IndexError: list index out of range` en `comandos_chat.formatear_listado`
  cuando una partida abierta tiene `resumen_ultimo_capitulo` vacío (partida
  creada sin capítulos). Reproducción: `estado_partida.listar_partidas_abiertas`
  + `formatear_listado` sobre `partidas/` reales, 3 abiertas, una con 0 capítulos.
- S9: "no tengo un boton para empezar un nuevo chat, y todas las partidas
  arrancan o continuan en el chat actual" — hace falta un botón "Nuevo chat"
  que limpie la conversación (hoy todo se acumula en el chat actual).
- S10 (L8): "Los chats actualmente estan en un desplegable con un botón de
  retomar esta partida. Lo que me gustaria es que se vean como chats, tipo
  chat gpt y tocandolos me retome el chat con la partida esa" — el sidebar
  lista los chats-partida tipo ChatGPT (más recientes primero, activo
  resaltado) y tocar una entrada retoma esa partida en un chat nuevo.
- S11 (L8+L9): "El boton de 'Nueva partida' y 'Nuevo chat' me resultan raros
  los dos" — queda UN SOLO botón, "Nuevo chat" (decisión del cuestionario:
  modelo "el chat ES la partida"; arranque "Espera mi instrucción"): crea
  chat + partida nueva y espera la instrucción para escribir el capítulo 1
  (conserva S2). El botón "Nueva partida" y el desplegable "Retomar partida
  guardada" desaparecen. `/nueva` = instrucción explícita de juego: si el
  chat actual tiene una partida sin capítulos, arranca capítulo 1 en ese
  turno; si ya tiene capítulos, crea chat + partida nueva y arranca ahí.

## Tasks

- T1 (S3, S4): `estado_partida.listar_partidas_abiertas(limite)` con resumen
  por partida (id, capítulos, título/resumen del último, decisión pendiente).
  Inline. Commit U1: 887a5da.
- T2 (S1, S3): tools `listar_partidas_abiertas` y `consultar_otra_partida`
  (read-only, ID validado). Worker A. Commit U2: 41468ff.
- T3 (S2, S3): tools de control de sesión `iniciar_nueva_partida` y
  `retomar_partida` (validan y devuelven; la app detecta la llamada y aplica
  el cambio de partida activa). Worker A. Commit U2: 41468ff.
- T4 (S6): módulo `comandos_chat.py` (parseo de `/nueva`, `/retomar`,
  `/partidas`, `/ayuda`; formateo del listado; saludo inicial). Worker B.
  Commit U2: 41468ff.
- T5 (S1, S2, S5, S7): reglas nuevas en `INSTRUCCIONES` del agente: no
  arrancar historia sin instrucción, meta-consultas con tools, volver a
  ofrecer opciones tras responder, confirmar cambios de sesión sin escribir
  capítulos en el mismo turno. Worker A. Commit U2: 41468ff.
- T6 (S1–S7): `app.py`: hilo de chat propio (`thread_id` del chat, no de la
  partida), partida activa opcional, enrutamiento de comandos, retomar en el
  mismo chat con reconstrucción del historial, sidebar coherente. Worker C
  (mwh0th1m-3-b225). Commit U3: e85a004.
- T7 (S1–S7): README y verificación final de la suite completa. Inline (el
  runtime rechazó un tercer worker y ordenó ejecución inline; unidad de
  docs). Commit U3: e85a004.
- T8 (S8, S9): fix de `formatear_listado` ante resumen/título vacíos (con
  test RED reproduciendo el IndexError) + botón "Nuevo chat" en el sidebar
  que resetea la conversación a estado inicial (nuevo `id_chat`, historial
  limpio con saludo, sin partida activa; las partidas quedan guardadas y se
  retoman con /retomar). Commit U4: 7e24888.
- T9 (S3, S6, S10, S11): revisión de UX: sidebar tipo ChatGPT con
  chats-partida, retomar siempre en chat nuevo, /retomar eliminado, /nueva
  con semántica de instrucción de juego, botón único "Nuevo chat" que crea
  partida a la espera; README. Commit U5.

## Log

- L1 (pedido original, textual): "Quiero hacer una modificaciones en el
  proyecto. Actualmente el proyecto es así, hay un chat que es una partida
  nueva y escribas lo que escribas arranca la partida igual, el sistema
  permite volver a partidas anteriores utilizando su ID, trae tanto el json
  de partida como el contexto con el checkpointer, pero lo que yo quiero es
  que el chat sea un chat como tal y que se le puedan preguntas cosas de las
  partidas anteriores y mediantes una instruccion pueda empezar una nueva
  partida. Pero quiero que el chay sea capaz de poder responder cosas de
  partidas anteriores, que yo pueda pedir retomar una partida y me liste las
  partidas abiertas (ultimas 3 o 5 abiertas) y asi elegir una y poder
  retormarla en ese mismo chat. Me explico ? decime lo que entediste de mi
  peticion."
- L2 (decisiones confirmadas, textual): "1. Quiero una mezcla entre ambos
  2. Partidas abiertas son las que no llegaron a un final 3. En ese caso,
  tiene que poder responder a la consulta sin salir de la partida activa.
  Luego al final de la respuesta tiene que volver a hacer las preguntas para
  que tomemos las decisiones de la patida actual"
- L3: cuestionario de diseño: agente único + comandos deterministas;
  comandos elegidos: /nueva, /retomar, /partidas, /ayuda ("Todas las
  mencionadas"); listado por defecto: últimas 3.
- L4: diseño técnico acordado con el usuario en chat: desacoplar thread_id
  del chat del id_partida; la app es autoridad del switch de partida (el LLM
  propone con tools, la app valida y aplica); continuidad canónica por JSON +
  contexto_narrativo.
- L5: slice boundary (844 líneas autoradas en U1+U2 más los 2 commits previos
  de main): T1–T5 commiteados en U1 (887a5da) y U2 (41468ff); T6+T7 forman el
  slice de cierre U3 en feat/chat-conversacional. El push/PR queda decisión
  del usuario.
- L6: cierre del feature. T6 por Worker C: rewiring de app.py (id_chat como
  thread_id, partida activa opcional, comandos deterministas, retomado
  determinista y propuesto por el agente vía pasos_agente.cambio_de_sesion,
  +6 tests). T7 inline: README actualizado (descripción, estructura, tools,
  memoria, ejecución, estado) y verificación final: pytest 216 passed,
  py_compile OK de los 6 módulos, imports OK. El flujo con LLM real queda
  pendiente (los comandos y el retomado determinista no usan LLM).
- L7 (corrección del usuario, textual): "me tira este error cuando pongo
  /retomar o /partidas" + "Ademas no tengo un boton para empezar un nuevo
  chat, y todas las partidas arrancan o continuan en el chat actual".
  Reproducción por el orquestador: IndexError en comandos_chat.formatear_listado
  con una partida abierta de 0 capítulos (resumen_ultimo_capitulo vacío).
- L8 (revisión de UX del usuario, textual): "Perfecto. Ya quedo mejor. Hay
  algunas cosas que hay que arreglar: - Hay dos comandos ambiguos: /retomar y
  /partidas. Yo dejaria solamente /partidas - Tenemos botones y funciones que
  no van. Por ejemplo. El boton de 'Nueva partida' y 'Nuevo chat' me resultan
  raros los dos. cual dejarias vos ? Y que implementacion le podemos dar. Que
  el chat sea chat o que cada chat inicie una nueva partida de una ? - Cada
  vez que retomo una partida, sea de donde sea, se tiene que retomar un chat
  nuevo - Los chats actualmente estan en un desplegable con un botón de
  retomar esta partida. Lo que me gustaria es que se vean como chats, tipo
  chat gpt y tocandolos me retome el chat con la partida esa Pero tengo la
  duda de si el chat es un si deberia ser una partida, o si el chat es chat y
  la partida se carga sobre un chat efimero"
- L9 (cuestionario de diseño): modelo "El chat ES la partida" (uno a uno,
  sidebar tipo ChatGPT, botón único "Nuevo chat"); arranque "Espera mi
  instrucción" (el chat nuevo no escribe capítulo 1 hasta que se lo pida).
