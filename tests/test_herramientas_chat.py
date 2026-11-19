"""Pruebas de las tools de chat: listar partidas abiertas, consultar otras
partidas, iniciar/retomar partidas y el guardia de partida activa.
No usan LLM ni red."""

import pytest

import estado_partida as ep
import herramientas
from conftest import escribir_capitulo, historia_completa


class RuntimeFalso:
    """Reemplazo mínimo de ToolRuntime: solo expone el contexto de la app."""

    def __init__(self, id_partida=""):
        self.context = herramientas.ContextoPartida(id_partida=id_partida)


# --- listar_partidas_abiertas -----------------------------------------------


def test_listar_partidas_abiertas_devuelve_solo_abiertas():
    terminada, abierta = ep.crear_partida(), ep.crear_partida()
    historia_completa(terminada)

    resultado = herramientas.listar_partidas_abiertas.func()

    assert "error" not in resultado
    assert [p["id_partida"] for p in resultado["partidas"]] == [abierta]
    resumen = resultado["partidas"][0]
    assert resumen["finalizada"] is False
    assert resumen["capitulos_escritos"] == 0


def test_listar_partidas_abiertas_incluye_campos_del_resumen():
    partida = ep.crear_partida()
    escribir_capitulo(partida)

    resumen = herramientas.listar_partidas_abiertas.func()["partidas"][0]

    assert resumen["capitulos_escritos"] == 1
    assert resumen["capitulo_actual"] == 0
    assert resumen["titulo_ultimo_capitulo"] == "Título 1"
    assert resumen["decision_pendiente"] is True


def test_listar_partidas_abiertas_respeta_el_limite():
    ids = [ep.crear_partida() for _ in range(4)]

    resultado = herramientas.listar_partidas_abiertas.func(3)

    assert [p["id_partida"] for p in resultado["partidas"]] == ids[:0:-1]


def test_listar_partidas_abiertas_sin_partidas():
    assert herramientas.listar_partidas_abiertas.func() == {"partidas": []}


# --- consultar_otra_partida -------------------------------------------------


def test_consultar_otra_partida_devuelve_estado_de_partida_abierta():
    otra = ep.crear_partida()
    escribir_capitulo(otra)

    resultado = herramientas.consultar_otra_partida.func(otra)

    assert "error" not in resultado
    assert resultado["id_partida"] == otra
    assert resultado["finalizada"] is False
    assert len(resultado["capitulos"]) == 1
    assert "registrar_decision" in resultado["siguiente_paso"]


def test_consultar_otra_partida_devuelve_estado_de_partida_finalizada():
    otra = ep.crear_partida()
    historia_completa(otra)

    resultado = herramientas.consultar_otra_partida.func(otra)

    assert "error" not in resultado
    assert resultado["finalizada"] is True
    assert "generar_pdf_historia" in resultado["siguiente_paso"]


def test_consultar_otra_partida_no_modifica_el_json_en_disco():
    otra = ep.crear_partida()
    escribir_capitulo(otra)
    ruta = ep.CARPETA_PARTIDAS / f"{otra}.json"
    antes = ruta.read_bytes()

    herramientas.consultar_otra_partida.func(otra)

    assert ruta.read_bytes() == antes


@pytest.mark.parametrize("id_malo", ["abc", "", "0" * 32])
def test_consultar_otra_partida_con_id_invalido_devuelve_error(id_malo):
    resultado = herramientas.consultar_otra_partida.func(id_malo)
    assert list(resultado) == ["error"]


# --- retomar_partida --------------------------------------------------------


def test_retomar_partida_devuelve_el_resumen_de_una_abierta():
    partida = ep.crear_partida()
    escribir_capitulo(partida)

    resultado = herramientas.retomar_partida.func(partida)

    assert "error" not in resultado
    assert resultado["id_partida"] == partida
    assert resultado["finalizada"] is False
    assert "registrar_decision" in resultado["siguiente_paso"]
    assert resultado["instruccion"]


