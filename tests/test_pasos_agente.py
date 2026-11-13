"""Razonamiento, pasos y capítulo de respaldo que muestra la UI (sin LLM ni Streamlit)."""

from langchain_core.messages import AIMessage, ToolMessage

import estado_partida as ep
from conftest import escribir_capitulo
from pasos_agente import capitulo_de_respaldo, extraer_razonamiento, pasos_de_mensaje


def test_razonamiento_desde_reasoning_content():
    mensaje = AIMessage(content="Capítulo 1", additional_kwargs={"reasoning_content": "Primero busco contexto."})
    assert extraer_razonamiento(mensaje) == "Primero busco contexto."


def test_razonamiento_desde_bloques_estandar():
    mensaje = AIMessage(content=[
        {"type": "reasoning", "reasoning": "Paso uno."},
        {"type": "reasoning", "reasoning": "Paso dos."},
        {"type": "text", "text": "Respuesta"},
    ])
    assert extraer_razonamiento(mensaje) == "Paso uno.\n\nPaso dos."
    assert mensaje.text == "Respuesta"


def test_sin_razonamiento_no_hay_paso():
    mensaje = AIMessage(content="Hola")
    assert extraer_razonamiento(mensaje) == ""
    assert pasos_de_mensaje(mensaje) == []


def test_razonamiento_va_antes_de_las_tools():
    mensaje = AIMessage(
        content="",
        additional_kwargs={"reasoning_content": "Necesito el contexto."},
        tool_calls=[{"name": "buscar_contexto_narrativo", "args": {"consulta": "mansión"}, "id": "1"}],
    )
    assert pasos_de_mensaje(mensaje) == [
        {"tipo": "razonamiento", "texto": "Necesito el contexto."},
        {"tipo": "tool", "nombre": "buscar_contexto_narrativo", "args": {"consulta": "mansión"}},
    ]


def test_resultado_de_tool():
    mensaje = ToolMessage(content="x" * 2000, name="guardar_capitulo", tool_call_id="1")
    [paso] = pasos_de_mensaje(mensaje)
    assert paso["tipo"] == "resultado" and paso["nombre"] == "guardar_capitulo"
    assert len(paso["texto"]) == 900


# --- Respaldo cuando el turno termina sin texto final ---------------------------


def test_respaldo_muestra_el_capitulo_nuevo_con_opciones():
    id_partida = ep.crear_partida()
    ep.guardar_capitulo(id_partida, "La llegada", "Entrás a la mansión.", ["Subir", "Bajar", "Salir"])
    texto = capitulo_de_respaldo(0, ep.consultar_estado(id_partida))
    assert texto == "**Capítulo 1: La llegada**\n\nEntrás a la mansión.\n\n1. Subir\n2. Bajar\n3. Salir"


def test_sin_capitulo_nuevo_no_hay_respaldo():
    id_partida = ep.crear_partida()
    escribir_capitulo(id_partida)
    assert capitulo_de_respaldo(1, ep.consultar_estado(id_partida)) is None


def test_respaldo_del_desenlace_sin_opciones():
    id_partida = ep.crear_partida()
    for _ in range(ep.TOTAL_CAPITULOS - 1):
        escribir_capitulo(id_partida)
        ep.registrar_decision(id_partida, 1)
    escribir_capitulo(id_partida)
    texto = capitulo_de_respaldo(ep.TOTAL_CAPITULOS - 1, ep.consultar_estado(id_partida))
    assert texto == f"**Capítulo {ep.TOTAL_CAPITULOS}: Título {ep.TOTAL_CAPITULOS}**\n\nTexto."
