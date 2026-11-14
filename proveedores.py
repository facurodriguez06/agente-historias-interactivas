"""Fábrica de modelos de chat.

LangChain ya unifica la interfaz: ChatNVIDIA, ChatDeepSeek y ChatOpenRouter son
BaseChatModel, así que el agente los usa igual (invoke, bind_tools, etc.).
Este módulo solo decide cuál instanciar según el .env:

    LLM_PROVIDER=nvidia | deepseek | openrouter  (sin definir: deepseek)
    LLM_MODEL=<nombre del modelo>   (opcional; cada proveedor tiene un default)

Agregar un proveedor = una función _crear_<proveedor>(modelo) + una entrada
en PROVEEDORES.
"""

import os

from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

TEMPERATURA = 0.5
MAX_TOKENS = 2500
MAX_REINTENTOS = 2
TIMEOUT_POR_DEFECTO = (
    120  # segundos; ChatNVIDIA trae 60 y con modelos grandes no alcanza
)


def _exigir_clave(variable):
    if not os.getenv(variable):
        raise RuntimeError(f"Falta {variable} en el archivo .env")


def _timeout():
    """Timeout de cada llamada en segundos, desde LLM_TIMEOUT (default 120)."""
    valor = os.getenv("LLM_TIMEOUT", "").strip()
    if not valor:
        return TIMEOUT_POR_DEFECTO
    try:
        segundos = float(valor)
    except ValueError:
        segundos = 0
    if segundos <= 0:
        raise RuntimeError(
            f"LLM_TIMEOUT={valor!r} no es válido: tiene que ser un número de segundos mayor a 0"
        )
    return segundos


def _crear_nvidia(modelo):
    _exigir_clave("NVIDIA_API_KEY")
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    # ChatNVIDIA lee NVIDIA_API_KEY del entorno. No tiene max_retries, y
    # max_tokens está deprecado: el equivalente es max_completion_tokens.
    # timeout llega a requests (conexión y lectura de cada pedido).
    return ChatNVIDIA(
        model=modelo,
        temperature=TEMPERATURA,
        max_completion_tokens=MAX_TOKENS,
        timeout=_timeout(),
    )


def _crear_deepseek(modelo):
    _exigir_clave("DEEPSEEK_API_KEY")
    from langchain_deepseek import ChatDeepSeek

    return ChatDeepSeek(
        model=modelo,
        temperature=TEMPERATURA,
        max_tokens=MAX_TOKENS,
        max_retries=MAX_REINTENTOS,
        timeout=_timeout(),
    )


def _crear_openrouter(modelo):
    _exigir_clave("OPENROUTER_API_KEY")
    from langchain_openrouter import ChatOpenRouter

    return ChatOpenRouter(
        model=modelo,
        temperature=TEMPERATURA,
        max_tokens=MAX_TOKENS,
        max_retries=MAX_REINTENTOS,
        # A diferencia de los otros proveedores, OpenRouter recibe milisegundos.
        timeout=int(_timeout() * 1000),
    )


PROVEEDORES = {
    "nvidia": _crear_nvidia,
    "deepseek": _crear_deepseek,
    "openrouter": _crear_openrouter,
}
MODELOS_POR_DEFECTO = {
    "nvidia": "nvidia/nemotron-3-ultra-550b-a55b",
    "deepseek": "deepseek-flash",
    "openrouter": "deepseek/deepseek-v4.1-flash-1017",
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