def test_retomar_partida_rechaza_una_finalizada():
    partida = ep.crear_partida()
    historia_completa(partida)

    resultado = herramientas.retomar_partida.func(partida)

    assert "already finished" in resultado["error"]


def test_retomar_partida_rechaza_una_inexistente():
    resultado = herramientas.retomar_partida.func("0" * 32)
    assert list(resultado) == ["error"]


# --- iniciar_nueva_partida --------------------------------------------------


def test_iniciar_nueva_partida_crea_la_partida_en_disco():
    resultado = herramientas.iniciar_nueva_partida.func()

    assert "error" not in resultado
    id_partida = resultado["id_partida"]
    assert id_partida
    assert resultado["instruccion"]
    estado = ep.consultar_estado(id_partida)
    assert estado["capitulos"] == [] and estado["finalizada"] is False
    assert (ep.CARPETA_PARTIDAS / f"{id_partida}.json").exists()


# --- guardia de partida activa ---------------------------------------------


def test_el_contexto_por_defecto_no_tiene_partida():
    assert herramientas.ContextoPartida().id_partida == ""


def test_consultar_estado_partida_sin_partida_activa():
    resultado = herramientas.consultar_estado_partida.func(RuntimeFalso(""))
    assert "No active game session" in resultado["error"]


def test_registrar_decision_sin_partida_activa():
    resultado = herramientas.registrar_decision.func(1, RuntimeFalso(""))
    assert "No active game session" in resultado["error"]


def test_guardar_capitulo_sin_partida_activa():
    resultado = herramientas.guardar_capitulo.func("T", "Texto", ["A", "B", "C"], RuntimeFalso(""))
    assert "No active game session" in resultado["error"]


def test_buscar_imagen_capitulo_sin_partida_activa():
    resultado = herramientas.buscar_imagen_capitulo.func("foggy mansion", RuntimeFalso(""))
    assert "No active game session" in resultado["error"]


def test_generar_pdf_historia_sin_partida_activa():
    resultado = herramientas.generar_pdf_historia.func(RuntimeFalso(""))
    assert "No active game session" in resultado


def test_consultar_otra_partida_acepta_id_corto():
    otra = ep.crear_partida()
    historia_completa(otra)

    resultado = herramientas.consultar_otra_partida.func(otra[:8])

    assert "error" not in resultado
    assert resultado["id_partida"] == otra
    assert resultado["finalizada"] is True


def test_listar_partidas_puede_incluir_finalizadas():
    terminada, abierta = ep.crear_partida(), ep.crear_partida()
    historia_completa(terminada)

    resultado = herramientas.listar_partidas_abiertas.func(incluir_finalizadas=True)

    ids = [p["id_partida"] for p in resultado["partidas"]]
    assert set(ids) == {abierta, terminada}


def test_imagen_tardia_en_capitulo_5_regenera_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    partida = ep.crear_partida()
    historia_completa(partida)
    ruta_pdf = tmp_path / "historias_generadas" / f"{partida}.pdf"
    ruta_pdf.parent.mkdir()
    ruta_pdf.write_bytes(b"%PDF-viejo")

    llamadas = []
    monkeypatch.setattr(
        herramientas.imagenes,
        "obtener_imagen",
        lambda *a, **kw: {
            "id_foto": "foto-5",
            "url_imagen": "https://images.unsplash.com/photo-5",
            "autor": "Autora",
            "url_autor": "https://unsplash.com/@autora",
            "url_foto": "https://unsplash.com/photos/foto-5",
            "descripcion": "study",
        },
    )
    monkeypatch.setattr(herramientas, "generar_pdf", lambda pid: llamadas.append(pid) or str(ruta_pdf))

    resultado = herramientas.buscar_imagen_capitulo.func("study", RuntimeFalso(partida))

    assert resultado["ok"] is True
    assert llamadas == [partida]
