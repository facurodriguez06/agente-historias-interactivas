"""Tools del agente: RAG del mundo narrativo, estado de la partida, imágenes y exportación a PDF.

El id de la partida NO es un argumento de las tools: lo fija la aplicación en el
contexto de cada ejecución (ContextoPartida) y las tools lo leen de ahí. Así el LLM
no puede elegir ni inventar de qué partida lee o escribe.
"""

from dataclasses import dataclass
from functools import lru_cache

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

import estado_partida
import imagenes
from generar_pdf import generar_pdf
from ingestar import DB_DIR, MODELO_EMBEDDINGS, COLECCION


@dataclass
class ContextoPartida:
    """Datos que fija la aplicación en cada ejecución del agente (no los decide el LLM)."""

    id_partida: str


@lru_cache(maxsize=1)
def obtener_base():
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    return Chroma(
        collection_name=COLECCION,
        embedding_function=embeddings,
        persist_directory=str(DB_DIR),
    )


@tool
def buscar_contexto_narrativo(consulta: str) -> str:
    """Busca lugares, ambientación, pistas y reglas del universo narrativo usando RAG. Entrada: consulta en español. Devuelve fragmentos con su fuente."""
    if not DB_DIR.exists():
        return "ERROR: base RAG no creada. Ejecutar primero: python ingestar.py"
    try:
        documentos = obtener_base().similarity_search(consulta, k=3)
        if not documentos:
            return "No se encontró información relevante en el corpus."
        return "\n\n".join(
            f"Fuente: {doc.metadata.get('source', 'desconocida')}\nContenido: {doc.page_content}"
            for doc in documentos
        )
    except Exception as exc:
        return f"ERROR al consultar RAG: {type(exc).__name__}: {exc}"


@tool
def consultar_estado_partida(runtime: ToolRuntime[ContextoPartida]) -> dict:
    """Devuelve el estado de la partida en curso: capítulos escritos, decisiones tomadas, inventario, pistas descubiertas, si terminó y cuál es el siguiente paso. Sin argumentos."""
    try:
        estado = estado_partida.consultar_estado(runtime.context.id_partida)
        return {**estado, "siguiente_paso": estado_partida.siguiente_paso(estado)}
    except (ValueError, OSError) as e:
        return {"error": str(e)}


@tool
def registrar_decision(
    opcion: int,
    runtime: ToolRuntime[ContextoPartida],
    objetos_recogidos: list[str] | None = None,
    objetos_usados: list[str] | None = None,
    pistas_descubiertas: list[str] | None = None,
) -> dict:
    """Registra la opción (1, 2 o 3) que el usuario eligió en el capítulo pendiente y actualiza inventario y pistas.
    - objetos_recogidos: solo objetos que el usuario ELIGIÓ recoger con esta decisión.
    - objetos_usados: objetos que esta decisión usa; deben estar ya en el inventario.
    - pistas_descubiertas: pistas nuevas que el usuario descubrió con esta decisión (frases cortas).
    Los objetos deben llamarse exactamente como figura en las instrucciones. Si devuelve error, corregí y reintentá."""
    try:
        return estado_partida.registrar_decision(
            runtime.context.id_partida,
            opcion,
            objetos_recogidos,
            objetos_usados,
            pistas_descubiertas,
        )
    except (ValueError, OSError) as e:
        return {"error": str(e)}


@tool
def guardar_capitulo(
    titulo: str,
    texto: str,
    opciones: list[str],
    runtime: ToolRuntime[ContextoPartida],
) -> dict:
    """Guarda el capítulo que estás por mostrar: título, texto narrado y opciones. Capítulos 1 a 4: exactamente tres opciones. Capítulo 5 (desenlace): opciones=[] y la historia queda terminada."""
    try:
        return estado_partida.guardar_capitulo(
            runtime.context.id_partida, titulo, texto, opciones
        )
    except (ValueError, OSError) as e:
        return {"error": str(e)}


@tool
def generar_pdf_historia(runtime: ToolRuntime[ContextoPartida]) -> str:
    """Genera el PDF con los capítulos y decisiones de la partida. Solo funciona cuando la historia terminó (capítulo 5 guardado). Devuelve la ruta del archivo."""
    try:
        return generar_pdf(runtime.context.id_partida)
    except (ValueError, OSError) as e:
        return f"Error al generar PDF: {e}"


@tool
def buscar_imagen_capitulo(consulta: str, runtime: ToolRuntime[ContextoPartida]) -> dict:
    """Busca en Unsplash una foto de ambiente para el capítulo que acabás de guardar y la adjunta (se muestra en la interfaz y en el PDF). Llamala una vez por capítulo, justo después de guardar_capitulo.
    - consulta: 3 a 5 palabras EN INGLÉS sobre el lugar o clima de la escena, por ejemplo "foggy old mansion library" o "rainy greenhouse glass". No uses nombres de personas.
    Si devuelve error, reintentá UNA vez con una consulta más genérica (por ejemplo "foggy mansion"); si vuelve a fallar, seguí sin imagen."""
    try:
        id_partida = runtime.context.id_partida
        # Se valida antes de llamar a la API para no gastar consultas si no corresponde.
        numero, ya_usadas = estado_partida.capitulo_para_imagen(id_partida)
        foto = imagenes.obtener_imagen(consulta, excluir_ids=ya_usadas)
        estado_partida.adjuntar_imagen(id_partida, foto)
        return {
            "ok": True,
            "capitulo": numero,
            "autor": foto["autor"],
            "descripcion": foto["descripcion"],
        }
    except (ValueError, OSError) as e:
        return {"error": str(e)}
