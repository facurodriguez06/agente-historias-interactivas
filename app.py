"""Interfaz Streamlit: historias, memoria persistente y herramientas del agente."""

import uuid

import streamlit as st
from langchain_core.messages import AIMessage

import comandos_chat
import estado_partida
from agente import crear_agente
from estado_partida import (
    CARPETA_PARTIDAS,
    TOTAL_CAPITULOS,
    consultar_estado,
    crear_partida,
    listar_partidas_abiertas,
    url_de_imagen,
)
from herramientas import ContextoPartida
from imagenes import URL_UNSPLASH, con_utm
from pasos_agente import capitulo_de_respaldo, cambio_de_sesion, pasos_de_mensaje
from proveedores import proveedor_y_modelo

st.set_page_config(
    page_title="Historias interactivas",
    page_icon="📖",
    layout="centered",
)

st.title("Historias interactivas")
st.caption("Prototipo Unidad 5 · RAG + create_agent + SQLite")

# El chat es UNA conversación con hilo propio: sobrevive a los cambios de partida.
if "id_chat" not in st.session_state:
    st.session_state.id_chat = uuid.uuid4().hex

# La partida activa es opcional: al cargar la app no hay ninguna y nada arranca solo.
if "id_partida" not in st.session_state:
    st.session_state.id_partida = ""

# Historial visible: (rol, texto, imagenes, pasos)
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []

if "imagenes_mostradas" not in st.session_state:
    st.session_state.imagenes_mostradas = set()

# Listado de partidas abiertas esperando una elección numérica (o None).
if "listado_pendiente" not in st.session_state:
    st.session_state.listado_pendiente = None

if "agente" not in st.session_state:
    try:
        st.session_state.agente = crear_agente()
    except Exception as exc:
        st.error(str(exc))
        st.stop()


def imagen_de_capitulo(capitulo):
    """Devuelve la foto y su atribución, si existe."""
    imagen = capitulo.get("imagen")
    if not imagen:
        return []
    url = url_de_imagen(capitulo)
    if not url:
        return []
    pie = (
        f"Foto: [{imagen['autor']}]({con_utm(imagen['url_autor'])}) / "
        f"[Unsplash]({con_utm(URL_UNSPLASH)})"
    )
    return [(url, pie)]


def reconstruir_historial(estado):
    """Redibuja capítulos/decisiones desde el JSON al retomar una partida.

    El checkpoint de SQLite conserva por separado la memoria del LLM.
    Los pasos técnicos de sesiones anteriores no se reconstruyen en la interfaz.
    """
    historial = []
    mostradas = set()
    decisiones = {d["capitulo"]: d for d in estado["decisiones"]}

    for capitulo in estado["capitulos"]:
        texto = f"**Capítulo {capitulo['numero']}: {capitulo['titulo']}**\n\n{capitulo['texto']}"
        if capitulo["numero"] == 5:
            texto += "\n\n**Historia terminada.**"
        fotos = imagen_de_capitulo(capitulo)
        if fotos:
            mostradas.add(capitulo["numero"])
        historial.append(("assistant", texto, fotos, []))
        decision = decisiones.get(capitulo["numero"])
        if decision:
            historial.append(("user", str(decision["opcion"]), [], []))

    return historial, mostradas


def partidas_guardadas():
    """Lista partidas JSON de más reciente a más antigua, excluyendo SQLite."""
    if not CARPETA_PARTIDAS.exists():
        return []
    return [
        ruta.stem
        for ruta in sorted(
            CARPETA_PARTIDAS.glob("*.json"),
            key=lambda ruta: ruta.stat().st_mtime,
            reverse=True,
        )
    ]


def estado_retomable(id_partida):
    """Estado de una partida que existe y no llegó a un final; None si no se puede retomar."""
    if not id_partida:
        return None
    try:
        estado = consultar_estado(id_partida)
    except (ValueError, OSError):
        return None
    if estado["finalizada"]:
        return None
    return estado


