"""Primera tool del agente: consulta RAG con referencia a su documento fuente."""

from functools import lru_cache

from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from ingestar import DB_DIR, MODELO_EMBEDDINGS, COLECCION


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


from estado_partida import consultar_estado


@tool
def consultar_estado_partida(id_partida: str) -> dict:
    """Consulta el estado de una partida para conocer sus decisiones, inventario y progreso."""
    try:
        return consultar_estado(id_partida)
    except ValueError as e:
        return {"error": str(e)}


from estado_partida import registrar_decision as guardar_decision


@tool
def registrar_decision(id_partida: str, opcion: int) -> dict:
    """Registra la opción elegida por el usuario y actualiza el estado de la partida."""
    try:
        return guardar_decision(id_partida, opcion)
    except ValueError as e:
        return {"error": str(e)}


from estado_partida import guardar_capitulo as guardar_capitulo_json


@tool
def guardar_capitulo(
    id_partida: str,
    titulo: str,
    texto: str,
    opciones: list[str]
) -> dict:
    """Guarda un capítulo de la historia con su título, narración y tres opciones."""
    try:
        return guardar_capitulo_json(
            id_partida, titulo, texto, opciones
        )
    except ValueError as e:
        return {"error": str(e)}
