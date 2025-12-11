import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import chromadb
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.storage import StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding


def load_config(path: str = "files/config.json") -> Dict[str, Any]:
    """
    Loads config from files/config.json by default.
    Override with APP_CONFIG env var if needed.
    """
    path = os.getenv("APP_CONFIG", path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Required-ish defaults
    cfg.setdefault("chroma_path", "data/chroma")
    cfg.setdefault("collection_name", "rag_poc")

    # Retrieval params
    cfg.setdefault("top_k", 5)
    cfg.setdefault("fetch_k", cfg["top_k"])

    # Score filtering (IMPORTANT: score may be similarity or distance depending on stack/version)
    cfg.setdefault("score_type", "auto")  # "auto" | "similarity" | "distance"
    cfg.setdefault("min_score", None)     # used when score_type == "similarity"
    cfg.setdefault("max_distance", None)  # used when score_type == "distance"

    # Safety: if filtering removes everything, keep at least N best results anyway
    cfg.setdefault("min_results", 1)

    # Debugging
    cfg.setdefault("debug_retrieval", False)

    return cfg


@dataclass
class RetrievalPayload:
    user: str
    input: str
    model: Optional[str] = None


@dataclass
class RetrievedChunk:
    text: str
    score: Optional[float]
    metadata: Dict[str, Any]


class Retriever:
    """
    Retrieval-only component:
    - Connects to persistent Chroma
    - Uses LlamaIndex to retrieve top chunks
    - Supports thresholding to reduce irrelevant context (token burn)

    Config keys:
      - chroma_path, collection_name
      - fetch_k: retrieve N candidates from vector store
      - top_k: final max results returned (after filtering)
      - score_type: "similarity" (higher better) or "distance" (lower better) or "auto"
      - min_score: keep scores >= min_score (similarity mode)
      - max_distance: keep scores <= max_distance (distance mode)
      - min_results: if filtering removes everything, keep at least this many best results
      - debug_retrieval: prints retrieval diagnostics
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None):
        self.cfg = config or load_config()
        self.api_key = api_key or os.getenv("API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing API_KEY (set it in .env or env vars).")

        # Must be compatible with embeddings used during ingestion
        Settings.embed_model = OpenAIEmbedding(api_key=self.api_key)

        self._index: Optional[VectorStoreIndex] = None

    def _get_index(self, rebuild: bool = False) -> VectorStoreIndex:
        """
        Si rebuild=True, recrée l'index même si self._index existe.
        """
        if self._index is not None and not rebuild:
            return self._index

        client = chromadb.PersistentClient(path=self.cfg["chroma_path"])
        collection = client.get_or_create_collection(self.cfg["collection_name"])
        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        self._index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context,
        )
        return self._index


    @staticmethod
    def _safe_float(x: Any) -> Optional[float]:
        if x is None:
            return None
        try:
            return float(x)
        except Exception:
            return None

    def _detect_score_type(self, numeric_scores: List[float]) -> str:
        """
        Heuristic used only if score_type == "auto".
        If scores often exceed 1.5, we treat as distance.
        Otherwise we default to similarity.
        (If you want deterministic behavior, set score_type explicitly in config.)
        """
        if not numeric_scores:
            return "similarity"
        if max(numeric_scores) > 1.5:
            return "distance"
        return "similarity"

    def retrieve(self, payload: RetrievalPayload) -> List[RetrievedChunk]:
        query = (payload.input or "").strip()
        if not query:
            return []

        index = self._get_index()

        top_k = int(self.cfg.get("top_k", 5))
        fetch_k = int(self.cfg.get("fetch_k", top_k))
        min_results = int(self.cfg.get("min_results", 1))
        debug = bool(self.cfg.get("debug_retrieval", False))

        score_type_cfg = (self.cfg.get("score_type") or "auto").strip().lower()
        min_score = self._safe_float(self.cfg.get("min_score", None))
        max_distance = self._safe_float(self.cfg.get("max_distance", None))

        retr = index.as_retriever(similarity_top_k=fetch_k)
        results = retr.retrieve(query)  # list of NodeWithScore

        # Collect numeric scores for auto-detection
        numeric_scores: List[float] = []
        for r in results:
            sc = self._safe_float(getattr(r, "score", None))
            if sc is not None:
                numeric_scores.append(sc)

        score_type = score_type_cfg
        if score_type == "auto":
            score_type = self._detect_score_type(numeric_scores)

        if debug:
            print(f"[Retriever] chroma_path={self.cfg.get('chroma_path')} collection={self.cfg.get('collection_name')}")
            print(f"[Retriever] query='{query[:80]}' fetch_k={fetch_k} top_k={top_k}")
            print(f"[Retriever] score_type={score_type} min_score={min_score} max_distance={max_distance}")
            print(f"[Retriever] raw_results={len(results)}")
            for i, r in enumerate(results[:10], 1):
                sc = getattr(r, "score", None)
                node = getattr(r, "node", None) or r
                meta = getattr(node, "metadata", {}) or {}
                src = meta.get("source_file") or meta.get("file_name") or "unknown"
                txt = node.get_content() if hasattr(node, "get_content") else str(node)
                preview = txt[:80].replace("\n", " ")
                print(f"  - {i}: score={sc} src={src} preview={preview}")

        # Apply threshold filtering only when configured
        filtered = []

        if score_type == "similarity" and min_score is not None:
            for r in results:
                sc = self._safe_float(getattr(r, "score", None))
                if sc is None:
                    filtered.append(r)  # don't drop unknown scores in POC
                elif sc >= min_score:
                    filtered.append(r)

        elif score_type == "distance" and max_distance is not None:
            for r in results:
                sc = self._safe_float(getattr(r, "score", None))
                if sc is None:
                    filtered.append(r)
                elif sc <= max_distance:  # distance: lower is better
                    filtered.append(r)

        else:
            filtered = results  # no threshold active

        # Safety net: never return empty if we had any results (unless DB is truly empty)
        if not filtered and results and min_results > 0:
            filtered = results[:min_results]

        # Final cap
        filtered = filtered[:top_k]

        out: List[RetrievedChunk] = []
        for r in filtered:
            node = getattr(r, "node", None) or r
            sc = getattr(r, "score", None)
            text = node.get_content() if hasattr(node, "get_content") else str(node)
            metadata = dict(getattr(node, "metadata", {}) or {})
            out.append(RetrievedChunk(text=text, score=sc, metadata=metadata))

        return out