def abrir_chat_de_partida(id_partida):
    """Abre `id_partida` en un chat nuevo: un chat por partida (S3).

    Cambia el hilo del chat (id_chat nuevo), deja la partida como activa y
    reconstruye la historia desde el JSON; el chat anterior queda guardado y se
    puede volver a abrir desde el sidebar o con /partidas. Sirve para partidas
    abiertas y también para terminadas (se abren para releerlas). Devuelve True
    si el cambio se aplicó; si la partida no existe, muestra el error y no toca
    nada: la partida activa queda como estaba.
    """
    try:
        estado = consultar_estado(id_partida)
    except (ValueError, OSError):
        estado = None
    if estado is None:
        st.error(f"No se pudo abrir la partida `{id_partida[:8]}`.")
        return False

    st.session_state.id_chat = uuid.uuid4().hex
    st.session_state.id_partida = id_partida
    st.session_state.listado_pendiente = None
    st.session_state.historial_visible = [
        (
            "assistant",
            f"Abriste la partida `{id_partida[:8]}` en un chat nuevo — así venía la historia:",
            [],
            [],
        )
    ]
    historial, mostradas = reconstruir_historial(estado)
    st.session_state.historial_visible.extend(historial)
    st.session_state.imagenes_mostradas = mostradas
    return True


def aplicar_cambio_del_agente(cambio):
    """Aplica el switch de partida que el agente propuso; lo ignora si es inválido.

    El agente ya le reportó el error al usuario: acá la app solo valida en silencio.
    Todo cambio abre un chat nuevo: un chat por partida (S3).
    """
    if cambio["accion"] == "retomar":
        estado = estado_retomable(cambio["id_partida"])
        if estado is None:
            return
        st.session_state.id_chat = uuid.uuid4().hex
        st.session_state.id_partida = cambio["id_partida"]
        st.session_state.listado_pendiente = None
        st.session_state.historial_visible = [
            (
                "assistant",
                f"Abriste la partida `{cambio['id_partida'][:8]}` en un chat nuevo — así venía la historia:",
                [],
                [],
            )
        ]
        historial, mostradas = reconstruir_historial(estado)
        st.session_state.historial_visible.extend(historial)
        st.session_state.imagenes_mostradas = mostradas
    elif cambio["accion"] == "nueva":
        try:
            consultar_estado(cambio["id_partida"])
        except (ValueError, OSError):
            return
        st.session_state.id_chat = uuid.uuid4().hex
        st.session_state.id_partida = cambio["id_partida"]
        st.session_state.listado_pendiente = None
        st.session_state.imagenes_mostradas = set()


INSTRUCCION_CAPITULO_1 = (
    "The application already created the game session and set it as the "
    "active game. Begin chapter 1 now following the mandatory workflow."
)


def partida_sin_capitulos():
    """True si el chat actual tiene una partida guardada y todavía sin capítulos."""
    if not st.session_state.id_partida:
        return False
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return False
    return not estado["capitulos"]


def ejecutar_nueva_partida():
    """Instrucción explícita de juego (S11): /nueva o el pedido del usuario.

    Si el chat actual tiene una partida sin capítulos (la que dejó el botón
    "Nuevo chat"), arranca el capítulo 1 acá mismo con un turno sintético. Si
    la partida ya estaba en marcha o terminada, o no hay ninguna, abre un chat
    nuevo con una partida nueva y escribe el capítulo 1 ahí: un chat por
    partida (S3).
    """
    if partida_sin_capitulos():
        turno_del_agente(INSTRUCCION_CAPITULO_1)
        return

    id_partida = crear_partida()
    st.session_state.id_chat = uuid.uuid4().hex
    st.session_state.id_partida = id_partida
    st.session_state.listado_pendiente = None
    st.session_state.imagenes_mostradas = set()

    nota = (
        f"Listo, te abrí un chat nuevo con una partida nueva (`{id_partida[:8]}`) "
        "y ya te arranco con el capítulo 1."
    )
    st.session_state.historial_visible = [("assistant", nota, [], [])]
    with st.chat_message("assistant"):
        st.markdown(nota)

    turno_del_agente(INSTRUCCION_CAPITULO_1)


def ejecutar_nuevo_chat():
    """Crea un chat nuevo con una partida nueva esperando la instrucción (S11).

    Un chat es una partida: el botón único "Nuevo chat" crea la partida (sin
    escribir capítulos) y la deja activa en un hilo nuevo. La historia no
    arranca sola (S2): espera la instrucción del usuario, que puede ser
    /nueva o un pedido en lenguaje natural.
    """
    id_partida = crear_partida()
    st.session_state.id_chat = uuid.uuid4().hex
    st.session_state.id_partida = id_partida
    st.session_state.historial_visible = [
        ("assistant", mensaje_de_bienvenida(id_partida), [], [])
    ]
    st.session_state.imagenes_mostradas = set()
    st.session_state.listado_pendiente = None
    st.rerun()


