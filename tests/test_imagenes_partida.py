"""Imágenes de los capítulos (hotlinking): estado, tool, PDF y flujo con el agente (red simulada)."""

import os

import pytest
from langchain_core.messages import AIMessage

import estado_partida as ep
from conftest import UnsplashFalso, escribir_capitulo, historia_completa, instalar_unsplash
from test_flujo_agente import ModeloGuionado, correr, crear, llamada, resultados_de_tools  # noqa: F401

herramientas = pytest.importorskip("herramientas")
generar_pdf = pytest.importorskip("generar_pdf")

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def foto(id_foto="foto1", autor="Ana Fotógrafa"):
    return {
        "id_foto": id_foto,
        "url_imagen": f"https://images.unsplash.com/{id_foto}.jpg",
        "autor": autor,
        "url_autor": "https://unsplash.com/@ana",
        "url_foto": f"https://unsplash.com/photos/{id_foto}",
        "descripcion": "una casa",
    }


def adjuntar(id_partida, id_foto="foto1"):
    """Simula lo que hace la tool: adjunta una foto (solo su URL) al último capítulo."""
    return ep.adjuntar_imagen(id_partida, foto(id_foto))


@pytest.fixture
def partida():
    return ep.crear_partida()


# --- estado ----------------------------------------------------------------


def test_sin_capitulos_no_hay_donde_adjuntar(partida):
    with pytest.raises(ValueError, match="ningún capítulo"):
        ep.capitulo_para_imagen(partida)


def test_los_capitulos_nuevos_empiezan_sin_imagen(partida):
    escribir_capitulo(partida)
    assert ep.consultar_estado(partida)["capitulos"][0]["imagen"] is None


def test_se_adjunta_al_ultimo_capitulo(partida):
    escribir_capitulo(partida)
    assert adjuntar(partida) == 1
    capitulo = ep.consultar_estado(partida)["capitulos"][0]
    assert capitulo["imagen"]["autor"] == "Ana Fotógrafa"
    assert ep.url_de_imagen(capitulo) == "https://images.unsplash.com/foto1.jpg"


def test_no_se_guarda_ningun_archivo_de_imagen(partida):
    escribir_capitulo(partida)
    adjuntar(partida)
    assert not (ep.CARPETA_PARTIDAS / "imagenes").exists()
    assert [p.suffix for p in ep.CARPETA_PARTIDAS.iterdir()] == [".json"]


@pytest.mark.parametrize(
    "url", ["https://evil.example/x.jpg", "http://images.unsplash.com/x.jpg", "", None]
)
def test_url_de_otro_host_no_se_adjunta(partida, url):
    escribir_capitulo(partida)
    ajena = foto()
    ajena["url_imagen"] = url
    with pytest.raises(ValueError, match="no es de Unsplash"):
        ep.adjuntar_imagen(partida, ajena)
    assert ep.consultar_estado(partida)["capitulos"][0]["imagen"] is None


def test_un_capitulo_no_admite_dos_imagenes(partida):
    escribir_capitulo(partida)
    adjuntar(partida)
    with pytest.raises(ValueError, match="ya tiene imagen"):
        ep.capitulo_para_imagen(partida)


def test_cada_capitulo_tiene_su_imagen_y_se_informan_las_usadas(partida):
    escribir_capitulo(partida)
    adjuntar(partida, "foto1")
    ep.registrar_decision(partida, 1)
    escribir_capitulo(partida)
    numero, usadas = ep.capitulo_para_imagen(partida)
    assert numero == 2 and usadas == ["foto1"]


def test_el_desenlace_tambien_lleva_imagen_con_la_partida_finalizada(partida):
    historia_completa(partida)
    assert ep.consultar_estado(partida)["finalizada"] is True
    assert adjuntar(partida) == 5


def test_url_de_imagen_es_none_sin_imagen(partida):
    escribir_capitulo(partida)
    assert ep.url_de_imagen(ep.consultar_estado(partida)["capitulos"][0]) is None


def test_capitulo_de_una_partida_vieja_sin_campo_imagen(partida):
    escribir_capitulo(partida)
    estado = ep.consultar_estado(partida)
    del estado["capitulos"][0]["imagen"]
    ep.guardar_estado(estado)
    assert ep.capitulo_para_imagen(partida)[0] == 1


