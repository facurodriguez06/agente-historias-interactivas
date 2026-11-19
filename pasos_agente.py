"""Traduce los mensajes del agente a pasos para mostrar en la UI.

Vive fuera de app.py para poder testearlo sin Streamlit. Cada paso es un dict
serializable, así se guarda en st.session_state y se redibuja en el historial.
"""

import json
import re

from langchain_core.messages import AIMessage, ToolMessage

_ID_PARTIDA = re.compile(r"[0-9a-f]{32}")


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


def capitulo_de_respaldo(capitulos_antes, estado):
    """Último capítulo guardado durante el turno, en el formato de la respuesta; None si no hubo.

    Red de seguridad para cuando el modelo guardó el capítulo pero terminó el turno sin texto.
    """
    if len(estado["capitulos"]) <= capitulos_antes:
        return None
    capitulo = estado["capitulos"][-1]
    partes = [f"**Capítulo {capitulo['numero']}: {capitulo['titulo']}**", capitulo["texto"]]
    if capitulo["opciones"]:
        partes.append("\n".join(f"{i}. {opcion}" for i, opcion in enumerate(capitulo["opciones"], start=1)))
    return "\n\n".join(partes)


def cambio_de_sesion(mensajes):
    """Cambio de partida que el agente propuso en un turno, o None si no propuso ninguno.

    La aplicación es la autoridad del switch: el agente solo lo propone con sus
    tools (retomar_partida por los args de la llamada, iniciar_nueva_partida
    por el id del resultado). Si el turno trae varios cambios, gana el último.
    Nada de esto levanta excepciones: una llamada rara se ignora y el turno
    termina como un turno común.
    """
    cambio = None
    for mensaje in mensajes:
        if isinstance(mensaje, AIMessage):
            for llamada in mensaje.tool_calls:
                if llamada.get("name") != "retomar_partida":
                    continue
                id_partida = (llamada.get("args") or {}).get("id_partida")
                if _id_valido(id_partida):
                    cambio = {"accion": "retomar", "id_partida": id_partida}
        elif isinstance(mensaje, ToolMessage):
            if mensaje.name not in ("iniciar_nueva_partida", "retomar_partida"):
                continue
            id_partida = _id_del_resultado(mensaje.content)
            if _id_valido(id_partida):
                accion = "nueva" if mensaje.name == "iniciar_nueva_partida" else "retomar"
                cambio = {"accion": accion, "id_partida": id_partida}
    return cambio


def _id_valido(id_partida):
    """Mismo criterio que estado_partida: uuid hex de 32 caracteres."""
    return isinstance(id_partida, str) and bool(_ID_PARTIDA.fullmatch(id_partida))


def _id_del_resultado(contenido):
    """id_partida del JSON que devuelve la tool, o None si no se puede leer."""
    if isinstance(contenido, (bytes, bytearray)):
        contenido = contenido.decode("utf-8", errors="replace")
    try:
        datos = json.loads(contenido) if isinstance(contenido, str) else contenido
    except (ValueError, TypeError):
        return None
    if not isinstance(datos, dict):
        return None
    return datos.get("id_partida")