def mensaje_de_bienvenida(id_partida):
    """Primer mensaje de un chat recién creado: partida lista, sin capítulos."""
    return (
        f"¡Hola! Te abrí un chat nuevo con una partida lista (`{id_partida[:8]}`). "
        "Todavía no escribí nada: la historia arranca cuando vos me lo pidas.\n\n"
        "Decime **«empezá»** cuando quieras arrancar, o **/ayuda** para ver "
        "todo lo que puedo hacer."
    )


def entradas_del_sidebar():
    """Chats-partida guardados (abiertas y terminadas), más recientes primero (S10).

    Mismo orden por mtime que listar_partidas_abiertas, sin el filtro de
    abiertas: la lista del sidebar muestra todos los chats. Los JSON ilegibles
    se ignoran, igual que en el listado del chat.
    """
    entradas = []
    for id_partida in partidas_guardadas():
        try:
            estado = consultar_estado(id_partida)
        except (ValueError, OSError):
            continue
        capitulos = estado["capitulos"]
        entradas.append(
            {
                "id_partida": id_partida,
                "capitulos": len(capitulos),
                "titulo": capitulos[-1]["titulo"] if capitulos else "Partida nueva",
                "finalizada": estado["finalizada"],
            }
        )
    return entradas


def dibujar_lista_de_chats():
    """Lista tipo ChatGPT de los chats-partida; la activa va resaltada (S10).

    Devuelve el id de la partida a abrir en un chat nuevo, o None.
    """
    elegida = None
    activa = st.session_state.id_partida
    entradas = entradas_del_sidebar()
    if not entradas:
        st.caption("Todavía no hay partidas guardadas.")
        return elegida

    for entrada in entradas:
        es_activa = entrada["id_partida"] == activa
        detalle = f"{entrada['capitulos']} de {TOTAL_CAPITULOS} capítulos"
        if entrada["finalizada"]:
            detalle += " · terminada"
        etiqueta = f"{'▶ ' if es_activa else ''}{entrada['titulo']} ({detalle})"
        if st.button(
            etiqueta,
            key=f"chat_{entrada['id_partida']}",
            type="primary" if es_activa else "secondary",
            use_container_width=True,
        ):
            # La activa ya es el chat de esa partida: un clic no abre otro chat.
            if not es_activa:
                elegida = entrada["id_partida"]
    return elegida


with st.sidebar:
    st.write("**Partida actual**")
    if st.session_state.id_partida:
        st.code(st.session_state.id_partida[:8])
    else:
        st.info("Sin partida activa")

    nuevo_chat_pedida = st.button("Nuevo chat", use_container_width=True)
    st.caption(
        "Crea un chat con una partida nueva en blanco; la historia arranca "
        "cuando se lo pedís."
    )

    st.write("**Chats**")
    retomar_pedida = dibujar_lista_de_chats()

    proveedor, modelo = proveedor_y_modelo()
    st.caption(f"**Modelo:** {proveedor} · `{modelo}`")
    st.info(
        "Los capítulos, las decisiones y el contexto narrativo se guardan en JSON. "
        "La memoria del agente se guarda en SQLite dentro de partidas/."
    )
    panel_estado = st.empty()


def mostrar_estado():
    """Muestra el estado de la partida desde el JSON."""
    with panel_estado.container():
        if not st.session_state.id_partida:
            st.info(
                "Sin partida activa. Podés empezar una con **/nueva** o abrir una "
                "guardada desde la lista de chats."
            )
            return

        try:
            estado = consultar_estado(st.session_state.id_partida)
        except (ValueError, OSError):
            st.warning("No se pudo leer el estado de la partida.")
            return

        st.write(f"**Capítulos escritos:** {len(estado['capitulos'])}/5")
        if estado["finalizada"]:
            st.success("Historia terminada")

        st.write("**Inventario**")
        st.write("\n".join(f"- {o}" for o in estado["inventario"]) or "_vacío_")
        st.write("**Pistas**")
        st.write(
            "\n".join(f"- {p}" for p in estado["pistas_descubiertas"]) or "_ninguna_"
        )

        contexto = estado.get("contexto_narrativo", {})
        with st.expander("Contexto narrativo guardado", expanded=False):
            st.write(
                f"**Ubicación:** {contexto.get('ubicacion_actual') or 'Sin definir'}"
            )
            st.write("**Hechos establecidos**")
            st.write(
                "\n".join(f"- {h}" for h in contexto.get("hechos_establecidos", []))
                or "_ninguno_"
            )
            st.write("**Misterios pendientes**")
            st.write(
                "\n".join(f"- {m}" for m in contexto.get("misterios_pendientes", []))
                or "_ninguno_"
            )


