"""Middleware propio de reintentos alrededor de cada llamada al modelo.

Problema que resuelve:
- Límites del proveedor (429): el catálogo gratuito de NVIDIA corta por cuota y
  sin reintento el turno se pierde. Se reintenta con espera exponencial.
- Errores transitorios: timeouts de lectura o conexión, conexiones caídas y
  respuestas 502/503/504 (visto: dos ReadTimeout seguidos contra
  integrate.api.nvidia.com). Misma espera exponencial que el 429.
- Respuestas vacías o mal formadas: con nemotron-3-ultra vimos un AIMessage sin
  tool_calls y sin texto, con la llamada a la tool escrita dentro del
  razonamiento. create_agent lo toma como respuesta final y el turno termina sin
  imagen ni texto. Se repite la misma llamada y, en el último intento, se le
  recuerda al modelo el formato de tool calling.

Por qué es código propio: la consigna pide justificar el middleware, y el
equivalente que trae NVIDIA forma parte de Deep Agents, que no se puede usar.
Se apoya solo en la API base de LangChain (AgentMiddleware.wrap_model_call), sin
middleware prearmado. Solo implementa la versión sync porque la app usa stream().
"""

import logging
import re
import time

import httpx
import openai
import requests

from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from diagnostico import es_respuesta_vacia, guardar_mensaje_crudo

log = logging.getLogger(__name__)

ESPERAS = (2, 4, 8)  # segundos antes de cada reintento por 429 o error transitorio
REINTENTOS_VACIA = 2
AVISO_FORMATO = (
    "Tu respuesta anterior salió vacía o con la llamada a la herramienta mal formada. "
    "Si ibas a usar una herramienta, llamala con el formato de tool calling; si no, respondé con texto."
)


# Timeouts y conexiones caídas: requests (ChatNVIDIA), httpx/openai (DeepSeek) y los de Python.
ERRORES_DE_RED = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    httpx.TimeoutException,
    httpx.NetworkError,
    openai.APIConnectionError,  # incluye APITimeoutError
    TimeoutError,
    ConnectionError,
)
CODIGOS_TRANSITORIOS = {502, 503, 504}


class ErrorLimiteProveedor(RuntimeError):
    """El proveedor siguió devolviendo 429 después de todos los reintentos."""


class ErrorProveedorNoResponde(RuntimeError):
    """El proveedor siguió con timeouts o errores 5xx después de todos los reintentos."""


def _codigo_http(error):
    """Código HTTP del error: status_code (openai/DeepSeek) o "[503] ..." en el texto (ChatNVIDIA)."""
    codigo = getattr(error, "status_code", None)
    if codigo is None and (coincidencia := re.search(r"\[(\d{3})\]", str(error))):
        codigo = int(coincidencia.group(1))
    return codigo


def es_error_de_limite(error):
    """429 en cualquiera de sus formas."""
    if _codigo_http(error) == 429:
        return True
    texto = str(error).lower()
    return "too many requests" in texto or "rate limit" in texto


def es_error_transitorio(error):
    """Timeout, conexión caída o 502/503/504: vale la pena reintentar."""
    return isinstance(error, ERRORES_DE_RED) or _codigo_http(error) in CODIGOS_TRANSITORIOS


def _motivo_error(error):
    """Motivo para el log si el error se reintenta, o None si hay que propagarlo."""
    if es_error_de_limite(error):
        return "límite del proveedor (429)"
    if es_error_transitorio(error):
        return f"error transitorio ({type(error).__name__})"
    return None


def _mensaje_ai(respuesta):
    if isinstance(respuesta, AIMessage):
        return respuesta
    if isinstance(respuesta, ModelResponse):
        return next((m for m in reversed(respuesta.result) if isinstance(m, AIMessage)), None)
    return None


def _motivo_mal_formada(mensaje):
    """Por qué la respuesta no sirve, o None si está bien."""
    if mensaje is None:
        return None
    if mensaje.invalid_tool_calls:
        return "tool call mal formada"
    if es_respuesta_vacia(mensaje):
        return "respuesta vacía"
    return None


class MiddlewareReintentos(AgentMiddleware):
    def __init__(self, dormir=time.sleep):
        super().__init__()
        self.dormir = dormir  # inyectable para que los tests no esperen de verdad

    def _llamar(self, request, handler):
        """Llama al modelo reintentando los 429 y los errores transitorios."""
        for intento, espera in enumerate((*ESPERAS, None), start=1):
            try:
                return handler(request)
            except Exception as error:
                motivo = _motivo_error(error)
                if motivo is None:
                    raise
                if espera is None:
                    if es_error_de_limite(error):
                        raise ErrorLimiteProveedor(
                            f"El proveedor sigue limitando los pedidos (429) después de {len(ESPERAS)} "
                            "reintentos. Esperá unos minutos o cambiá de modelo en el .env."
                        ) from error
                    raise ErrorProveedorNoResponde(
                        "El proveedor no respondió a tiempo; probá de nuevo en un minuto. "
                        f"(Último error: {type(error).__name__}, después de {len(ESPERAS)} reintentos)"
                    ) from error
                log.warning("Reintento %d/%d por %s; espero %ds", intento, len(ESPERAS), motivo, espera)
                self.dormir(espera)

    def wrap_model_call(self, request, handler):
        respuesta = self._llamar(request, handler)
        for intento in range(1, REINTENTOS_VACIA + 1):
            mensaje = _mensaje_ai(respuesta)
            motivo = _motivo_mal_formada(mensaje)
            if motivo is None:
                return respuesta
            guardar_mensaje_crudo(mensaje)
            log.warning("Reintento %d/%d por %s", intento, REINTENTOS_VACIA, motivo)
            pedido = request
            if intento == REINTENTOS_VACIA:
                # El aviso va solo en este pedido: no queda guardado en el historial.
                pedido = request.override(messages=[*request.messages, HumanMessage(AVISO_FORMATO)])
            respuesta = self._llamar(pedido, handler)
        mensaje = _mensaje_ai(respuesta)
        if motivo := _motivo_mal_formada(mensaje):
            guardar_mensaje_crudo(mensaje)
            log.error("La respuesta sigue con %s después de %d reintentos; se devuelve igual",
                      motivo, REINTENTOS_VACIA)
        return respuesta
