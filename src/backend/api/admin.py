from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import chromadb

from chromadb import PersistentClient
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from src.backend.services.logger import logger

ALLOWED_EXT = {".txt", ".html", ".csv"}  

def load_config(path: str = "files/config.json") -> Dict[str, Any]:
    path = os.getenv("APP_CONFIG", path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_data_dir(cfg: Dict[str, Any]) -> Path:
    data_path = cfg.get("data_path")
    if not data_path:
        raise RuntimeError("Missing 'data_path' in config.")
    p = Path(data_path).expanduser().resolve()
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        raise RuntimeError(f"data_path is not a directory: {p}")
    return p

def get_chroma_path(cfg: Dict[str, Any]) -> Path:
    chroma_path = cfg.get("chroma_path")
    if not chroma_path:
        raise RuntimeError("Missing 'chroma_path' in config.")
    p = Path(chroma_path).expanduser().resolve()
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        raise RuntimeError(f"chroma_path is not a directory: {p}")
    return p


def safe_resolve_under(base: Path, rel_path: str) -> Path:
    """
    Prevent path traversal: ensures final resolved path stays under base.
    """
    rel_path = rel_path.strip().lstrip("/").replace("\\", "/")
    if rel_path == "" or rel_path.startswith(".") and rel_path in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid path.")
    if ".." in rel_path.split("/"):
        raise HTTPException(status_code=400, detail="Path traversal detected.")
    p = (base / rel_path).resolve()
    if base not in p.parents and p != base:
        raise HTTPException(status_code=400, detail="Invalid path (outside data repo).")
    return p


def list_files(base: Path, recursive: bool = False) -> List[Dict[str, Any]]:
    pattern = "**/*" if recursive else "*"
    out: List[Dict[str, Any]] = []
    for p in base.glob(pattern):
        if not p.is_file():
            continue
        st = p.stat()
        out.append(
            {
                "name": p.name,
                "rel_path": str(p.relative_to(base)).replace("\\", "/"),
                "ext": p.suffix.lower(),
                "size_bytes": st.st_size,
                "modified_ts": int(st.st_mtime),
            }
        )
    out.sort(key=lambda x: x["modified_ts"], reverse=True)
    return out


router = APIRouter(prefix="/admin", tags=["admin"])
CFG = load_config()
DATA_DIR = get_data_dir(CFG)
CHROMA_PATH = Path(CFG.get("chroma_path", "data/chroma")).expanduser().resolve()




class UploadResponse(BaseModel):
    saved_as: str
    size_bytes: int


@router.get("/raw-files")
def admin_list_raw_files(
    recursive: bool = Query(False, description="List files recursively"),
    ext: Optional[str] = Query(None, description="Filter by extension, e.g. .pdf"),
):
    logger.info(f"[ADMIN] Listing raw files (recursive={recursive}, ext={ext})")
    files = list_files(DATA_DIR, recursive=recursive)
    if ext:
        ext_norm = ext.lower().strip()
        if not ext_norm.startswith("."):
            ext_norm = "." + ext_norm
        files = [f for f in files if f["ext"] == ext_norm]
    return {"data_path": str(DATA_DIR), "files": files}


@router.post("/raw-files/upload", response_model=UploadResponse)
async def admin_upload_raw_file(file: UploadFile = File(...)):
    """
    Uploads a file into the raw repo (DATA_DIR).
    This is what "inject a file into the repo" means.
    """
    filename = (file.filename or "").strip()
    logger.info(f"[ADMIN] Upload reçu : {filename}")
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = Path(filename).suffix.lower()
    if ALLOWED_EXT and ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Extension not allowed: {ext}")

    target = safe_resolve_under(DATA_DIR, filename)

    # Ensure parent folder exists (if you ever allow subpaths)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Save stream to disk
    size = 0
    with target.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)  # 1MB
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)

    logger.success(f"[ADMIN] Upload sauvegardé : {target}")
    return UploadResponse(saved_as=str(target.relative_to(DATA_DIR)).replace("\\", "/"), size_bytes=size)


