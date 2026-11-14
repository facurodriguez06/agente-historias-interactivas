"""Interfaz Streamlit: historias, memoria persistente y herramientas del agente."""

import streamlit as st
from langchain_core.messages import AIMessage

from agente import crear_agente
from estado_partida import (
    CARPETA_PARTIDAS,
    consultar_estado,
    crear_partida,
    url_de_imagen,
)
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
st.caption("Prototipo Unidad 5 · RAG + create_agent + SQLite")


if "id_partida" not in st.session_state:
    st.session_state.id_partida = crear_partida()

# Historial visible: (rol, texto, imagenes, pasos)
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []

if "imagenes_mostradas" not in st.session_state:
    st.session_state.imagenes_mostradas = set()

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


with st.sidebar:
    st.write("**Partida actual**")
    st.code(st.session_state.id_partida)

    if st.button("Nueva partida"):
        st.session_state.id_partida = crear_partida()
        st.session_state.historial_visible = []
        st.session_state.imagenes_mostradas = set()
        st.rerun()

    opciones_guardadas = partidas_guardadas()
    if opciones_guardadas:
        elegida = st.selectbox(
            "Retomar partida guardada",
            options=opciones_guardadas,
            format_func=lambda identificador: identificador[:8],
            index=0,
        )
        if st.button("Retomar esta partida"):
            try:
                estado_guardado = consultar_estado(elegida)
                historial, mostradas = reconstruir_historial(estado_guardado)
                st.session_state.id_partida = elegida
                st.session_state.historial_visible = historial
                st.session_state.imagenes_mostradas = mostradas
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(f"No se pudo retomar la partida: {exc}")

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
    try:
        return len(consultar_estado(st.session_state.id_partida)["capitulos"])
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

    elif (
        not estado["finalizada"]
        and estado["capitulo_actual"] > 0
        and len(estado["capitulos"]) == estado["capitulo_actual"]
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

except (ValueError, OSError):
    pass


mensaje_escrito = st.chat_input("Escribí tu mensaje...")
pregunta = opcion_elegida or solicitud_reintento or mensaje_escrito

if pregunta:
    st.session_state.historial_visible.append(("user", pregunta, [], []))
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        respuesta = ""
        pasos = []
        imagenes = []
        capitulos_antes = cantidad_de_capitulos()

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
    mostrar_estado()
    st.rerun()
