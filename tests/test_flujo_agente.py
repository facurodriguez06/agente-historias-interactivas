"""Flujo de punta a punta con un modelo FALSO que emite tool calls guionadas.

No usa ningún LLM ni red: comprueba que create_agent, las tools y el contexto
funcionan juntos, en especial que el id de la partida sale del contexto de la
aplicación y no de lo que diga el modelo.
"""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver

import estado_partida as ep

herramientas = pytest.importorskip("herramientas")
create_agent = pytest.importorskip("langchain.agents").create_agent


class ModeloGuionado(BaseChatModel):
    """Devuelve, en orden, los AIMessage de `guion` (uno por llamada al modelo)."""

    guion: list
    paso: int = 0

    @property
    def _llm_type(self):
        return "guionado"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        mensaje = self.guion[self.paso]
        self.paso += 1
        return ChatResult(generations=[ChatGeneration(message=mensaje)])


def llamada(nombre, **args):
    return AIMessage(content="", tool_calls=[{"name": nombre, "args": args, "id": f"id{nombre}"}])


def crear(guion):
    return create_agent(
        model=ModeloGuionado(guion=guion),
        tools=[
            herramientas.consultar_estado_partida,
            herramientas.registrar_decision,
            herramientas.guardar_capitulo,
            herramientas.generar_pdf_historia,
        ],
        context_schema=herramientas.ContextoPartida,
        checkpointer=InMemorySaver(),
    )


def correr(agente, id_partida, texto):
    return agente.invoke(
        {"messages": [{"role": "user", "content": texto}]},
        {"configurable": {"thread_id": id_partida}},
        context=herramientas.ContextoPartida(id_partida=id_partida),
    )


def resultados_de_tools(respuesta):
    return [m for m in respuesta["messages"] if isinstance(m, ToolMessage)]


def test_las_tools_usan_el_id_del_contexto_y_no_exponen_id_al_modelo():
    for t in (herramientas.consultar_estado_partida, herramientas.guardar_capitulo,
              herramientas.registrar_decision, herramientas.generar_pdf_historia):
        assert "id_partida" not in t.args and "runtime" not in t.args

    id_partida = ep.crear_partida()
    agente = crear([
        llamada("guardar_capitulo", titulo="Llegada", texto="Entrás a la casa.", opciones=["A", "B", "C"]),
        AIMessage(content="Capítulo 1: Llegada"),
    ])
    correr(agente, id_partida, "Empezá")
    assert ep.consultar_estado(id_partida)["capitulos"][0]["titulo"] == "Llegada"


def test_error_de_validacion_vuelve_al_modelo_sin_romper_el_flujo():
    id_partida = ep.crear_partida()
    agente = crear([
        llamada("registrar_decision", opcion=1),  # no hay capítulo pendiente
        AIMessage(content="Todavía no hay capítulo."),
    ])
    respuesta = correr(agente, id_partida, "Elijo la 1")
    assert "pendiente" in resultados_de_tools(respuesta)[0].content
    assert respuesta["messages"][-1].content == "Todavía no hay capítulo."


def test_decision_con_inventario_a_traves_del_agente():
    id_partida = ep.crear_partida()
    agente = crear([
        llamada("guardar_capitulo", titulo="Uno", texto="Texto.", opciones=["A", "B", "C"]),
        AIMessage(content="Capítulo 1"),
        llamada("registrar_decision", opcion=2, objetos_recogidos=["Llave oxidada"]),
        AIMessage(content="Tenés la llave."),
    ])
    correr(agente, id_partida, "Empezá")
    correr(agente, id_partida, "Elijo la 2, recojo la llave")
    estado = ep.consultar_estado(id_partida)
    assert estado["inventario"] == ["Llave oxidada"]
    assert estado["decisiones"][0]["opcion"] == 2


def test_partidas_distintas_no_se_mezclan():
    a, b = ep.crear_partida(), ep.crear_partida()
    agente = crear([
        llamada("guardar_capitulo", titulo="Solo A", texto="Texto.", opciones=["A", "B", "C"]),
        AIMessage(content="ok"),
    ])
    correr(agente, a, "Empezá")
    assert len(ep.consultar_estado(a)["capitulos"]) == 1
    assert ep.consultar_estado(b)["capitulos"] == []
