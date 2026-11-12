import os

import pytest

import estado_partida as ep
from conftest import escribir_capitulo, historia_completa

generar_pdf = pytest.importorskip("generar_pdf")

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def test_pdf_rechaza_historia_sin_terminar():
    id_partida = ep.crear_partida()
    escribir_capitulo(id_partida)
    with pytest.raises(ValueError, match="no termino"):
        generar_pdf.generar_pdf(id_partida)


@pytest.mark.skipif(not os.path.exists(FUENTE), reason="falta la fuente DejaVu del sistema")
def test_pdf_de_historia_completa(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    id_partida = ep.crear_partida()
    historia_completa(id_partida)
    ruta = generar_pdf.generar_pdf(id_partida)
    assert (tmp_path / ruta).read_bytes().startswith(b"%PDF")
