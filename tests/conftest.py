import pytest

import estado_partida


@pytest.fixture(autouse=True)
def carpeta_partidas_temporal(tmp_path, monkeypatch):
    """Cada test escribe sus partidas en una carpeta temporal, nunca en partidas/."""
    monkeypatch.setattr(estado_partida, "CARPETA_PARTIDAS", tmp_path / "partidas")


def escribir_capitulo(id_partida, numero=None):
    """Guarda el capítulo siguiente con datos de prueba (3 opciones; el 5 sin opciones)."""
    estado = estado_partida.consultar_estado(id_partida)
    numero = numero or len(estado["capitulos"]) + 1
    opciones = [] if numero == estado_partida.TOTAL_CAPITULOS else ["A", "B", "C"]
    return estado_partida.guardar_capitulo(id_partida, f"Título {numero}", "Texto.", opciones)


def historia_completa(id_partida):
    """Juega los 5 capítulos eligiendo siempre la opción 1."""
    for _ in range(estado_partida.TOTAL_CAPITULOS - 1):
        escribir_capitulo(id_partida)
        estado_partida.registrar_decision(id_partida, 1)
    escribir_capitulo(id_partida)
