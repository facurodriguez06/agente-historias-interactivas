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


def crear(guion, extra_tools=()):
    return create_agent(
        model=ModeloGuionado(guion=guion),
        tools=[
            herramientas.consultar_estado_partida,
            herramientas.registrar_decision,
            herramientas.guardar_capitulo,
            herramientas.generar_pdf_historia,
            *extra_tools,
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


def test_empezar_con_partida_activa_sin_capitulos_escribe_el_capitulo_1(monkeypatch):
    """S12: "empezá" con una partida activa de 0 capítulos escribe el capítulo 1
    en ese mismo turno, sin llamar a iniciar_nueva_partida (la sesión ya existe).
    """

    class BaseFalsa:
        def similarity_search(self, consulta, k=3):
            return []

    # RAG hermético: la tool de contexto corre sin cargar el modelo de embeddings.
    monkeypatch.setattr(herramientas, "obtener_base", lambda: BaseFalsa())

    id_partida = ep.crear_partida()
    partidas_antes = len(list(ep.CARPETA_PARTIDAS.glob("*.json")))
    agente = crear(
        [
            llamada("consultar_estado_partida"),
            llamada("buscar_contexto_narrativo", consulta="old mansion entrance hall fog"),
            llamada(
                "guardar_capitulo",
                titulo="La llegada",
                texto="Entrás a la casona.",
                opciones=["A", "B", "C"],
                ubicacion_actual="Entrance Hall",
                hechos_nuevos=[],
                misterios_nuevos=["Who owns the mansion?"],
                misterios_resueltos=[],
                resumen_contexto="The protagonist arrives at the mansion.",
            ),
            AIMessage(content="Capítulo 1: La llegada"),
        ],
        extra_tools=[herramientas.buscar_contexto_narrativo, herramientas.iniciar_nueva_partida],
    )
    respuesta = correr(agente, id_partida, "empezá")

    nombres = [m.name for m in resultados_de_tools(respuesta)]
    assert "guardar_capitulo" in nombres
    assert "iniciar_nueva_partida" not in nombres
    assert "consultar_estado_partida" in nombres
    assert "buscar_contexto_narrativo" in nombres

    estado = ep.consultar_estado(id_partida)
    assert len(estado["capitulos"]) == 1
    assert estado["capitulos"][0]["titulo"] == "La llegada"
    assert estado["capitulos"][0]["opciones"] == ["A", "B", "C"]

    # No se creó ninguna partida nueva: la sesión activa ya existía.
    assert len(list(ep.CARPETA_PARTIDAS.glob("*.json"))) == partidas_antes


def test_las_instrucciones_ordenan_escribir_el_capitulo_1_con_partida_sin_capitulos():
    """Aserción barata (sin LLM): el texto de INSTRUCCIONES contiene la regla S12."""
    import agente

    assert "BEGIN CHAPTER 1 NOW" in agente.INSTRUCCIONES
    assert "has 0 chapters written" in agente.INSTRUCCIONES
    assert "jugemos" in agente.INSTRUCCIONES
    assert "Do NOT call iniciar_nueva_partida in this case" in agente.INSTRUCCIONES
    # La regla vieja (confirmar sin escribir) ya no puede quedar en el prompt.
    assert (
        "confirm the new game was created WITHOUT writing any chapter" not in agente.INSTRUCCIONES
    )
