"""Construye la base vectorial local a partir de los tres Markdown del corpus."""
from pathlib import Path
import shutil

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
DB_DIR = ROOT / "chroma_db"
MODELO_EMBEDDINGS = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLECCION = "mundo_misterio"


def main():
    documentos = []
    for ruta in sorted(CORPUS.glob("*.md")):
        documentos.append(
            Document(page_content=ruta.read_text(encoding="utf-8"), metadata={"source": ruta.name})
        )
    if len(documentos) < 3:
        raise RuntimeError("Se necesitan al menos 3 documentos en corpus/.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=650, chunk_overlap=100)
    fragmentos = splitter.split_documents(documentos)
    print(f"Documentos: {len(documentos)}; fragmentos: {len(fragmentos)}")
    print("Cargando modelo de embeddings (la primera vez puede descargar archivos)...")
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)

    # En este prototipo la ingesta reconstruye el índice por completo.
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)
    Chroma.from_documents(
        documents=fragmentos,
        embedding=embeddings,
        persist_directory=str(DB_DIR),
        collection_name=COLECCION,
    )
    print("Base vectorial creada correctamente en chroma_db/")


if __name__ == "__main__":
    main()
