"""Traduce los mensajes del agente a pasos para mostrar en la UI.

Vive fuera de app.py para poder testearlo sin Streamlit. Cada paso es un dict
serializable, así se guarda en st.session_state y se redibuja en el historial.
"""

from langchain_core.messages import AIMessage, ToolMessage


def extraer_razonamiento(mensaje):
    """Razonamiento de un AIMessage ("" si no trae).

    Los proveedores que usan bloques estándar lo dejan en content_blocks con
    type "reasoning"; otros (ChatNVIDIA, DeepSeek) en additional_kwargs["reasoning_content"].
    """
    bloques = [
        b["reasoning"] for b in mensaje.content_blocks
        if b.get("type") == "reasoning" and b.get("reasoning")
    ]
    return "\n\n".join(bloques) or mensaje.additional_kwargs.get("reasoning_content") or ""


def pasos_de_mensaje(mensaje):
    """Pasos de un mensaje, en orden: razonamiento → tool calls, o el resultado de una tool."""
    pasos = []
    if isinstance(mensaje, AIMessage):
        if razonamiento := extraer_razonamiento(mensaje):
            pasos.append({"tipo": "razonamiento", "texto": razonamiento})
        for llamada in mensaje.tool_calls:
            pasos.append({"tipo": "tool", "nombre": llamada["name"], "args": llamada.get("args", {})})
    elif isinstance(mensaje, ToolMessage):
        pasos.append({"tipo": "resultado", "nombre": mensaje.name, "texto": str(mensaje.content)[:900]})
    return pasos
