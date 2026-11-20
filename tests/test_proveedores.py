"""Fábrica de proveedores: qué proveedor y modelo se eligen según el entorno (sin red)."""

import pytest

import proveedores


@pytest.fixture(autouse=True)
def sin_dotenv(monkeypatch):
    """Los tests no leen el .env real del desarrollador."""
    monkeypatch.setattr(proveedores, "load_dotenv", lambda: None)
    for variable in ("LLM_PROVIDER", "LLM_MODEL", "LLM_TIMEOUT", "NVIDIA_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY"):
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


def test_openrouter_con_modelo_elegido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", " OpenRouter ")
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    assert proveedores.proveedor_y_modelo() == ("openrouter", "deepseek/deepseek-v4.1-flash-1017")


def test_openrouter_sin_modelo_usa_el_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert proveedores.proveedor_y_modelo() == ("openrouter", "deepseek/deepseek-v4.1-flash-1017")


def test_openrouter_conserva_modelo_y_permite_tools(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")
    monkeypatch.setenv("OPENROUTER_API_KEY", "clave-de-prueba")
    modelo = proveedores.obtener_modelo()
    assert modelo.model_name == "deepseek/deepseek-v4.1-flash-1017"
    assert modelo.max_retries == proveedores.MAX_REINTENTOS
    assert "clave-de-prueba" not in str(proveedores.proveedor_y_modelo())
    herramienta = {"type": "function", "function": {
        "name": "sumar", "description": "Suma dos enteros.",
        "parameters": {"type": "object", "properties": {
            "a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"]},
    }}
    assert modelo.bind_tools([herramienta]).kwargs["tools"] == [herramienta]


def test_proveedor_invalido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(RuntimeError, match="nvidia, deepseek"):
        proveedores.proveedor_y_modelo()


def test_no_expone_la_clave(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "clave-de-prueba")
    assert "clave-de-prueba" not in str(proveedores.proveedor_y_modelo())


@pytest.mark.parametrize("proveedor, variable", [("nvidia", "NVIDIA_API_KEY"), ("deepseek", "DEEPSEEK_API_KEY"), ("openrouter", "OPENROUTER_API_KEY")])
def test_falta_la_clave(monkeypatch, proveedor, variable):
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    with pytest.raises(RuntimeError, match=variable):
        proveedores.obtener_modelo()


@pytest.mark.parametrize("proveedor, variable, clase", [
    ("nvidia", "NVIDIA_API_KEY", "ChatNVIDIA"),
    ("deepseek", "DEEPSEEK_API_KEY", "ChatDeepSeek"),
    ("openrouter", "OPENROUTER_API_KEY", "ChatOpenRouter"),
])
def test_crea_el_modelo_del_proveedor(monkeypatch, proveedor, variable, clase):
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    monkeypatch.setenv(variable, "clave-de-prueba")
    modelo = proveedores.obtener_modelo()
    assert type(modelo).__name__ == clase
    assert modelo.temperature == 0.7 and modelo.max_tokens == 2500


@pytest.mark.parametrize("proveedor, variable, atributo", [
    ("nvidia", "NVIDIA_API_KEY", lambda m: m._client.timeout),
    ("deepseek", "DEEPSEEK_API_KEY", lambda m: m.request_timeout),
    ("openrouter", "OPENROUTER_API_KEY", lambda m: m.client.sdk_configuration.timeout_ms / 1000),
])
def test_timeout_por_defecto_y_configurable(monkeypatch, proveedor, variable, atributo):
    monkeypatch.setenv("LLM_PROVIDER", proveedor)
    monkeypatch.setenv(variable, "clave-de-prueba")
    assert atributo(proveedores.obtener_modelo()) == 120
    monkeypatch.setenv("LLM_TIMEOUT", "45")
    assert atributo(proveedores.obtener_modelo()) == 45


@pytest.mark.parametrize("valor", ["abc", "0", "-5"])
def test_timeout_invalido(monkeypatch, valor):
    monkeypatch.setenv("LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", "clave-de-prueba")
    monkeypatch.setenv("LLM_TIMEOUT", valor)
    with pytest.raises(RuntimeError, match="LLM_TIMEOUT"):
        proveedores.obtener_modelo()
