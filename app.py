"""Interfaz Streamlit para jugar, guardar y retomar historias de misterio."""

import uuid
from pathlib import Path

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
    url_de_imagen,
)
from herramientas import ContextoPartida
from imagenes import URL_UNSPLASH, con_utm
from pasos_agente import capitulo_de_respaldo, cambio_de_sesion, pasos_de_mensaje
from proveedores import proveedor_y_modelo

st.set_page_config(
    page_title="Historias interactivas", page_icon="📖", layout="centered"
)
st.title("Historias interactivas")
st.caption("Prototipo Unidad 5 · RAG + create_agent + SQLite")

# 1. Estado de la sesión: el chat y la partida tienen IDs diferentes.
for clave, valor in {
    "id_chat": uuid.uuid4().hex,
    "id_partida": "",
    "historial_visible": [],
    "imagenes_mostradas": set(),
    "listado_pendiente": None,
    "eliminar_pendiente": None,
}.items():
    if clave not in st.session_state:
        st.session_state[clave] = valor

if "agente" not in st.session_state:
    try:
        st.session_state.agente = crear_agente()
    except Exception as exc:
        st.error(str(exc))
        st.stop()


def leer_partida(id_partida):
    """Lee un JSON sin interrumpir Streamlit si no existe o es inválido."""
    if not id_partida:
        return None
    try:
        return consultar_estado(id_partida)
    except (ValueError, OSError):
        return None


def agregar_mensaje(rol, texto, imagenes=None, pasos=None):
    st.session_state.historial_visible.append((rol, texto, imagenes or [], pasos or []))


def iniciar_chat(id_partida):
    """Activa la partida y abre un nuevo hilo del agente."""
    st.session_state.id_chat = uuid.uuid4().hex
    st.session_state.id_partida = id_partida
    st.session_state.listado_pendiente = None
    st.session_state.imagenes_mostradas = set()


# 2. Imágenes, historial y partidas guardadas.
def imagen_de_capitulo(capitulo):
    imagen = capitulo.get("imagen")
    url = url_de_imagen(capitulo) if imagen else None
    if not url:
        return []
    pie = (
        f"Foto: [{imagen['autor']}]({con_utm(imagen['url_autor'])}) / "
        f"[Unsplash]({con_utm(URL_UNSPLASH)})"
    )
    return [(url, pie)]


def reconstruir_historial(estado):
    historial, mostradas = [], set()
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
    if not CARPETA_PARTIDAS.exists():
        return []
    archivos = sorted(
        CARPETA_PARTIDAS.glob("*.json"),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )
    return [ruta.stem for ruta in archivos]


def estado_retomable(id_partida):
    estado = leer_partida(id_partida)
    return estado if estado and not estado["finalizada"] else None


def abrir_chat_de_partida(id_partida):
    """Retoma una partida reconstruyendo sus capítulos desde el JSON."""
    estado = leer_partida(id_partida)
    if estado is None:
        st.error(f"No se pudo abrir la partida `{id_partida[:8]}`.")
        return False

    iniciar_chat(id_partida)
    st.session_state.historial_visible = [
        (
            "assistant",
            f"Abriste la partida `{id_partida[:8]}` "
            "en un chat nuevo — así venía la historia:",
            [],
            [],
        )
    ]
    historial, mostradas = reconstruir_historial(estado)
    st.session_state.historial_visible.extend(historial)
    st.session_state.imagenes_mostradas = mostradas
    return True


def aplicar_cambio_del_agente(cambio):
    """La tool propone el cambio; Streamlit lo aplica al finalizar el turno."""
    id_partida = cambio["id_partida"]
    if cambio["accion"] == "retomar":
        if estado_retomable(id_partida) is not None:
            abrir_chat_de_partida(id_partida)
    elif cambio["accion"] == "nueva" and leer_partida(id_partida) is not None:
        iniciar_chat(id_partida)


def continuar_con_partida_actual():
    st.session_state.listado_pendiente = None
    estado = estado_retomable(st.session_state.id_partida)
    hay_opciones = (
        estado is not None
        and bool(estado["capitulos"])
        and len(estado["capitulos"]) == estado["capitulo_actual"] + 1
    )
    mensaje = (
        "Volvemos a la partida actual. Estas son las tres opciones que tenés pendientes:"
        if hay_opciones
        else "Volvemos a la partida actual. Por ahora no hay decisiones pendientes."
    )
    agregar_mensaje("assistant", mensaje)
    st.rerun()