mostrar_estado()


def cantidad_de_capitulos():
    if not st.session_state.id_partida:
        return 0
    try:
        return len(consultar_estado(st.session_state.id_partida)["capitulos"])
    except (ValueError, OSError):
        return 0


def respuesta_de_respaldo(capitulos_antes):
    """Recupera el capítulo si el modelo no devolvió texto."""
    if not st.session_state.id_partida:
        return ""
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return ""
    return capitulo_de_respaldo(capitulos_antes, estado) or ""


def imagenes_nuevas():
    """Obtiene imágenes que todavía no fueron mostradas."""
    if not st.session_state.id_partida:
        return []
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return []

    nuevas = []
    for capitulo in estado["capitulos"]:
        if capitulo["numero"] in st.session_state.imagenes_mostradas:
            continue
        fotos = imagen_de_capitulo(capitulo)
        if not fotos:
            continue
        st.session_state.imagenes_mostradas.add(capitulo["numero"])
        nuevas.extend(fotos)
    return nuevas


def dibujar_paso(paso):
    """Muestra razonamiento, llamada a una tool o resultado."""
    if paso["tipo"] == "razonamiento":
        with st.expander("💭 Razonamiento", expanded=True):
            st.caption(
                "  \n".join(linea.strip() for linea in paso["texto"].splitlines())
            )
    elif paso["tipo"] == "tool":
        st.write(f"🔧 Tool: **{paso['nombre']}**")
        st.json(paso["args"], expanded=False)
    elif paso["tipo"] == "resultado":
        st.write(f"✅ Resultado de **{paso['nombre']}**")
        st.code(paso["texto"])


def preparar_respuesta(respuesta, capitulos_antes):
    """Muestra el texto guardado; nunca duplica las opciones de los botones."""
    if not st.session_state.id_partida:
        return respuesta
    try:
        estado = consultar_estado(st.session_state.id_partida)
        if len(estado["capitulos"]) > capitulos_antes:
            capitulo = estado["capitulos"][-1]
            if capitulo["opciones"]:
                titulo = f"**Capítulo {capitulo['numero']}: {capitulo['titulo']}**"
                return f"{titulo}\n\n{capitulo['texto']}"
    except (ValueError, OSError):
        pass
    return respuesta


def turno_del_agente(mensaje_para_el_modelo):
    """Corre un turno del agente, lo muestra y lo guarda en el historial visible.

    `mensaje_para_el_modelo` es lo que llega al LLM; para los turnos sintéticos
    (como el de /nueva) no es texto del usuario y no se muestra en el transcript.
    Al final del turno aplica el cambio de partida que el agente haya propuesto.
    """
    with st.chat_message("assistant"):
        respuesta = ""
        pasos = []
        mensajes_del_turno = []
        capitulos_antes = cantidad_de_capitulos()

        with st.container(border=True), st.spinner("El agente está trabajando..."):
            try:
                for evento in st.session_state.agente.stream(
                    {"messages": [{"role": "user", "content": mensaje_para_el_modelo}]},
                    {"configurable": {"thread_id": st.session_state.id_chat}},
                    context=ContextoPartida(id_partida=st.session_state.id_partida),
                    stream_mode="updates",
                ):
                    for salida_nodo in evento.values():
                        for mensaje in salida_nodo.get("messages", []):
                            mensajes_del_turno.append(mensaje)
                            for paso in pasos_de_mensaje(mensaje):
                                pasos.append(paso)
                                dibujar_paso(paso)
                            if (
                                isinstance(mensaje, AIMessage)
                                and mensaje.text
                                and not mensaje.tool_calls
                            ):
                                respuesta = mensaje.text
            except Exception as exc:
                respuesta = f"Ocurrió un error: `{type(exc).__name__}: {exc}`"

        if not respuesta:
            respuesta = respuesta_de_respaldo(capitulos_antes)
        respuesta = preparar_respuesta(respuesta, capitulos_antes)
        st.markdown(respuesta or "El agente no produjo una respuesta de texto.")

        imagenes = imagenes_nuevas()
        for url, pie in imagenes:
            st.image(url, caption=pie)

    st.session_state.historial_visible.append(("assistant", respuesta, imagenes, pasos))

    cambio = cambio_de_sesion(mensajes_del_turno)
    if cambio:
        aplicar_cambio_del_agente(cambio)

    mostrar_estado()
    st.rerun()


