"""Volcado de respuestas vacías a logs/ (en una carpeta temporal)."""

import json

from langchain_core.messages import AIMessage

import diagnostico


def test_detecta_respuesta_vacia():
    assert diagnostico.es_respuesta_vacia(AIMessage(content=""))
    assert diagnostico.es_respuesta_vacia(AIMessage(content="   ", additional_kwargs={"reasoning_content": "x"}))
    assert not diagnostico.es_respuesta_vacia(AIMessage(content="Capítulo 1"))
    con_tool = AIMessage(content="", tool_calls=[{"name": "sumar", "args": {}, "id": "1"}])
    assert not diagnostico.es_respuesta_vacia(con_tool)


def test_guarda_el_mensaje_crudo(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostico, "CARPETA_LOGS", tmp_path / "logs")
    mensaje = AIMessage(
        content="",
        additional_kwargs={"reasoning_content": "function functionfunction..."},
        response_metadata={"finish_reason": "stop"},
        invalid_tool_calls=[{"name": "guardar_capitulo", "args": "{roto", "id": "1", "error": None}],
    )
    ruta = diagnostico.guardar_mensaje_crudo(mensaje)
    assert ruta.parent == tmp_path / "logs" and ruta.suffix == ".json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["additional_kwargs"]["reasoning_content"] == "function functionfunction..."
    assert datos["response_metadata"]["finish_reason"] == "stop"
    assert datos["tool_calls"] == [] and datos["invalid_tool_calls"][0]["name"] == "guardar_capitulo"


def test_dos_volcados_seguidos_no_se_pisan(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostico, "CARPETA_LOGS", tmp_path / "logs")
    rutas = {diagnostico.guardar_mensaje_crudo(AIMessage(content="")) for _ in range(5)}
    assert len(rutas) == 5 and len(list((tmp_path / "logs").glob("*.json"))) == 5