# 3. Crear una historia o un chat vacío.
INSTRUCCION_CAPITULO_1 = (
    "The application already created the game session and set it as the "
    "active game. Begin chapter 1 now following the mandatory workflow."
)


def partida_sin_capitulos():
    estado = leer_partida(st.session_state.id_partida)
    return estado is not None and not estado["capitulos"]


def mensaje_de_bienvenida(id_partida):
    return (
        f"¡Hola! Te abrí un chat nuevo con una partida lista (`{id_partida[:8]}`). "
        "Todavía no escribí nada: la historia arranca cuando vos me lo pidas.\n\n"
        "Decime **«empezá»** cuando quieras arrancar, "
        "o **/ayuda** para ver todo lo que puedo hacer."
    )


def ejecutar_nueva_partida():
    """Un 'empezá' genera el capítulo 1 en el mismo turno."""
    if partida_sin_capitulos():
        turno_del_agente(INSTRUCCION_CAPITULO_1)
        return

    id_partida = crear_partida()
    iniciar_chat(id_partida)
    nota = (
        f"Listo, te abrí un chat nuevo con una partida nueva (`{id_partida[:8]}`) "
        "y ya te arranco con el capítulo 1."
    )
    st.session_state.historial_visible = [("assistant", nota, [], [])]
    with st.chat_message("assistant"):
        st.markdown(nota)
    turno_del_agente(INSTRUCCION_CAPITULO_1)


def ejecutar_nuevo_chat():
    id_partida = crear_partida()
    iniciar_chat(id_partida)
    st.session_state.historial_visible = [
        ("assistant", mensaje_de_bienvenida(id_partida), [], [])
    ]
    st.rerun()


# 4. Barra lateral: elegir, renombrar o borrar partidas.
def entradas_del_sidebar():
    entradas = []
    for id_partida in partidas_guardadas():
        estado = leer_partida(id_partida)
        if estado is None:
            continue
        capitulos = estado["capitulos"]
        titulo = estado.get("nombre_chat") or (
            capitulos[-1]["titulo"] if capitulos else "Partida nueva"
        )
        entradas.append(
            {
                "id_partida": id_partida,
                "capitulos": len(capitulos),
                "titulo": titulo,
                "finalizada": estado["finalizada"],
            }
        )
    return entradas


def dibujar_lista_de_chats():
    elegida = None
    entradas = entradas_del_sidebar()
    if not entradas:
        st.caption("Todavía no hay partidas guardadas.")
        return None

    for entrada in entradas:
        id_partida = entrada["id_partida"]
        es_activa = id_partida == st.session_state.id_partida
        detalle = f"{entrada['capitulos']} de {TOTAL_CAPITULOS} capítulos"
        if entrada["finalizada"]:
            detalle += " · terminada"
        titulo = entrada["titulo"]
        if len(titulo) > 16:
            titulo = titulo[:15].rstrip() + "…"
        etiqueta = f"{'▶ ' if es_activa else ''}{id_partida[:8]} · {titulo}"

        col_chat, col_borrar = st.columns([3.5, 1.5], gap="small")
        with col_chat:
            if (
                st.button(
                    etiqueta,
                    key=f"chat_{id_partida}",
                    help=f"{entrada['titulo']} — {detalle}\nID: {id_partida}",
                    type="primary" if es_activa else "secondary",
                    use_container_width=True,
                )
                and not es_activa
            ):
                elegida = id_partida

        with col_borrar:
            if st.button(
                "Borrar",
                icon=":material/delete:",
                key=f"eliminar_{id_partida}",
                help="Eliminar este chat y su partida guardada",
                type="tertiary",
                use_container_width=True,
            ):
                st.session_state.eliminar_pendiente = id_partida
                st.rerun()

        if st.session_state.eliminar_pendiente == id_partida:
            st.warning("¿Eliminar este chat? Se borrará su partida guardada.")
            col_si, col_no = st.columns(2)
            with col_si:
                if st.button(
                    "Sí, eliminar", key=f"si_{id_partida}", use_container_width=True
                ):
                    try:
                        (CARPETA_PARTIDAS / f"{id_partida}.json").unlink()
                    except OSError as exc:
                        st.error(f"No se pudo eliminar la partida: {exc}")
                    else:
                        st.session_state.eliminar_pendiente = None
                        st.session_state.listado_pendiente = None
                        if es_activa:
                            st.session_state.id_partida = ""
                            st.session_state.id_chat = uuid.uuid4().hex
                            st.session_state.historial_visible = [
                                ("assistant", comandos_chat.saludo_inicial(), [], [])
                            ]
                            st.session_state.imagenes_mostradas = set()
                        st.rerun()
            with col_no:
                if st.button(
                    "Cancelar", key=f"no_{id_partida}", use_container_width=True
                ):
                    st.session_state.eliminar_pendiente = None
                    st.rerun()
    return elegida