@router.delete("/raw-files/{rel_path:path}")
def admin_delete_raw_and_chroma_file(rel_path: str):

    orchestrator = router.orchestrator 
    
    logger.warning(f"[ADMIN] Suppression du fichier : {rel_path}")

    # --- 1) Suppression dans DATA_DIR ---
    target = safe_resolve_under(DATA_DIR, rel_path)
    filename = target.name

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    target.unlink()
    logger.info(f"[ADMIN] Fichier supprimé : {rel_path}")

    # --- 2) Suppression dans Chroma ---
    try:
        client = PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_collection(CFG["collection_name"])

        # Récupération de TOUTES les métadatas (comme ton script)
        data = collection.get(include=["metadatas"])

        ids_to_delete = []
        for id_, meta in zip(data.get("ids", []), data.get("metadatas", [])):
            if meta and meta.get("file_name") == filename:
                ids_to_delete.append(id_)

        if ids_to_delete:
            logger.warning(
                f"[ADMIN] Suppression dans Chroma : {len(ids_to_delete)} chunks liés à {filename}"
            )
            collection.delete(ids=ids_to_delete)
            logger.success(
                f"[ADMIN] Embeddings supprimés pour {filename} — chunks={len(ids_to_delete)}"
            )
        else:
            logger.info(
                f"[ADMIN] Aucun embedding trouvé dans Chroma pour {filename}"
            )

    except Exception as e:
        logger.error(f"[ADMIN] Erreur lors de la suppression dans Chroma : {e}")
        raise HTTPException(
            status_code=500,
            detail=f"File deleted from data/, but failed removing embeddings from Chroma: {e}",
        )
    # Dans ton routeur admin_delete_raw_and_chroma_file
    # Après la suppression dans Chroma
    try:

        # Suppression terminée → on reconstruit le retriever
        # Assure-toi de passer la config et l'API key existantes
        cfg = orchestrator.retriever.cfg
        api_key = orchestrator.retriever.api_key

        # Recrée un retriever propre
        orchestrator.retriever = orchestrator.retriever.__class__(config=cfg, api_key=api_key)
        _ = orchestrator.retriever._get_index(rebuild=True)
        logger.info("[ADMIN] Retriever rafraîchi après suppression du fichier")
  # ou build_retriever() si tu as une fonction
        logger.info("[ADMIN] Retriever rafraîchi après suppression du fichier")
    except Exception as e:
        logger.error(f"[ADMIN] Impossible de rafraîchir le retriever : {e}")


    # --- 3) Retour ---
    return {
        "deleted_file": rel_path,
        "deleted_embeddings": len(ids_to_delete),
        "collection_name": CFG["collection_name"],
        "chroma_path": str(CHROMA_PATH),
    }



