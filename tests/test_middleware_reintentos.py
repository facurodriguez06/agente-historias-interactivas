"""Middleware de reintentos con un modelo falso dentro de create_agent (sin LLM ni red)."""

import logging

import pytest
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

import diagnostico
import middleware_reintentos as mr


class Error429(Exception):
    status_code = 429


class ModeloFalso(BaseChatModel):
    """Devuelve (o lanza, si es una excepción) cada elemento de `guion`, en orden."""

    guion: list
    recibidos: list = []

    @property
    def _llm_type(self):
        return "falso"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.recibidos.append(list(messages))
        if not self.guion:
            raise AssertionError("el modelo fue llamado más veces de las previstas")
        paso = self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return ChatResult(generations=[ChatGeneration(message=paso)])


@tool
def sumar(a: int, b: int) -> int:
    """Suma dos enteros."""
    return a + b


VACIO = AIMessage(content="", additional_kwargs={"reasoning_content": "function functionfunction..."})
TOOL_OK = AIMessage(content="", tool_calls=[{"name": "sumar", "args": {"a": 21, "b": 21}, "id": "t1"}])
FINAL = AIMessage(content="Da 42.")


@pytest.fixture(autouse=True)
def logs_temporales(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostico, "CARPETA_LOGS", tmp_path / "logs")
    return tmp_path / "logs"


def correr(guion):
    esperas = []
    modelo = ModeloFalso(guion=list(guion), recibidos=[])
    agente = create_agent(model=modelo, tools=[sumar],
                          middleware=[mr.MiddlewareReintentos(dormir=esperas.append)])
    resultado = agente.invoke({"messages": [{"role": "user", "content": "¿21 + 21?"}]})
    return resultado["messages"], modelo, esperas


def test_429_y_despues_ok(caplog):
    with caplog.at_level(logging.WARNING, logger="middleware_reintentos"):
        mensajes, modelo, esperas = correr([Error429("limite"), FINAL])
    assert mensajes[-1].text == "Da 42."
    assert esperas == [2]
    assert "Reintento 1/3 por límite" in caplog.text


def test_429_de_nvidia_se_reconoce_por_el_texto():
    assert mr.es_error_de_limite(Exception("[429] Too Many Requests\nRequestID: x"))
    assert not mr.es_error_de_limite(Exception("[401] Unauthorized"))


def test_429_siempre_espera_exponencial_y_propaga_error_claro():
    esperas = []
    modelo = ModeloFalso(guion=[Error429("x")] * 4, recibidos=[])
    agente = create_agent(model=modelo, tools=[sumar], middleware=[mr.MiddlewareReintentos(dormir=esperas.append)])
    with pytest.raises(mr.ErrorLimiteProveedor, match="429"):
        agente.invoke({"messages": [{"role": "user", "content": "hola"}]})
    assert esperas == [2, 4, 8]
    assert len(modelo.recibidos) == 4  # 1 llamada + 3 reintentos


def test_otros_errores_no_se_reintentan():
    modelo = ModeloFalso(guion=[ValueError("otro")], recibidos=[])
    agente = create_agent(model=modelo, tools=[sumar], middleware=[mr.MiddlewareReintentos(dormir=lambda s: None)])
    with pytest.raises(ValueError, match="otro"):
        agente.invoke({"messages": [{"role": "user", "content": "hola"}]})
    assert len(modelo.recibidos) == 1


def test_vacio_y_despues_tool_call_valida(logs_temporales, caplog):
    with caplog.at_level(logging.WARNING, logger="middleware_reintentos"):
        mensajes, modelo, _ = correr([VACIO, TOOL_OK, FINAL])
    resultados = [m for m in mensajes if isinstance(m, ToolMessage)]
    assert resultados[0].content == "42"
    assert mensajes[-1].text == "Da 42."
    assert "Reintento 1/2 por respuesta vacía" in caplog.text
    assert len(list(logs_temporales.glob("*.json"))) == 1
    # El primer reintento repite el pedido tal cual, sin aviso.
    assert modelo.recibidos[1] == modelo.recibidos[0]


def test_el_aviso_va_solo_en_el_segundo_reintento_y_no_queda_en_el_historial():
    mensajes, modelo, _ = correr([VACIO, VACIO, FINAL])
    ultimo_pedido = modelo.recibidos[2][-1]
    assert isinstance(ultimo_pedido, HumanMessage) and ultimo_pedido.content == mr.AVISO_FORMATO
    assert not any(m.content == mr.AVISO_FORMATO for m in mensajes)
    assert mensajes[-1].text == "Da 42."


def test_tool_call_mal_formada_se_reintenta():
    roto = AIMessage(content="", invalid_tool_calls=[{"name": "sumar", "args": "{a: 21", "id": "t1", "error": None}])
    mensajes, modelo, _ = correr([roto, TOOL_OK, FINAL])
    assert mensajes[-1].text == "Da 42."
    assert len(modelo.recibidos) == 3


def test_vacio_tres_veces_termina_sin_colgarse(logs_temporales):
    mensajes, modelo, _ = correr([VACIO, VACIO, VACIO])
    assert len(modelo.recibidos) == 3  # 1 llamada + 2 reintentos, y corta
    assert mensajes[-1].text == ""
    assert len(list(logs_temporales.glob("*.json"))) == 3
