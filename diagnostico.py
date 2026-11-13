"""Diagnóstico de respuestas vacías del modelo.

Algunos modelos (visto con nemotron-3-ultra) a veces devuelven un AIMessage sin
tool_calls y sin texto, con la llamada a la tool escrita dentro del razonamiento.
Para entender qué llegó, se guarda el mensaje crudo en logs/<fecha-hora>.json.
"""

import json
from datetime import datetime
from pathlib import Path

CARPETA_LOGS = Path(__file__).parent / "logs"


def es_respuesta_vacia(mensaje):
    """Sin tool_calls y sin texto: el agente no tiene con qué seguir."""
    return not mensaje.tool_calls and not mensaje.text.strip()


def guardar_mensaje_crudo(mensaje):
    """Guarda el AIMessage tal como llegó y devuelve la ruta del JSON."""
    CARPETA_LOGS.mkdir(exist_ok=True)
    ruta = CARPETA_LOGS / f"{datetime.now():%Y-%m-%d_%H-%M-%S-%f}.json"
    datos = {
        "content": mensaje.content,
        "additional_kwargs": mensaje.additional_kwargs,
        "response_metadata": mensaje.response_metadata,
        "tool_calls": mensaje.tool_calls,
        "invalid_tool_calls": mensaje.invalid_tool_calls,
    }
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return ruta
