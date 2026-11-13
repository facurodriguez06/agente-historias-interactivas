"""Prueba manual del modelo configurado en el .env (no lo importa la app).

    python scripts/probar_modelo.py --listar   # modelos de NVIDIA con soporte de tools
    python scripts/probar_modelo.py            # tool calling + razonamiento con obtener_modelo()
    python scripts/probar_modelo.py --latencia # la prueba de tool calling 2 veces, con tiempos
    python scripts/probar_modelo.py --modelos m1,m2  # --latencia para cada modelo (pisa LLM_MODEL)
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from langchain_core.tools import tool

from middleware_reintentos import ERRORES_DE_RED
from proveedores import obtener_modelo

PREGUNTA = "¿cuánto es 21 + 21? usá la tool"
REPETICIONES_LATENCIA = 2


@tool
def sumar(a: int, b: int) -> int:
    """Suma dos números enteros."""
    return a + b


def describir_error(error):
    """Mensaje corto para los errores más comunes (sin traceback)."""
    texto = str(error)
    estado = getattr(error, "status_code", None)
    if estado is None:
        coincidencia = re.match(r"\s*\[(\d{3})\]", texto)  # formato de ChatNVIDIA: "[401] ..."
        estado = int(coincidencia.group(1)) if coincidencia else None
    if estado == 401:
        return "401: la API key es inválida o venció. Revisala en el .env."
    if estado == 403:
        return "403: la key no tiene acceso a este modelo."
    if estado == 404:
        return "404: el modelo no existe para este proveedor. Revisá LLM_MODEL (probá --listar)."
    if estado == 410:
        return "410: el modelo fue dado de baja en el endpoint hosteado."
    if estado == 429:
        return "429: límite de pedidos o de cuota alcanzado. Esperá un rato y reintentá."
    if estado in (502, 503, 504):
        return f"{estado}: el proveedor no está disponible ahora. Probá en un rato."
    if isinstance(error, ERRORES_DE_RED):
        return f"timeout o conexión ({type(error).__name__}): el modelo no respondió a tiempo (ver LLM_TIMEOUT)."
    primera_linea = texto.strip().splitlines()[0] if texto.strip() else type(error).__name__
    return f"{type(error).__name__}: {primera_linea}"


def listar_modelos_nvidia():
    load_dotenv()
    if not os.getenv("NVIDIA_API_KEY"):
        raise RuntimeError("Falta NVIDIA_API_KEY en el archivo .env")
    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    modelos = [m for m in ChatNVIDIA.get_available_models() if m.supports_tools]
    for modelo in sorted(modelos, key=lambda m: m.id):
        extra = "  (thinking)" if modelo.supports_thinking else ""
        print(f"{modelo.id}{extra}")
    print(f"\n{len(modelos)} modelos con supports_tools=True")


def razonamiento(mensaje):
    """Devuelve {origen: texto} con cada lugar donde vino razonamiento."""
    encontrado = {}
    # content crudo: algunos proveedores mandan bloques de razonamiento nativos.
    if isinstance(mensaje.content, list):
        bloques = [b for b in mensaje.content if isinstance(b, dict) and b.get("type") in ("reasoning", "thinking")]
        if bloques:
            encontrado["content (bloques nativos)"] = " ".join(
                str(b.get("reasoning") or b.get("thinking") or "") for b in bloques
            )
    # content_blocks: vista normalizada de LangChain (también incluye reasoning_content).
    bloques = [b for b in mensaje.content_blocks if b.get("type") == "reasoning"]
    if bloques:
        encontrado["content_blocks"] = " ".join(b.get("reasoning", "") for b in bloques)
    if mensaje.additional_kwargs.get("reasoning_content"):
        encontrado['additional_kwargs["reasoning_content"]'] = mensaje.additional_kwargs["reasoning_content"]
    return encontrado


def recortar(texto, largo=300):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= largo else texto[:largo] + f"... ({len(texto)} caracteres)"


def mostrar(titulo, mensaje):
    print(f"\n=== {titulo} ===")
    if mensaje.tool_calls:
        for llamada in mensaje.tool_calls:
            print(f"tool_call: {llamada['name']}({llamada['args']})")
    else:
        print("tool_calls: ninguna")
    print(f"texto: {recortar(mensaje.text) or '(vacío)'}")
    origenes = razonamiento(mensaje)
    if not origenes:
        print("razonamiento: no vino")
    for origen, texto in origenes.items():
        print(f"razonamiento en {origen}: {recortar(texto)}")
    return origenes


def soporta_thinking(modelo):
    # Solo ChatNVIDIA expone esta info (en su catálogo interno de modelos).
    info = getattr(getattr(modelo, "_client", None), "model", None)
    return bool(info and info.supports_thinking)


def probar():
    modelo = obtener_modelo()
    nombre = getattr(modelo, "model", None) or getattr(modelo, "model_name", "?")
    print(f"Modelo: {type(modelo).__name__} / {nombre}")
    con_tools = modelo.bind_tools([sumar])

    normal = con_tools.invoke(PREGUNTA)
    origenes_normal = mostrar("Sin configurar thinking", normal)

    if not soporta_thinking(modelo):
        print("\nEste modelo no declara thinking_mode: no se prueba con thinking activado.")
        return

    # thinking_mode viaja como kwarg de invocación y ChatNVIDIA lo traduce
    # al parámetro o prefijo que use cada modelo.
    pensando = con_tools.invoke(PREGUNTA, thinking_mode=True)
    origenes_pensando = mostrar("Con thinking_mode=True", pensando)

    print("\n=== Diferencia ===")
    print(f"tool_calls: {len(normal.tool_calls)} sin configurar / {len(pensando.tool_calls)} con thinking")
    largo = lambda o: max((len(t) for t in o.values()), default=0)
    print(f"razonamiento: {largo(origenes_normal)} caracteres sin configurar / {largo(origenes_pensando)} con thinking")
    print(f"orígenes sin configurar: {', '.join(origenes_normal) or 'ninguno'}")
    print(f"orígenes con thinking:   {', '.join(origenes_pensando) or 'ninguno'}")


def tool_call_correcta(mensaje):
    return any(
        llamada["name"] == "sumar" and llamada["args"] == {"a": 21, "b": 21}
        for llamada in mensaje.tool_calls
    )


def medir_modelo(nombre=None):
    """Hace la prueba de tool calling REPETICIONES_LATENCIA veces y devuelve una fila para la tabla.

    Captura los errores de cada llamada (404, 410, timeout...) y sigue con la siguiente.
    """
    if nombre:
        os.environ["LLM_MODEL"] = nombre  # load_dotenv no pisa variables ya definidas
    fila = {"modelo": nombre or os.getenv("LLM_MODEL") or "(default)", "ok": 0, "razonamiento": 0,
            "tiempos": [], "error": ""}
    try:
        modelo = obtener_modelo()
    except RuntimeError as error:
        fila["error"] = str(error)
        print(f"\n### {fila['modelo']}: {fila['error']}")
        return fila
    fila["modelo"] = getattr(modelo, "model", None) or getattr(modelo, "model_name", None) or fila["modelo"]
    print(f"\n### {fila['modelo']}")
    con_tools = modelo.bind_tools([sumar])
    for intento in range(1, REPETICIONES_LATENCIA + 1):
        inicio = time.perf_counter()
        try:
            mensaje = con_tools.invoke(PREGUNTA)
        except Exception as error:
            fila["error"] = describir_error(error)
            print(f"  llamada {intento}: ERROR tras {time.perf_counter() - inicio:.1f}s -> {fila['error']}")
            continue
        segundos = time.perf_counter() - inicio
        ok, pensado = tool_call_correcta(mensaje), bool(razonamiento(mensaje))
        fila["tiempos"].append(segundos)
        fila["ok"] += ok
        fila["razonamiento"] += pensado
        print(f"  llamada {intento}: {segundos:.1f}s | tool call correcta: {'sí' if ok else 'no'}"
              f" | razonamiento: {'sí' if pensado else 'no'}")
    return fila


def imprimir_tabla(filas):
    encabezado = ("modelo", "ok tool call", "razonamiento", "segundos promedio", "error")
    renglones = []
    for f in filas:
        promedio = f"{sum(f['tiempos']) / len(f['tiempos']):.1f}" if f["tiempos"] else "-"
        renglones.append((f["modelo"], f"{f['ok']}/{REPETICIONES_LATENCIA}",
                          f"{f['razonamiento']}/{REPETICIONES_LATENCIA}", promedio, f["error"][:60]))
    anchos = [max(len(r[i]) for r in [encabezado, *renglones]) for i in range(len(encabezado))]
    linea = lambda r: " | ".join(c.ljust(a) for c, a in zip(r, anchos)).rstrip()
    print("\n" + linea(encabezado))
    print("-+-".join("-" * a for a in anchos))
    for r in renglones:
        print(linea(r))


def medir_latencia(modelos):
    load_dotenv()
    filas = [medir_modelo(m) for m in modelos] if modelos else [medir_modelo()]
    imprimir_tabla(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listar", action="store_true", help="lista los modelos de NVIDIA con soporte de tools")
    parser.add_argument("--latencia", action="store_true",
                        help=f"repite la prueba de tool calling {REPETICIONES_LATENCIA} veces y mide cada llamada")
    parser.add_argument("--modelos", help="modelos separados por coma; mide cada uno (implica --latencia)")
    args = parser.parse_args()
    modelos = [m.strip() for m in (args.modelos or "").split(",") if m.strip()]
    try:
        if args.listar:
            listar_modelos_nvidia()
        elif args.latencia or modelos:
            medir_latencia(modelos)
        else:
            probar()
    except RuntimeError as error:  # configuración: falta la key, proveedor inválido
        print(f"Error de configuración: {error}")
        return 1
    except Exception as error:
        print(f"Error al llamar al modelo: {describir_error(error)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