# El saludo solo abre el chat la primera vez; no viaja al agente.
if not st.session_state.historial_visible:
    st.session_state.historial_visible.append(
        ("assistant", comandos_chat.saludo_inicial(), [], [])
    )

# Historial de mensajes que se muestra en Streamlit
for rol, contenido, imagenes, pasos in st.session_state.historial_visible:
    with st.chat_message(rol):
        if pasos:
            with st.container(border=True):
                for paso in pasos:
                    dibujar_paso(paso)
        st.markdown(contenido)
        for url, pie in imagenes:
            st.image(url, caption=pie)


# Botones de decisión del último capítulo pendiente
opcion_elegida = None
solicitud_reintento = None
estado_actual = None
if st.session_state.id_partida:
    try:
        estado_actual = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        estado_actual = None

if estado_actual:
    capitulo_pendiente = (
        not estado_actual["finalizada"]
        and bool(estado_actual["capitulos"])
        and len(estado_actual["capitulos"]) == estado_actual["capitulo_actual"] + 1
    )
    if capitulo_pendiente:
        capitulo = estado_actual["capitulos"][-1]
        st.write("**¿Qué querés hacer?**")
        for i, opcion in enumerate(capitulo["opciones"], start=1):
            if st.button(
                f"{i}. {opcion}",
                key=f"opcion_{st.session_state.id_partida}_{capitulo['numero']}_{i}",
                use_container_width=True,
            ):
                opcion_elegida = str(i)

    elif (
        not estado_actual["finalizada"]
        and estado_actual["capitulo_actual"] > 0
        and len(estado_actual["capitulos"]) == estado_actual["capitulo_actual"]
    ):
        st.warning(
            "La última decisión está guardada, pero falta "
            "generar el capítulo siguiente."
        )

        if st.button(
            "Reintentar capítulo pendiente",
            key=f"reintentar_{st.session_state.id_partida}",
            use_container_width=True,
        ):
            solicitud_reintento = (
                "Continuá la historia desde el estado guardado. "
                "La última decisión YA fue registrada en el JSON. "
                "NO vuelvas a llamar registrar_decision. "
                "Primero consultá el estado de la partida. "
                "Después consultá el contexto narrativo necesario "
                "y generá el próximo capítulo usando guardar_capitulo. "
                "No repitas capítulos anteriores. "
                "Si es el capítulo 5, generá también la imagen y el PDF."
            )

mensaje_escrito = st.chat_input("Escribí tu mensaje o un comando (/ayuda)...")
pregunta = opcion_elegida or solicitud_reintento or mensaje_escrito

# Botones del sidebar y comandos del chat: mismos caminos.
if nuevo_chat_pedida:
    ejecutar_nuevo_chat()

if retomar_pedida:
    if abrir_chat_de_partida(retomar_pedida):
        st.rerun()

if pregunta:
    st.session_state.historial_visible.append(("user", pregunta, [], []))
    with st.chat_message("user"):
        st.markdown(pregunta)

    # Comandos deterministas: se resuelven acá, sin llamar al agente.
    comando = comandos_chat.parsear_comando(pregunta)

    if comando == "ayuda":
        st.session_state.historial_visible.append(
            ("assistant", comandos_chat.texto_ayuda(), [], [])
        )
        st.rerun()

    if comando == "partidas":
        abiertas = listar_partidas_abiertas(limite=comandos_chat.LIMITE_PARTIDAS)
        st.session_state.historial_visible.append(
            ("assistant", comandos_chat.formatear_listado(abiertas), [], [])
        )
        st.session_state.listado_pendiente = abiertas
        st.rerun()

    if comando == "nueva":
        ejecutar_nueva_partida()

    # Elección numérica sobre un listado pendiente: se abre en un chat nuevo (S3).
    listado = st.session_state.listado_pendiente or []
    eleccion = comandos_chat.eleccion_numerica(pregunta, len(listado))
    if listado:
        st.session_state.listado_pendiente = None
        if eleccion:
            if abrir_chat_de_partida(listado[eleccion - 1]["id_partida"]):
                st.rerun()
            st.stop()

    # Cualquier otro texto va al agente en lenguaje natural.
    turno_del_agente(pregunta)
