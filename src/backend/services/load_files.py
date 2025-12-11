import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

import chromadb
from llama_index.core import Document, Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.storage import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from src.backend.services.logger import logger


def load_config(path: str = "files/config.json") -> Dict[str, Any]:
    path = os.getenv("APP_CONFIG", path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg.setdefault("data_path", "data")
    cfg.setdefault("chroma_path", "data/chroma")
    cfg.setdefault("collection_name", "rag_poc")
    cfg.setdefault("chunk_size", 800)
    cfg.setdefault("chunk_overlap", 120)
    return cfg


def stable_doc_id(file_path: Path) -> str:
    h = hashlib.sha256()
    h.update(str(file_path).encode("utf-8"))
    h.update(file_path.read_bytes())
    return h.hexdigest()[:24]


def find_file_by_name(data_dir: Path, filename: str) -> Path:
    matches = [p for p in data_dir.rglob(filename) if p.is_file()]
    if not matches:
        raise FileNotFoundError(f"File '{filename}' not found under {data_dir}")
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple files named '{filename}' found under {data_dir}:\n"
            + "\n".join(str(m) for m in matches)
        )
    return matches[0]


def load_single_file_as_documents(file_path: Path) -> List[Document]:
    logger.debug(f"[INGEST] Chargement du fichier brut : {file_path}")
    reader = SimpleDirectoryReader(
        input_dir=str(file_path.parent),
        required_exts=[file_path.suffix.lower()],
        recursive=False,
    )
    docs = reader.load_data()

    # Best-effort filter to only the requested file
    filtered: List[Document] = []
    for d in docs:
        meta = d.metadata or {}
        file_name = (meta.get("file_name") or meta.get("filename") or "").strip()
        file_path_meta = (meta.get("file_path") or "").strip()

        if file_name and file_name != file_path.name:
            continue
        if file_path_meta and Path(file_path_meta).name != file_path.name:
            continue
        filtered.append(d)
    logger.info(f"[INGEST] Documents chargés depuis {file_path} : {len(filtered) if filtered else len(docs)}")
    return filtered if filtered else docs


def ingest_file(file_path: Path, cfg: Dict[str, Any], api_key: str) -> None:
    logger.info(f"[INGEST] Début ingestion : {file_path}")
    # Configure chunking + embeddings
    Settings.node_parser = SentenceSplitter(
        chunk_size=int(cfg["chunk_size"]),
        chunk_overlap=int(cfg["chunk_overlap"]),
    )
    Settings.embed_model = OpenAIEmbedding(api_key=api_key)

    docs = load_single_file_as_documents(file_path)
    logger.debug(f"[INGEST] Nombre de documents bruts : {len(docs)}")
    if not docs:
        raise RuntimeError(f"No documents loaded from {file_path}")

    # Add simple metadata
    doc_id = stable_doc_id(file_path)
    ingested_at = int(time.time())
    enriched_docs: List[Document] = []
    logger.debug(f"[INGEST] Nombre de chunks générés : {len(enriched_docs)}")
    for d in docs:
        meta = dict(d.metadata or {})
        meta.update(
            {
                "source_file": file_path.name,
                "source_path": str(file_path),
                "file_ext": file_path.suffix.lower(),
                "doc_id": doc_id,
                "ingested_at": ingested_at,
            }
        )
        enriched_docs.append(Document(text=d.text, metadata=meta))

    # Persistent Chroma
    chroma_path = Path(cfg["chroma_path"])
    chroma_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"[INGEST] Connexion à la DB Chroma : {chroma_path}")
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(cfg["collection_name"])
    vector_store = ChromaVectorStore(chroma_collection=collection, store_text=True)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    logger.debug("[INGEST] Indexation des documents dans Chroma…")
    _ = VectorStoreIndex.from_documents(
        enriched_docs,
        storage_context=storage_context,
        show_progress=True,
    )

    logger.success(
    f"[INGEST] Ingestion terminée\n"
    f"   File: {file_path}\n"
    f"   doc_id: {doc_id}\n"
    f"   Inserted documents: {len(enriched_docs)}\n"
    f"   Collection: {cfg['collection_name']}\n"
    f"   Chroma path: {chroma_path}"
    )


def repl() -> int:
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        print("ERROR: Missing API_KEY (set it in .env).")
        return 1

    cfg = load_config()
    data_dir = Path(cfg["data_path"])
    if not data_dir.exists():
        print(f"ERROR: data_path does not exist: {data_dir}")
        return 1

    print("RAG POC Ingestion (type 'exit' to quit)")
    print(f"- Raw data folder: {data_dir}")
    print(f"- Chroma folder:   {cfg['chroma_path']}")
    print(f"- Collection:      {cfg['collection_name']}\n")

    while True:
        filename = input("Filename to ingest > ").strip()
        if not filename:
            continue
        if filename.lower() in {"exit", "quit", "q"}:
            print("Bye 👋")
            return 0

        try:
            file_path = find_file_by_name(data_dir, filename)
            ingest_file(file_path, cfg, api_key)
        except Exception as e:
            print(f"❌ {type(e).__name__}: {e}")
        print()  # spacing


if __name__ == "__main__":
    raise SystemExit(repl())