def mostrar_estado():
    """Muestra capítulos, inventario, pistas y contexto guardado."""
    with panel_estado.container():
        estado = leer_partida(st.session_state.id_partida)
        if estado is None:
            if st.session_state.id_partida:
                st.warning("No se pudo leer el estado de la partida.")
            else:
                st.info(
                    "Sin partida activa. Podés empezar una con **/nueva** "
                    "o abrir una guardada desde la lista de chats."
                )
            return

        st.write(
            f"**Capítulos escritos:** {len(estado['capitulos'])}/{TOTAL_CAPITULOS}"
        )
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


with st.sidebar:
    st.write("**Partida actual**")
    if st.session_state.id_partida:
        id_actual = st.session_state.id_partida
        st.code(id_actual[:8])
        estado_nombre = leer_partida(id_actual)
        if estado_nombre is not None:
            capitulos = estado_nombre["capitulos"]
            nombre_actual = estado_nombre.get("nombre_chat") or (
                capitulos[-1]["titulo"] if capitulos else "Partida nueva"
            )
            with st.expander("Renombrar chat actual"):
                nuevo_nombre = st.text_input(
                    "Nombre del chat",
                    value=nombre_actual,
                    key=f"nombre_chat_{id_actual}",
                    max_chars=60,
                )
                if st.button(
                    "Guardar nombre",
                    key=f"guardar_nombre_{id_actual}",
                    use_container_width=True,
                ):
                    if nuevo_nombre.strip():
                        estado_nombre["nombre_chat"] = nuevo_nombre.strip()
                        estado_partida.guardar_estado(estado_nombre)
                        st.rerun()
                    else:
                        st.warning("El nombre no puede estar vacío.")
    else:
        st.info("Sin partida activa")

    nuevo_chat_pedida = st.button("Nuevo chat", use_container_width=True)
    st.caption(
        "Crea un chat con una partida nueva en blanco; "
        "la historia arranca cuando se lo pedís."
    )
    st.write("**Chats**")
    retomar_pedida = dibujar_lista_de_chats()
    proveedor, modelo = proveedor_y_modelo()
    st.caption(f"**Modelo:** {proveedor} · `{modelo}`")
    st.info(
        "Los capítulos, las decisiones y el contexto narrativo se guardan "
        "en JSON. La memoria del agente se guarda en SQLite dentro de partidas/."
    )
    panel_estado = st.empty()

mostrar_estado()


# 5. El turno del agente: streaming, tools, imágenes y respuesta.
def cantidad_de_capitulos():
    estado = leer_partida(st.session_state.id_partida)
    return len(estado["capitulos"]) if estado else 0


def respuesta_de_respaldo(capitulos_antes):
    estado = leer_partida(st.session_state.id_partida)
    if estado is None:
        return ""
    return capitulo_de_respaldo(capitulos_antes, estado) or ""


def imagenes_nuevas():
    estado = leer_partida(st.session_state.id_partida)
    if estado is None:
        return []
    nuevas = []
    for capitulo in estado["capitulos"]:
        if capitulo["numero"] not in st.session_state.imagenes_mostradas:
            fotos = imagen_de_capitulo(capitulo)
            if fotos:
                st.session_state.imagenes_mostradas.add(capitulo["numero"])
                nuevas.extend(fotos)
    return nuevas


def dibujar_paso(paso):
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
    estado = leer_partida(st.session_state.id_partida)
    if estado and len(estado["capitulos"]) > capitulos_antes:
        capitulo = estado["capitulos"][-1]
        if capitulo["opciones"]:
            return f"**Capítulo {capitulo['numero']}: {capitulo['titulo']}**\n\n{capitulo['texto']}"
    return respuesta


def turno_del_agente(mensaje_para_el_modelo):
    """Ejecuta el agente sin alterar su flujo de streaming."""
    with st.chat_message("assistant"):
        respuesta, pasos, mensajes_del_turno = "", [], []
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

    agregar_mensaje("assistant", respuesta, imagenes, pasos)
    cambio = cambio_de_sesion(mensajes_del_turno)
    if cambio:
        aplicar_cambio_del_agente(cambio)
    mostrar_estado()
    st.rerun()


# 6. Mostrar historial, decisiones, PDF y procesar entradas.
if not st.session_state.historial_visible:
    agregar_mensaje("assistant", comandos_chat.saludo_inicial())

