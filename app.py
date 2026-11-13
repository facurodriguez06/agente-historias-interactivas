"""Interfaz Streamlit del prototipo: chat, memoria y logs de tools en vivo."""
import streamlit as st
from langchain_core.messages import AIMessage
from agente import crear_agente
from estado_partida import consultar_estado, crear_partida, url_de_imagen
from herramientas import ContextoPartida
from imagenes import URL_UNSPLASH, con_utm
from pasos_agente import capitulo_de_respaldo, pasos_de_mensaje

st.set_page_config(page_title="Historias interactivas", page_icon="📖", layout="centered")
st.title("📖 Historias interactivas")
st.caption("Prototipo Unidad 5 · RAG + create_agent + checkpointer")

# Un solo identificador por partida: es el id del JSON y también el thread_id del checkpointer.
if "id_partida" not in st.session_state:
    st.session_state.id_partida = crear_partida()
# Cada entrada: (rol, texto, imagenes, pasos) con imagenes = [(url, pie de foto)] y
# pasos = razonamiento y tools del turno (ver pasos_agente.py), para redibujarlos en el historial.
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []
# Capítulos cuya imagen ya se mostró en el chat (para no repetirla)
if "imagenes_mostradas" not in st.session_state:
    st.session_state.imagenes_mostradas = set()
if "agente" not in st.session_state:
    try:
        st.session_state.agente = crear_agente()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

with st.sidebar:
    st.write("**Partida actual**")
    st.code(st.session_state.id_partida[:8])
    if st.button("Nueva partida"):
        st.session_state.id_partida = crear_partida()
        st.session_state.historial_visible = []
        st.session_state.imagenes_mostradas = set()
        st.rerun()
    st.info("La memoria de la conversación dura mientras está abierta la sesión de Streamlit; "
            "el estado de la partida se guarda en partidas/.")
    panel_estado = st.empty()


def mostrar_estado():
    """Resumen de la partida leído del JSON (se vuelve a dibujar al terminar cada turno)."""
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
        st.write("\n".join(f"- {p}" for p in estado["pistas_descubiertas"]) or "_ninguna_")


mostrar_estado()


def cantidad_de_capitulos():
    try:
        return len(consultar_estado(st.session_state.id_partida)["capitulos"])
    except (ValueError, OSError):
        return 0


def respuesta_de_respaldo(capitulos_antes):
    """Si el modelo no dio texto final pero guardó un capítulo, se muestra desde el JSON."""
    try:
        estado = consultar_estado(st.session_state.id_partida)
    except (ValueError, OSError):
        return ""
    return capitulo_de_respaldo(capitulos_antes, estado) or ""


def imagenes_nuevas():
    """Imágenes de capítulos que todavía no se mostraron: [(url, pie de foto)]. Se cargan por hotlinking."""
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
            f"Foto: [{imagen['autor']}]({con_utm(imagen['url_autor'])}) / "
            f"[Unsplash]({con_utm(URL_UNSPLASH)})"
        )
        nuevas.append((url, pie))
    return nuevas


def dibujar_paso(paso):
    """Un paso del turno: razonamiento, llamada a una tool o su resultado."""
    if paso["tipo"] == "razonamiento":
        with st.expander("💭 Razonamiento", expanded=True):
            # Un salto de línea por renglón y sin sangrías (que markdown tomaría por código).
            st.caption("  \n".join(linea.strip() for linea in paso["texto"].splitlines()))
    elif paso["tipo"] == "tool":
        st.write(f"🔧 Tool: **{paso['nombre']}**")
        st.json(paso["args"], expanded=False)
    elif paso["tipo"] == "resultado":
        st.write(f"✅ Resultado de **{paso['nombre']}**")
        st.code(paso["texto"])


for rol, contenido, imagenes, pasos in st.session_state.historial_visible:
    with st.chat_message(rol):
        if pasos:
            with st.container(border=True):
                for paso in pasos:
                    dibujar_paso(paso)
        st.markdown(contenido)
        for url, pie in imagenes:
            st.image(url, caption=pie)

pregunta = st.chat_input("Ej.: Empezá una historia de misterio en la mansión")
if pregunta:
    st.session_state.historial_visible.append(("user", pregunta, [], []))
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        respuesta = ""
        pasos = []
        capitulos_antes = cantidad_de_capitulos()
        # Contenedor y no st.status: st.status es un expander y no admite el del razonamiento adentro.
        with st.container(border=True), st.spinner("El agente está trabajando..."):
            try:
                for evento in st.session_state.agente.stream(
                    {"messages": [{"role": "user", "content": pregunta}]},
                    {"configurable": {"thread_id": st.session_state.id_partida}},
                    context=ContextoPartida(id_partida=st.session_state.id_partida),
                    stream_mode="updates",
                ):
                    for salida_nodo in evento.values():
                        for mensaje in salida_nodo.get("messages", []):
                            for paso in pasos_de_mensaje(mensaje):
                                pasos.append(paso)
                                dibujar_paso(paso)
                            if isinstance(mensaje, AIMessage) and mensaje.text and not mensaje.tool_calls:
                                respuesta = mensaje.text
            except Exception as exc:
                respuesta = f"Ocurrió un error: `{type(exc).__name__}: {exc}`"
        if not respuesta:
            respuesta = respuesta_de_respaldo(capitulos_antes)
        st.markdown(respuesta or "El agente no produjo una respuesta de texto.")
        imagenes = imagenes_nuevas()
        for url, pie in imagenes:
            st.image(url, caption=pie)
    st.session_state.historial_visible.append(("assistant", respuesta, imagenes, pasos))
    mostrar_estado()
