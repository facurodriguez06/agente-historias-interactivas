"""Pruebas de las reglas de la historia. No usan LLM ni red."""

import pytest

import estado_partida as ep
from conftest import escribir_capitulo, historia_completa


@pytest.fixture
def partida():
    return ep.crear_partida()


# --- identificador ---------------------------------------------------------


@pytest.mark.parametrize(
    "id_malo", ["../../etc/passwd", "abc", "", "A" * 32, "g" * 32, None, 123]
)
def test_id_invalido_se_rechaza(id_malo):
    with pytest.raises(ValueError, match="inválido"):
        ep.consultar_estado(id_malo)


def test_partida_inexistente():
    with pytest.raises(ValueError, match="no existe"):
        ep.consultar_estado("0" * 32)


def test_crear_partida_estado_inicial(partida):
    estado = ep.consultar_estado(partida)
    assert estado["capitulo_actual"] == 0
    assert estado["capitulos"] == [] and estado["decisiones"] == []
    assert estado["inventario"] == [] and estado["pistas_descubiertas"] == []
    assert estado["finalizada"] is False


def test_partidas_independientes():
    a, b = ep.crear_partida(), ep.crear_partida()
    escribir_capitulo(a)
    assert len(ep.consultar_estado(a)["capitulos"]) == 1
    assert ep.consultar_estado(b)["capitulos"] == []


def test_partida_anterior_sin_campo_finalizada(partida):
    estado = ep.consultar_estado(partida)
    del estado["finalizada"]
    ep.guardar_estado(estado)
    assert ep.consultar_estado(partida)["finalizada"] is False


def test_no_quedan_archivos_temporales(partida):
    escribir_capitulo(partida)
    assert [p.suffix for p in ep.CARPETA_PARTIDAS.iterdir()] == [".json"]


# --- capítulos y decisiones ------------------------------------------------


def test_no_se_decide_sin_capitulo(partida):
    with pytest.raises(ValueError, match="pendiente"):
        ep.registrar_decision(partida, 1)


def test_no_se_escribe_con_capitulo_pendiente(partida):
    escribir_capitulo(partida)
    with pytest.raises(ValueError, match="pendiente"):
        escribir_capitulo(partida)


def test_no_hay_doble_decision(partida):
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 2)
    with pytest.raises(ValueError, match="pendiente"):
        ep.registrar_decision(partida, 2)


@pytest.mark.parametrize("opcion", [0, 4, -1, True, "1", None])
def test_opcion_invalida(partida, opcion):
    escribir_capitulo(partida)
    with pytest.raises(ValueError, match="opcion"):
        ep.registrar_decision(partida, opcion)
    assert ep.consultar_estado(partida)["decisiones"] == []


@pytest.mark.parametrize("opciones", [[], ["A"], ["A", "B"], ["A", "B", "C", "D"], ["A", "", "C"]])
def test_capitulo_exige_tres_opciones(partida, opciones):
    with pytest.raises(ValueError):
        ep.guardar_capitulo(partida, "T", "Texto", opciones)


def test_titulo_y_texto_no_vacios(partida):
    with pytest.raises(ValueError):
        ep.guardar_capitulo(partida, "  ", "Texto", ["A", "B", "C"])
    with pytest.raises(ValueError):
        ep.guardar_capitulo(partida, "T", "", ["A", "B", "C"])


def test_decision_queda_registrada(partida):
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 3)
    estado = ep.consultar_estado(partida)
    assert estado["capitulo_actual"] == 1
    assert estado["decisiones"][0]["capitulo"] == 1
    assert estado["decisiones"][0]["opcion"] == 3


# --- cierre de la historia -------------------------------------------------


def test_el_desenlace_no_lleva_opciones(partida):
    for _ in range(4):
        escribir_capitulo(partida)
        ep.registrar_decision(partida, 1)
    with pytest.raises(ValueError, match="desenlace"):
        ep.guardar_capitulo(partida, "Final", "Texto", ["A", "B", "C"])
    assert ep.consultar_estado(partida)["finalizada"] is False