for rol, contenido, imagenes, pasos in st.session_state.historial_visible:
    with st.chat_message(rol):
        if pasos:
            with st.container(border=True):
                for paso in pasos:
                    dibujar_paso(paso)
        st.markdown(contenido)
        for url, pie in imagenes:
            st.image(url, caption=pie)

seleccion_menu = None
if st.session_state.listado_pendiente is not None:
    st.write("**Elegí una partida:**")
    for numero, partida in enumerate(st.session_state.listado_pendiente, start=1):
        estado_texto = " · terminada" if partida["finalizada"] else ""
        etiqueta = (
            f"{numero}. {partida['titulo']} "
            f"({partida['capitulos']}/{TOTAL_CAPITULOS} capítulos){estado_texto}"
        )
        if st.button(
            etiqueta,
            key=f"menu_partida_{partida['id_partida']}",
            use_container_width=True,
        ):
            seleccion_menu = partida["id_partida"]
    if st.button(
        "4. Continuar con partida actual",
        key="menu_continuar_actual",
        use_container_width=True,
    ):
        seleccion_menu = "actual"

opcion_elegida = None
solicitud_reintento = None
estado_actual = leer_partida(st.session_state.id_partida)
if estado_actual and st.session_state.listado_pendiente is None:
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
            "La última decisión está guardada, pero falta generar el capítulo siguiente."
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

if estado_actual and estado_actual["finalizada"]:
    ruta_pdf = Path("historias_generadas") / f"{st.session_state.id_partida}.pdf"
    if ruta_pdf.exists():
        st.download_button(
            "Descargar historia en PDF",
            data=ruta_pdf.read_bytes(),
            file_name=ruta_pdf.name,
            mime="application/pdf",
            use_container_width=True,
        )

mensaje_escrito = st.chat_input("Escribí tu mensaje o un comando (/ayuda)...")
pregunta = opcion_elegida or solicitud_reintento or mensaje_escrito

if nuevo_chat_pedida:
    ejecutar_nuevo_chat()
if retomar_pedida and abrir_chat_de_partida(retomar_pedida):
    st.rerun()
if seleccion_menu == "actual":
    continuar_con_partida_actual()
elif seleccion_menu is not None and abrir_chat_de_partida(seleccion_menu):
    st.rerun()

if pregunta:
    agregar_mensaje("user", pregunta)
    with st.chat_message("user"):
        st.markdown(pregunta)

    comando = comandos_chat.parsear_comando(pregunta)
    pedidos_de_inicio = {
        "empeza",
        "empezá",
        "arranca",
        "arrancá",
        "comenza",
        "comenzá",
        "juguemos",
        "jugemos",
        "quiero jugar",
        "quiero empezar",
        "empeza la historia",
        "empezá la historia",
    }
    mensaje_normalizado = pregunta.strip().lower().rstrip("!. ")
    if (
        comando is None
        and mensaje_normalizado in pedidos_de_inicio
        and (not st.session_state.id_partida or partida_sin_capitulos())
    ):
        ejecutar_nueva_partida()
        st.stop()

    if comando == "ayuda":
        agregar_mensaje("assistant", comandos_chat.texto_ayuda())
        st.rerun()

    if comando == "partidas":
        partidas = [
            p
            for p in entradas_del_sidebar()
            if p["id_partida"] != st.session_state.id_partida
        ][:3]
        st.session_state.listado_pendiente = partidas
        mensaje = (
            "Estas son tus últimas partidas guardadas. Elegí una para abrirla "
            "o seleccioná **4. Continuar con partida actual**."
            if partidas
            else "No hay otras partidas guardadas. Podés elegir "
            "**4. Continuar con partida actual**."
        )
        agregar_mensaje("assistant", mensaje)
        st.rerun()

    if comando == "nueva":
        ejecutar_nueva_partida()

    listado = st.session_state.listado_pendiente
    if listado is not None:
        eleccion = comandos_chat.eleccion_numerica(pregunta, 4)
        if eleccion == 4:
            continuar_con_partida_actual()
        elif eleccion is not None and eleccion <= len(listado):
            id_elegida = listado[eleccion - 1]["id_partida"]
            if abrir_chat_de_partida(id_elegida):
                st.rerun()
            st.stop()
        else:
            agregar_mensaje(
                "assistant",
                "Elegí una de las partidas disponibles "
                "o la opción **4. Continuar con partida actual**.",
            )
            st.rerun()

    turno_del_agente(pregunta)
