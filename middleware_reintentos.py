"""Middleware propio de reintentos alrededor de cada llamada al modelo.

Problema que resuelve:
- Límites del proveedor (429): el catálogo gratuito de NVIDIA corta por cuota y
  sin reintento el turno se pierde. Se reintenta con espera exponencial.
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
import time

from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from diagnostico import es_respuesta_vacia, guardar_mensaje_crudo

log = logging.getLogger(__name__)

ESPERAS_LIMITE = (2, 4, 8)  # segundos antes de cada reintento por 429
REINTENTOS_VACIA = 2
AVISO_FORMATO = (
    "Tu respuesta anterior salió vacía o con la llamada a la herramienta mal formada. "
    "Si ibas a usar una herramienta, llamala con el formato de tool calling; si no, respondé con texto."
)


class ErrorLimiteProveedor(RuntimeError):
    """El proveedor siguió devolviendo 429 después de todos los reintentos."""


def es_error_de_limite(error):
    """429 en cualquiera de sus formas: status_code (openai/DeepSeek) o "[429] ..." (ChatNVIDIA)."""
    if getattr(error, "status_code", None) == 429:
        return True
    texto = str(error).lower()
    return "[429]" in texto or "too many requests" in texto or "rate limit" in texto


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
        """Llama al modelo reintentando solo los errores de límite."""
        for intento, espera in enumerate((*ESPERAS_LIMITE, None), start=1):
            try:
                return handler(request)
            except Exception as error:
                if not es_error_de_limite(error):
                    raise
                if espera is None:
                    raise ErrorLimiteProveedor(
                        f"El proveedor sigue limitando los pedidos (429) después de {len(ESPERAS_LIMITE)} "
                        "reintentos. Esperá unos minutos o cambiá de modelo en el .env."
                    ) from error
                log.warning("Reintento %d/%d por límite del proveedor (429); espero %ds",
                            intento, len(ESPERAS_LIMITE), espera)
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
