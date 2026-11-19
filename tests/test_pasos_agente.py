"""Razonamiento, pasos y capítulo de respaldo que muestra la UI (sin LLM ni Streamlit)."""

import json

from langchain_core.messages import AIMessage, ToolMessage

import estado_partida as ep
from conftest import escribir_capitulo
from pasos_agente import (
    capitulo_de_respaldo,
    cambio_de_sesion,
    extraer_razonamiento,
    pasos_de_mensaje,
)


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


# --- Cambio de sesión propuesto por el agente dentro de un turno -----------------

ID_A = "a" * 32
ID_B = "b" * 32


def llamada_retomar(id_partida):
    return AIMessage(
        content="",
        tool_calls=[{"name": "retomar_partida", "args": {"id_partida": id_partida}, "id": "1"}],
    )


def resultado_nueva(id_partida, contenido=None):
    if contenido is None:
        contenido = json.dumps({"id_partida": id_partida, "instruccion": "solo confirmá"})
    return ToolMessage(content=contenido, name="iniciar_nueva_partida", tool_call_id="2")


def test_cambio_retomar_por_args_de_la_tool():
    assert cambio_de_sesion([llamada_retomar(ID_A)]) == {
        "accion": "retomar",
        "id_partida": ID_A,
    }


def test_cambio_nueva_por_json_del_resultado_de_la_tool():
    assert cambio_de_sesion([resultado_nueva(ID_B)]) == {
        "accion": "nueva",
        "id_partida": ID_B,
    }


def test_id_invalido_se_ignora():
    assert cambio_de_sesion([llamada_retomar("no-existo")]) is None
    assert cambio_de_sesion([resultado_nueva("1234")]) is None


def test_el_ultimo_cambio_gana():
    assert cambio_de_sesion([llamada_retomar(ID_A), resultado_nueva(ID_B)]) == {
        "accion": "nueva",
        "id_partida": ID_B,
    }
    assert cambio_de_sesion([resultado_nueva(ID_B), llamada_retomar(ID_A)]) == {
        "accion": "retomar",
        "id_partida": ID_A,
    }


def test_turno_sin_cambios_devuelve_none():
    mensajes = [
        AIMessage(
            content="",
            tool_calls=[{"name": "consultar_estado_partida", "args": {}, "id": "3"}],
        ),
        ToolMessage(content="{\"capitulos\": []}", name="consultar_estado_partida", tool_call_id="3"),
        AIMessage(content="Elegí una opción, por favor."),
    ]
    assert cambio_de_sesion(mensajes) is None
    assert cambio_de_sesion([]) is None


def test_contenido_malformado_se_ignora():
    assert cambio_de_sesion([resultado_nueva(None, contenido="no es json")]) is None
    assert cambio_de_sesion([resultado_nueva(None, contenido="[1, 2]")]) is None


def test_cambio_retomar_con_id_corto_desde_resultado_de_la_tool():
    mensajes = [
        llamada_retomar(ID_A[:8]),
        ToolMessage(
            content=json.dumps({"id_partida": ID_A, "instruccion": "ok"}),
            name="retomar_partida",
            tool_call_id="1",
        ),
    ]
    assert cambio_de_sesion(mensajes) == {"accion": "retomar", "id_partida": ID_A}