def test_el_capitulo_5_finaliza_la_partida(partida):
    historia_completa(partida)
    estado = ep.consultar_estado(partida)
    assert len(estado["capitulos"]) == 5
    assert len(estado["decisiones"]) == 4
    assert estado["finalizada"] is True
    assert estado["capitulos"][4]["opciones"] == []


def test_partida_finalizada_rechaza_escrituras(partida):
    historia_completa(partida)
    with pytest.raises(ValueError, match="terminó"):
        ep.registrar_decision(partida, 1)
    with pytest.raises(ValueError, match="terminó"):
        ep.guardar_capitulo(partida, "Extra", "Texto", ["A", "B", "C"])
    assert len(ep.consultar_estado(partida)["capitulos"]) == 5


def test_siguiente_paso_guia_el_flujo(partida):
    assert "capítulo 1" in ep.siguiente_paso(ep.consultar_estado(partida))
    r = escribir_capitulo(partida)
    assert "registrar_decision" in r["siguiente_paso"]
    r = ep.registrar_decision(partida, 1)
    assert "capítulo 2" in r["siguiente_paso"]
    for _ in range(3):
        escribir_capitulo(partida)
        r = ep.registrar_decision(partida, 1)
    assert "desenlace" in r["siguiente_paso"]
    r = escribir_capitulo(partida)
    assert r["finalizada"] is True and "generar_pdf_historia" in r["siguiente_paso"]


# --- inventario y pistas ---------------------------------------------------


def test_recoger_objeto_del_catalogo(partida):
    escribir_capitulo(partida)
    r = ep.registrar_decision(partida, 1, objetos_recogidos=["llave OXIDADA"])
    assert r["inventario"] == ["Llave oxidada"]
    assert ep.consultar_estado(partida)["decisiones"][0]["objetos_recogidos"] == ["Llave oxidada"]


def test_objeto_fuera_del_catalogo(partida):
    escribir_capitulo(partida)
    with pytest.raises(ValueError, match="desconocido"):
        ep.registrar_decision(partida, 1, objetos_recogidos=["Espada mágica"])
    estado = ep.consultar_estado(partida)
    assert estado["inventario"] == [] and estado["decisiones"] == []


def test_no_se_usa_un_objeto_que_no_se_tiene(partida):
    escribir_capitulo(partida)
    with pytest.raises(ValueError, match="no lo tiene"):
        ep.registrar_decision(partida, 1, objetos_usados=["Llave oxidada"])
    assert ep.consultar_estado(partida)["decisiones"] == []


def test_usar_un_objeto_poseido(partida):
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 1, objetos_recogidos=["Llave oxidada"])
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 2, objetos_usados=["Llave oxidada"])
    estado = ep.consultar_estado(partida)
    assert estado["decisiones"][1]["objetos_usados"] == ["Llave oxidada"]
    assert estado["inventario"] == ["Llave oxidada"]


def test_no_se_recoge_dos_veces(partida):
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 1, objetos_recogidos=["Llave oxidada"])
    escribir_capitulo(partida)
    with pytest.raises(ValueError, match="ya está"):
        ep.registrar_decision(partida, 1, objetos_recogidos=["Llave oxidada"])


def test_repetidos_en_la_misma_decision_se_ignoran(partida):
    escribir_capitulo(partida)
    r = ep.registrar_decision(partida, 1, objetos_recogidos=["Llave oxidada", "llave oxidada "])
    assert r["inventario"] == ["Llave oxidada"]


def test_pistas_sin_duplicados(partida):
    escribir_capitulo(partida)
    ep.registrar_decision(partida, 1, pistas_descubiertas=["El reloj marca las 02:17"])
    escribir_capitulo(partida)
    r = ep.registrar_decision(
        partida, 1, pistas_descubiertas=["El reloj marca las 02:17", "La nota tiene iniciales"]
    )
    assert r["pistas_descubiertas"] == ["El reloj marca las 02:17", "La nota tiene iniciales"]


def test_pista_vacia_se_rechaza(partida):
    escribir_capitulo(partida)
    with pytest.raises(ValueError):
        ep.registrar_decision(partida, 1, pistas_descubiertas=["  "])
    assert ep.consultar_estado(partida)["decisiones"] == []
