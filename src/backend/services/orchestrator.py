from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Base folder for prompt files
PROMPTS_BASE_DIR = Path("files/prompts/")

FALLBACK_SYSTEM_PROMPT = (
    "You are a RAG assistant.\n\n"
    "Rules (must follow):\n"
    "1) Use ONLY the information present in the provided CONTEXT.\n"
    "2) If the answer is not explicitly stated in the CONTEXT, reply: "
    "\"Je ne sais pas d’après le contexte fourni.\"\n"
    "3) Do NOT add outside knowledge, examples, analogies, or background.\n"
    "4) Keep the answer concise and factual.\n"
    "5) If relevant, include short citations of the document."
)


def load_config(path: str = "files/config.json") -> Dict[str, Any]:
    path = os.getenv("APP_CONFIG", path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_prompt_path(cfg: Dict[str, Any]) -> Path:
    """
    config.json contains only a filename, e.g.:
      "prompt_system": "default_sytem_prompt.txt"

    We resolve it as:
      files/prompts/rag/<filename>
    """
    name = (cfg.get("prompt_system") or "").strip()
    if not name:
        # Default name if config is missing
        name = "default_sytem_prompt.txt"
    return PROMPTS_BASE_DIR / name


def load_system_prompt(cfg: Dict[str, Any]) -> str:
    """
    Loads the system prompt from the resolved prompt path.
    Falls back safely if missing/empty.
    """
    p = resolve_prompt_path(cfg)
    try:
        content = p.read_text(encoding="utf-8").strip()
        return content if content else FALLBACK_SYSTEM_PROMPT
    except FileNotFoundError:
        return FALLBACK_SYSTEM_PROMPT


@dataclass
class OrchestratorInput:
    user: str
    input: str
    model: str
    session_id: Optional[str] = None
    chat_history: Optional[List[Dict[str, str]]] = None


@dataclass
class RetrievedChunk:
    text: str
    score: Optional[float]
    metadata: Dict[str, Any]


@dataclass
class OrchestratorOutput:
    answer: str
    usage: Dict[str, int]
    sources: List[Dict[str, Any]]


class Orchestrator:
    """
    Orchestrates:
    - retrieval (vector store)
    - prompt assembly (system prompt + context + history)
    - LLM call (returns usage)
    """

    def __init__(
        self,
        retriever,      # retrieve(payload) -> List[RetrievedChunk]
        llm_client,     # chat(model, messages, temperature=...) -> (answer, usage_dict)
        config: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
    ):
        self.cfg = config or load_config()
        self.retriever = retriever
        self.llm_client = llm_client
        self.top_k = int(top_k if top_k is not None else self.cfg.get("top_k", 5))
        self.temperature = temperature

        # Priority: explicit override > file from config > fallback
        self.system_prompt = system_prompt or load_system_prompt(self.cfg)

    def _format_context(self, chunks: List[RetrievedChunk]) -> Tuple[str, List[Dict[str, Any]]]:
        sources: List[Dict[str, Any]] = []
        parts: List[str] = []

        for i, ch in enumerate(chunks, start=1):
            meta = ch.metadata or {}
            source_file = meta.get("source_file") or meta.get("file_name") or "unknown"
            source_path = meta.get("source_path") or meta.get("file_path") or ""
            chunk_txt = (ch.text or "").strip()

            parts.append(f"[{i}] source_file={source_file}\n{chunk_txt}")
            sources.append(
                {
                    "ref": i,
                    "source_file": source_file,
                    "source_path": source_path,
                    "score": ch.score,
                    "metadata": meta,
                }
            )

        return ("\n\n---\n\n".join(parts) if parts else ""), sources

    def build_messages(self, orch_in: OrchestratorInput, context_block: str) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]

        if orch_in.chat_history:
            messages.extend(orch_in.chat_history)

        messages.append(
            {
                "role": "user",
                "content": f"QUESTION:\n{orch_in.input}\n\nCONTEXT:\n{context_block}",
            }
        )
        return messages

    def run(self, orch_in: OrchestratorInput) -> OrchestratorOutput:
        payload = type("Payload", (), {})()
        payload.user = orch_in.user
        payload.input = orch_in.input
        payload.model = orch_in.model

        chunks: List[RetrievedChunk] = self.retriever.retrieve(payload)
        chunks = [c for c in chunks if getattr(c, "text", None)]  
        chunks = chunks[: self.top_k]

        if not chunks:
            return OrchestratorOutput(
                answer="Aucun document trouvé pour cette requête.",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                sources=[],
            )

        context_block, sources = self._format_context(chunks)
        messages = self.build_messages(orch_in, context_block)

        answer, usage = self.llm_client.chat(
            model=orch_in.model,
            messages=messages,
            temperature=self.temperature,
        )

        usage = usage or {}
        usage_out = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }

        return OrchestratorOutput(answer=answer, usage=usage_out, sources=sources)


# ---------------------------
# Local test (no retriever/LLM needed)
# ---------------------------
if __name__ == "__main__":
    cfg = load_config()
    prompt_path = resolve_prompt_path(cfg)

    print("Resolved prompt path:", prompt_path)
    system_prompt = load_system_prompt(cfg)
    print("\n--- LOADED SYSTEM PROMPT ---\n")
    print(system_prompt)
    print("\n--- END SYSTEM PROMPT ---\n")

    # Fake context + fake request: we only test prompt assembly (not calling LLM)
    fake_chunks = [
        RetrievedChunk(
            text="Le surhomme n’est pas un “super-héros”. C’est une figure de dépassement et de création de valeurs.",
            score=0.91,
            metadata={"source_file": "nietzsche_fr_poc.pdf", "doc_id": "abc123"},
        ),
        RetrievedChunk(
            text="L’éternel retour est une épreuve existentielle : vouloir revivre chaque instant à l’identique.",
            score=0.87,
            metadata={"source_file": "nietzsche_fr_poc.pdf", "doc_id": "abc123"},
        ),
    ]

    # Build an orchestrator with dummy deps (we won't call run())
    class DummyRetriever:
        def retrieve(self, payload):
            return fake_chunks

    class DummyLLM:
        def chat(self, model, messages, temperature=0.2):
            return "dummy", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    orch = Orchestrator(retriever=DummyRetriever(), llm_client=DummyLLM(), config=cfg)

    orch_in = OrchestratorInput(
        user="lionel.f",
        input="Explique le surhomme et l’éternel retour.",
        model=cfg.get("default_model", "gpt-4.1-mini"),
    )

    context_block, _sources = orch._format_context(fake_chunks)
    messages = orch.build_messages(orch_in, context_block)

    print("--- GENERATED MESSAGES PAYLOAD ---")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("--- END ---")
