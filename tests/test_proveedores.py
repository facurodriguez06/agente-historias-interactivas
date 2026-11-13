"""Fábrica de proveedores: qué proveedor y modelo se eligen según el entorno (sin red)."""

import pytest

import proveedores


@pytest.fixture(autouse=True)
def sin_dotenv(monkeypatch):
    """Los tests no leen el .env real del desarrollador."""
    monkeypatch.setattr(proveedores, "load_dotenv", lambda: None)
    for variable in ("LLM_PROVIDER", "LLM_MODEL", "NVIDIA_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(variable, raising=False)


def test_sin_configurar_usa_deepseek_con_su_modelo_por_defecto():
    assert proveedores.proveedor_y_modelo() == ("deepseek", "deepseek-flash")


def test_nvidia_con_modelo_elegido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", " NVIDIA ")
    monkeypatch.setenv("LLM_MODEL", "meta/llama-3.3-70b-instruct")
    assert proveedores.proveedor_y_modelo() == ("nvidia", "meta/llama-3.3-70b-instruct")


def test_nvidia_sin_modelo_usa_el_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    assert proveedores.proveedor_y_modelo() == ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b")


def test_proveedor_invalido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(RuntimeError, match="nvidia, deepseek"):
        proveedores.proveedor_y_modelo()


def test_no_expone_la_clave(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "clave-de-prueba")
    assert "clave-de-prueba" not in str(proveedores.proveedor_y_modelo())


@pytest.mark.parametrize("proveedor, variable", [("nvidia", "NVIDIA_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY")])
def test_falta_la_clave(monkeypatch, proveedor, variable):
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    with pytest.raises(RuntimeError, match=variable):
        proveedores.obtener_modelo()


@pytest.mark.parametrize("proveedor, variable, clase", [
    ("nvidia", "NVIDIA_API_KEY", "ChatNVIDIA"),
    ("deepseek", "DEEPSEEK_API_KEY", "ChatDeepSeek"),
])
def test_crea_el_modelo_del_proveedor(monkeypatch, proveedor, variable, clase):
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    monkeypatch.setenv(variable, "clave-de-prueba")
    modelo = proveedores.obtener_modelo()
    assert type(modelo).__name__ == clase
    assert modelo.temperature == 0.5 and modelo.max_tokens == 1000
