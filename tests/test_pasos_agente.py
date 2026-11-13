"""Extracción del razonamiento y pasos que muestra la UI (sin LLM ni Streamlit)."""

from langchain_core.messages import AIMessage, ToolMessage

from pasos_agente import extraer_razonamiento, pasos_de_mensaje


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
