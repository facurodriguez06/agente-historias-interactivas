"""Fábrica de modelos de chat.

LangChain ya unifica la interfaz: ChatNVIDIA, ChatDeepSeek y el resto son
BaseChatModel, así que el agente los usa igual (invoke, bind_tools, etc.).
Este módulo solo decide cuál instanciar según el .env:

    LLM_PROVIDER=nvidia | deepseek  (sin definir: deepseek)
    LLM_MODEL=<nombre del modelo>   (opcional; cada proveedor tiene un default)

Agregar un proveedor = una función _crear_<proveedor>(modelo) + una entrada
en PROVEEDORES.
"""

import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

TEMPERATURA = 0.5
MAX_TOKENS = 1000
MAX_REINTENTOS = 2


def _exigir_clave(variable):
    if not os.getenv(variable):
        raise RuntimeError(f"Falta {variable} en el archivo .env")


def _crear_nvidia(modelo):
    _exigir_clave("NVIDIA_API_KEY")
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    # ChatNVIDIA lee NVIDIA_API_KEY del entorno. No tiene max_retries, y
    # max_tokens está deprecado: el equivalente es max_completion_tokens.
    return ChatNVIDIA(
        model=modelo,
        temperature=TEMPERATURA,
        max_completion_tokens=MAX_TOKENS,
    )


def _crear_deepseek(modelo):
    _exigir_clave("DEEPSEEK_API_KEY")
    from langchain_deepseek import ChatDeepSeek

    return ChatDeepSeek(
        model=modelo,
        temperature=TEMPERATURA,
        max_tokens=MAX_TOKENS,
        max_retries=MAX_REINTENTOS,
    )


PROVEEDORES = {"nvidia": _crear_nvidia, "deepseek": _crear_deepseek}
MODELOS_POR_DEFECTO = {
    "nvidia": "nvidia/nemotron-3-ultra-550b-a55b",
    "deepseek": "deepseek-flash",
}


def proveedor_y_modelo():
    """(proveedor, modelo) que se van a usar según el .env. No lee ni devuelve claves."""
    load_dotenv()
    # Sin LLM_PROVIDER se usa deepseek, como antes de existir este módulo.
    proveedor = (os.getenv("LLM_PROVIDER") or "deepseek").strip().lower()
    if proveedor not in PROVEEDORES:
        raise RuntimeError(
            f"LLM_PROVIDER={proveedor!r} no es válido. "
            f"Opciones: {', '.join(PROVEEDORES)}"
        )
    modelo = os.getenv("LLM_MODEL", "").strip() or MODELOS_POR_DEFECTO[proveedor]
    return proveedor, modelo


def obtener_modelo() -> BaseChatModel:
    proveedor, modelo = proveedor_y_modelo()
    return PROVEEDORES[proveedor](modelo)