def test_guardar_capitulo_recuerda_pedir_la_imagen(partida):
    r = escribir_capitulo(partida)
    assert "buscar_imagen_capitulo" in r["imagen_pendiente"]


# --- PDF -------------------------------------------------------------------


@pytest.mark.skipif(not os.path.exists(FUENTE), reason="falta la fuente DejaVu del sistema")
def test_pdf_con_imagenes_y_credito(partida, unsplash, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for numero in range(1, 5):
        escribir_capitulo(partida)
        adjuntar(partida, f"foto{numero}")
        ep.registrar_decision(partida, 1)
    escribir_capitulo(partida)
    adjuntar(partida, "foto5")
    contenido = (tmp_path / generar_pdf.generar_pdf(partida)).read_bytes()
    assert contenido.count(b"/Subtype /Image") == 5
    assert b"unsplash.com" in contenido and b"utm_source=agente_historias_interactivas" in contenido
    # Se pidió cada foto a su URL original y no quedó ninguna copia en disco
    assert len([u for u in unsplash.urls() if u.startswith("https://images.")]) == 5
    assert not (ep.CARPETA_PARTIDAS / "imagenes").exists()
    assert list(tmp_path.rglob("*.jpg")) == []


@pytest.mark.skipif(not os.path.exists(FUENTE), reason="falta la fuente DejaVu del sistema")
def test_pdf_con_capitulos_sin_imagen(partida, unsplash, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for _ in range(4):
        escribir_capitulo(partida)
        ep.registrar_decision(partida, 1)
    escribir_capitulo(partida)
    contenido = (tmp_path / generar_pdf.generar_pdf(partida)).read_bytes()
    assert contenido.startswith(b"%PDF") and b"/Subtype /Image" not in contenido
    assert unsplash.llamadas == []


@pytest.mark.skipif(not os.path.exists(FUENTE), reason="falta la fuente DejaVu del sistema")
@pytest.mark.parametrize(
    "falla",
    [
        {"estado_imagen": 404},
        {"contenido": b"no soy una imagen"},
        {"error_red": __import__("requests").ConnectionError()},
    ],
    ids=["404", "no_es_jpeg", "sin_red"],
)
def test_si_la_foto_no_se_puede_descargar_el_pdf_sale_sin_ella(partida, tmp_path, monkeypatch, falla):
    """Sin red al exportar, el PDF se genera igual: el capítulo sale sin imagen."""
    monkeypatch.chdir(tmp_path)
    escribir_capitulo(partida)
    adjuntar(partida)
    ep.registrar_decision(partida, 1)
    for _ in range(3):
        escribir_capitulo(partida)
        ep.registrar_decision(partida, 1)
    escribir_capitulo(partida)
    instalar_unsplash(monkeypatch, UnsplashFalso(**falla))
    contenido = (tmp_path / generar_pdf.generar_pdf(partida)).read_bytes()
    assert contenido.startswith(b"%PDF") and b"/Subtype /Image" not in contenido


# --- tool y flujo con el agente ---------------------------------------------


def agente_con_imagenes(guion):
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import InMemorySaver

    return create_agent(
        model=ModeloGuionado(guion=guion),
        tools=[herramientas.guardar_capitulo, herramientas.buscar_imagen_capitulo,
               herramientas.registrar_decision],
        context_schema=herramientas.ContextoPartida,
        checkpointer=InMemorySaver(),
    )


def test_la_tool_no_expone_el_id_de_partida():
    assert list(herramientas.buscar_imagen_capitulo.args) == ["consulta"]


def test_flujo_guardar_capitulo_y_buscar_imagen(partida, unsplash):
    agente = agente_con_imagenes([
        llamada("guardar_capitulo", titulo="Llegada", texto="Entrás.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="foggy old mansion"),
        AIMessage(content="Capítulo 1"),
    ])
    respuesta = correr(agente, partida, "Empezá")
    resultado = resultados_de_tools(respuesta)[1].content
    assert "Ana Fotógrafa" in resultado
    capitulo = ep.consultar_estado(partida)["capitulos"][0]
    assert capitulo["imagen"]["id_foto"] == "foto1"
    assert ep.url_de_imagen(capitulo) == "https://images.unsplash.com/foto1.jpg"
    # Hotlinking: la tool no pidió la foto ni guardó archivos
    assert [u for u in unsplash.urls() if u.startswith("https://images.")] == []
    assert not (ep.CARPETA_PARTIDAS / "imagenes").exists()


def test_si_unsplash_falla_la_historia_sigue_sin_imagen(partida, monkeypatch):
    instalar_unsplash(monkeypatch, UnsplashFalso(estado_busqueda=403))
    agente = agente_con_imagenes([
        llamada("guardar_capitulo", titulo="Llegada", texto="Entrás.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="foggy old mansion"),
        AIMessage(content="Capítulo 1 sin imagen"),
    ])
    respuesta = correr(agente, partida, "Empezá")
    assert "límite" in resultados_de_tools(respuesta)[1].content
    assert respuesta["messages"][-1].content == "Capítulo 1 sin imagen"
    assert ep.consultar_estado(partida)["capitulos"][0]["imagen"] is None


def test_sin_key_la_tool_devuelve_error_y_no_rompe(partida, monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    agente = agente_con_imagenes([
        llamada("guardar_capitulo", titulo="Llegada", texto="Entrás.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="foggy old mansion"),
        AIMessage(content="ok"),
    ])
    respuesta = correr(agente, partida, "Empezá")
    assert "UNSPLASH_ACCESS_KEY" in resultados_de_tools(respuesta)[1].content


def test_no_se_gasta_cuota_si_el_capitulo_ya_tiene_imagen(partida, unsplash):
    agente = agente_con_imagenes([
        llamada("guardar_capitulo", titulo="Llegada", texto="Entrás.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="foggy old mansion"),
        AIMessage(content="uno"),
    ])
    correr(agente, partida, "Empezá")
    antes = len(unsplash.llamadas)
    agente2 = agente_con_imagenes([
        llamada("buscar_imagen_capitulo", consulta="otra consulta"),
        AIMessage(content="dos"),
    ])
    respuesta = correr(agente2, partida, "Otra imagen")
    assert "ya tiene imagen" in resultados_de_tools(respuesta)[0].content
    assert len(unsplash.llamadas) == antes


def test_sin_capitulo_la_tool_no_llama_a_la_api(partida, unsplash):
    agente = agente_con_imagenes([
        llamada("buscar_imagen_capitulo", consulta="foggy old mansion"),
        AIMessage(content="ok"),
    ])
    respuesta = correr(agente, partida, "Imagen")
    assert "ningún capítulo" in resultados_de_tools(respuesta)[0].content
    assert unsplash.llamadas == []


def test_el_segundo_capitulo_no_repite_foto(partida, unsplash):
    agente = agente_con_imagenes([
        llamada("guardar_capitulo", titulo="Uno", texto="Texto.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="mansion"),
        AIMessage(content="uno"),
        llamada("registrar_decision", opcion=1),
        llamada("guardar_capitulo", titulo="Dos", texto="Texto.", opciones=["A", "B", "C"]),
        llamada("buscar_imagen_capitulo", consulta="mansion"),
        AIMessage(content="dos"),
    ])
    correr(agente, partida, "Empezá")
    correr(agente, partida, "Elijo 1")
    capitulos = ep.consultar_estado(partida)["capitulos"]
    assert [c["imagen"]["id_foto"] for c in capitulos] == ["foto1", "foto2"]


@pytest.mark.skipif(not os.path.exists(FUENTE), reason="falta la fuente DejaVu del sistema")
def test_titulo_imagen_y_credito_van_juntos_en_el_pdf(partida, unsplash, tmp_path, monkeypatch):
    """Regresión: un título no puede quedar solo al pie de una página con su imagen en la siguiente."""
    from reportlab.platypus import Image, KeepTogether, Paragraph

    monkeypatch.chdir(tmp_path)
    for numero in range(1, 5):
        escribir_capitulo(partida)
        adjuntar(partida, f"foto{numero}")
        ep.registrar_decision(partida, 1)
    escribir_capitulo(partida)
    adjuntar(partida, "foto5")

    capturado = {}

    class DocumentoEspia:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, elementos):
            capturado["elementos"] = elementos

    monkeypatch.setattr(generar_pdf, "SimpleDocTemplate", DocumentoEspia)
    generar_pdf.generar_pdf(partida)

    bloques = [e for e in capturado["elementos"] if isinstance(e, KeepTogether)]
    assert len(bloques) == 5
    for bloque in bloques:
        contenido = bloque._content
        assert isinstance(contenido[0], Paragraph)  # el título
        assert any(isinstance(c, Image) for c in contenido)
