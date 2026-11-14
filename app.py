"""Interfaz Streamlit: historias, memoria y herramientas del agente."""

import streamlit as st
from langchain_core.messages import AIMessage

from agente import crear_agente
from estado_partida import consultar_estado, crear_partida, url_de_imagen
from herramientas import ContextoPartida
from imagenes import URL_UNSPLASH, con_utm
from pasos_agente import capitulo_de_respaldo, pasos_de_mensaje
from proveedores import proveedor_y_modelo

st.set_page_config(
    page_title="Historias interactivas",
    page_icon="📖",
    layout="centered",
)

st.title("Historias interactivas")
st.caption("Prototipo Unidad 5 · RAG + create_agent + checkpointer")


# Inicializar la partida
if "id_partida" not in st.session_state:
    st.session_state.id_partida = crear_partida()

# Historial visible: (rol, texto, imagenes, pasos)
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []

# Evitar mostrar la misma imagen dos veces
if "imagenes_mostradas" not in st.session_state:
    st.session_state.imagenes_mostradas = set()

# Crear el agente una sola vez por sesión
if "agente" not in st.session_state:
    try:
        st.session_state.agente = crear_agente()
    except Exception as exc:
        st.error(str(exc))
        st.stop()


# Panel lateral
with st.sidebar:
    st.write("**Partida actual**")
    st.code(st.session_state.id_partida[:8])

    if st.button("Nueva partida"):
        st.session_state.id_partida = crear_partida()
        st.session_state.historial_visible = []
        st.session_state.imagenes_mostradas = set()
        st.rerun()

    proveedor, modelo = proveedor_y_modelo()
    st.caption(f"**Modelo:** {proveedor} · `{modelo}`")

    st.info(
        "La memoria de la conversación dura mientras está abierta "
        "la sesión de Streamlit; el estado de la partida se guarda "
        "en partidas/."
    )

    panel_estado = st.empty()


def mostrar_estado():
    """Muestra el estado de la partida desde el JSON."""
    with panel_estado.container():
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


mostrar_estado()


def cantidad_de_capitulos():
    """Devuelve la cantidad de capítulos escritos."""
    try:
        estado = consultar_estado(st.session_state.id_partida)
        return len(estado["capitulos"])
    except (ValueError, OSError):
        return 0


def respuesta_de_respaldo(capitulos_antes):
    """Recupera el capítulo si el modelo no devolvió texto."""
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return ""

    return capitulo_de_respaldo(capitulos_antes, estado) or ""


def imagenes_nuevas():
    """Obtiene imágenes que todavía no fueron mostradas."""
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return []

    nuevas = []

    for capitulo in estado["capitulos"]:
        url = url_de_imagen(capitulo)

        if url is None or capitulo["numero"] in st.session_state.imagenes_mostradas:
            continue

        st.session_state.imagenes_mostradas.add(capitulo["numero"])

        imagen = capitulo["imagen"]

        pie = (
            f"Foto: [{imagen['autor']}]"
            f"({con_utm(imagen['url_autor'])}) / "
            f"[Unsplash]({con_utm(URL_UNSPLASH)})"
        )

        nuevas.append((url, pie))

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
    """
    Si se generó un capítulo con opciones, devuelve solamente
    el título y la narración guardados en el JSON.

    Las opciones se muestran por separado como botones.
    El capítulo final conserva la respuesta del modelo para
    poder mostrar también la información del PDF.
    """
    try:
        estado = consultar_estado(st.session_state.id_partida)

        if len(estado["capitulos"]) > capitulos_antes:
            capitulo = estado["capitulos"][-1]

            if capitulo["opciones"]:
                titulo = f"**Capítulo {capitulo['numero']}: " f"{capitulo['titulo']}**"

                return f"{titulo}\n\n{capitulo['texto']}"

    except (ValueError, OSError):
        pass

    return respuesta


# Mostrar el historial de la conversación
for rol, contenido, imagenes, pasos in st.session_state.historial_visible:
    with st.chat_message(rol):

        if pasos:
            with st.container(border=True):
                for paso in pasos:
                    dibujar_paso(paso)

        st.markdown(contenido)

        for url, pie in imagenes:
            st.image(url, caption=pie)


# Mostrar botones cuando hay un capítulo pendiente
opcion_elegida = None

try:
    estado = consultar_estado(st.session_state.id_partida)

    capitulo_pendiente = (
        not estado["finalizada"]
        and bool(estado["capitulos"])
        and len(estado["capitulos"]) == estado["capitulo_actual"] + 1
    )

    if capitulo_pendiente:
        capitulo = estado["capitulos"][-1]

        st.write("**¿Qué querés hacer?**")

        for i, opcion in enumerate(capitulo["opciones"], start=1):
            if st.button(
                f"{i}. {opcion}",
                key=(
                    f"opcion_{st.session_state.id_partida}_" f"{capitulo['numero']}_{i}"
                ),
                use_container_width=True,
            ):
                opcion_elegida = str(i)

except (ValueError, OSError):
    pass


# Mantener el chat para comenzar la historia o hacer preguntas
mensaje_escrito = st.chat_input("Escribí tu mensaje...")

# Los botones envían directamente el número de la opción
pregunta = opcion_elegida or mensaje_escrito


if pregunta:

    st.session_state.historial_visible.append(("user", pregunta, [], []))

    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):

        respuesta = ""
        pasos = []
        imagenes = []

        capitulos_antes = cantidad_de_capitulos()

        with (
            st.container(border=True),
            st.spinner("El agente está trabajando..."),
        ):
            try:
                for evento in st.session_state.agente.stream(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": pregunta,
                            }
                        ]
                    },
                    {"configurable": {"thread_id": st.session_state.id_partida}},
                    context=ContextoPartida(id_partida=st.session_state.id_partida),
                    stream_mode="updates",
                ):

                    for salida_nodo in evento.values():

                        for mensaje in salida_nodo.get("messages", []):

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
                respuesta = f"Ocurrió un error: " f"`{type(exc).__name__}: {exc}`"

        # Usar el capítulo guardado si el modelo no respondió
        if not respuesta:
            respuesta = respuesta_de_respaldo(capitulos_antes)

        # CAMBIO PRINCIPAL:
        # Mostrar solo la narración y no duplicar las opciones
        respuesta = preparar_respuesta(
            respuesta,
            capitulos_antes,
        )

        st.markdown(respuesta or "El agente no produjo una respuesta de texto.")

        imagenes = imagenes_nuevas()

        for url, pie in imagenes:
            st.image(url, caption=pie)

    # Guardar en el historial la respuesta ya corregida
    st.session_state.historial_visible.append(("assistant", respuesta, imagenes, pasos))

    mostrar_estado()

    st.rerun()