@router.post("/ingest/{rel_path:path}")
def admin_ingest_file(rel_path: str):
    """
    Chunk + embed + insert into Chroma for a file already present in the raw repo.
    """
    target = safe_resolve_under(DATA_DIR, rel_path)
    logger.info(f"[ADMIN] Ingestion demandée pour : {rel_path}")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing API_KEY (set it in .env).")

    try:
        # Import here to avoid circular imports at startup
        from src.backend.services.load_files import ingest_file
        logger.debug(f"[ADMIN] Appel ingest_file() pour : {target}")
        ingest_file(target, CFG, api_key)

        return {
            "status": "ok",
            "ingested": str(target.relative_to(DATA_DIR)).replace("\\", "/"),
            "collection_name": CFG.get("collection_name"),
            "chroma_path": CFG.get("chroma_path"),
        }

    except Exception as e:
        logger.error(f"[ADMIN] Erreur ingestion : {type(e).__name__} — {e}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@router.post("/raw-files/upload-and-ingest", response_model=UploadResponse)
async def admin_upload_and_ingest(file: UploadFile = File(...)):
    """
    Uploads a file into the raw repo (DATA_DIR) and immediately ingests it into Chroma.
    """
    filename = (file.filename or "").strip()
    logger.info(f"[ADMIN] Upload+Ingest reçu : {filename}")
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = Path(filename).suffix.lower()
    if ALLOWED_EXT and ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Extension not allowed: {ext}")

    api_key = os.getenv("API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing API_KEY (set it in .env).")

    target = safe_resolve_under(DATA_DIR, filename)
    target.parent.mkdir(parents=True, exist_ok=True)

    # Save upload to disk
    size = 0
    with target.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)

    # Ingest right away
    try:
        from src.backend.services.load_files import ingest_file
        logger.debug(f"[ADMIN] Ingestion immédiate de : {target}")
        ingest_file(target, CFG, api_key)
    except Exception as e:
        # Optional: rollback the uploaded file if ingestion fails
        try:
            if target.exists():
                target.unlink()
        except Exception:
            logger.error(f"[ADMIN] Erreur upload+ingest : {type(e).__name__} — {e}")
            pass
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {type(e).__name__}: {e}")

    return UploadResponse(
        saved_as=str(target.relative_to(DATA_DIR)).replace("\\", "/"),
        size_bytes=size,
    )


@router.delete("/vector/reset")
def admin_reset_vector_store():
    logger.warning("[ADMIN] Reset complet du vector store demandé")
    cfg = CFG
    client = chromadb.PersistentClient(path=str(cfg["chroma_path"]))

    # safest: delete the whole collection and recreate
    try:
        client.delete_collection(cfg["collection_name"])
    except Exception:
        # if it doesn't exist, ignore
        pass

    client.get_or_create_collection(cfg["collection_name"])
    logger.info(f"[ADMIN] Vector store reset : {cfg['collection_name']}")
    return {"status": "ok", "reset_collection": cfg["collection_name"], "chroma_path": cfg["chroma_path"]}



@router.delete("/vector/file/{rel_path:path}")
def admin_delete_vectors_for_raw_file(rel_path: str):
    logger.warning(f"[ADMIN] Suppression des embeddings pour : {rel_path}")
    target = safe_resolve_under(DATA_DIR, rel_path)
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Raw file not found.")

    client = chromadb.PersistentClient(path=str(CFG["chroma_path"]))
    col = client.get_or_create_collection(CFG["collection_name"])

    # Count before (ids are always returned; don't include "ids")
    before = col.get(where={"name": target.name})
    before_n = len(before.get("ids", []) or [])

    # Delete
    col.delete(where={"name": target.name})

    # Count after
    after = col.get(where={"name": target.name})
    after_n = len(after.get("ids", []) or [])

    logger.info(f"[ADMIN] Embeddings supprimés pour : {rel_path} (deleted={max(0,before_n-after_n)})")
    return {
        "status": "ok",
        "filename": target.name,
        "deleted": max(0, before_n - after_n),
        "remaining_for_file": after_n,
        "collection_count": col.count(),
        "collection_name": CFG["collection_name"],
    }

@router.delete("/vector/wipe")
def admin_wipe_vector_store():
    """
    DANGER: Deletes the entire Chroma collection (all vectors) and recreates it empty.
    """
    client = chromadb.PersistentClient(path=str(CFG["chroma_path"]))
    name = CFG["collection_name"]

    # Delete collection (nukes all vectors)
    try:
        client.delete_collection(name)
    except Exception:
        # If it doesn't exist, that's fine
        pass

    # Recreate empty collection
    client.get_or_create_collection(name)

    # Verify
    col = client.get_collection(name)
    return {
        "status": "ok",
        "action": "wipe",
        "chroma_path": CFG["chroma_path"],
        "collection_name": name,
        "count": col.count(),
    }
