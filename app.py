"""Interfaz Streamlit del prototipo: chat, memoria y logs de tools en vivo."""
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from agente import crear_agente

st.set_page_config(page_title="Historias interactivas", page_icon="📖", layout="centered")
st.title("📖 Historias interactivas")
st.caption("Prototipo Unidad 5 · RAG + create_agent + checkpointer")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "historial_visible" not in st.session_state:
    st.session_state.historial_visible = []
if "agente" not in st.session_state:
    try:
        st.session_state.agente = crear_agente()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

with st.sidebar:
    st.write("**Partida actual**")
    st.code(st.session_state.thread_id[:8])
    if st.button("Nueva partida"):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.historial_visible = []
        st.rerun()
    st.info("La memoria del prototipo dura mientras está abierta la sesión de Streamlit.")

for rol, contenido in st.session_state.historial_visible:
    with st.chat_message(rol):
        st.markdown(contenido)

pregunta = st.chat_input("Ej.: Empezá una historia de misterio en la mansión")
if pregunta:
    st.session_state.historial_visible.append(("user", pregunta))
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        respuesta = ""
        with st.status("El agente está trabajando...", expanded=True) as status:
            try:
                for evento in st.session_state.agente.stream(
                    {"messages": [{"role": "user", "content": pregunta}]},
                    {"configurable": {"thread_id": st.session_state.thread_id}},
                    stream_mode="updates",
                ):
                    for salida_nodo in evento.values():
                        for mensaje in salida_nodo.get("messages", []):
                            if isinstance(mensaje, AIMessage):
                                for llamada in mensaje.tool_calls:
                                    st.write(f"🔧 Tool: **{llamada['name']}**")
                                    st.json(llamada.get("args", {}), expanded=False)
                                if mensaje.content and not mensaje.tool_calls:
                                    respuesta = str(mensaje.content)
                            elif isinstance(mensaje, ToolMessage):
                                st.write(f"✅ Resultado de **{mensaje.name}**")
                                st.code(str(mensaje.content)[:900])
                status.update(label="Ejecución terminada", state="complete")
            except Exception as exc:
                respuesta = f"Ocurrió un error: `{type(exc).__name__}: {exc}`"
                status.update(label="Error en el agente", state="error")
        st.markdown(respuesta or "El agente no produjo una respuesta de texto.")
    st.session_state.historial_visible.append(("assistant", respuesta))
