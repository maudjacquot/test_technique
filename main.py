import json
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.backend.services.retriever import Retriever
from src.backend.services.orchestrator import Orchestrator, OrchestratorInput
from src.backend.services.llm_client import OpenAILLMClient

from src.backend.api.admin import router as admin_router
from src.backend.services.logger import logger

def load_config(path: str = "files/config.json") -> Dict[str, Any]:
    path = os.getenv("APP_CONFIG", path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg.setdefault("default_model", "gpt-4.1-mini")
    cfg.setdefault("top_k", 5)
    # prompt_system is just a filename; orchestrator will prefix it with files/prompts/rag/
    cfg.setdefault("prompt_system", "default_sytem_prompt.txt")
    return cfg


load_dotenv()
CONFIG = load_config()
DEFAULT_MODEL = CONFIG["default_model"]

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("Missing API_KEY. Put it in your .env file or environment variables.")

app = FastAPI(title="RAG POC API", version="0.7.0")
logger.info("Starting RAG POC API...")

app.include_router(admin_router)

# Core components
retriever = Retriever(config=CONFIG, api_key=API_KEY)
llm_client = OpenAILLMClient(api_key=API_KEY)
orchestrator = Orchestrator(
    retriever=retriever,
    llm_client=llm_client,
    config=CONFIG,
    top_k=int(CONFIG.get("top_k", 5)),
)

admin_router.orchestrator = orchestrator

@app.get("/health")
def health():
    logger.debug("Health check appelé")
    return {
        "status": "ok",
        "default_model": DEFAULT_MODEL,
        "collection_name": CONFIG.get("collection_name"),
    }


class EntryRequest(BaseModel):
    user: str = Field(..., description="Username of the logged user")
    input: str = Field(..., description="The request sent by the user")
    model: Optional[str] = Field(None, description="Optional override of model; default comes from config.json")


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChoiceMessage(BaseModel):
    role: str
    content: str


class Choice(BaseModel):
    index: int
    message: ChoiceMessage
    finish_reason: str = "stop"


class ChatCompletionsResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


@app.post("/v1/chat/completions", response_model=ChatCompletionsResponse)
def chat_completions(req: EntryRequest):
    if not req.user.strip():
        raise HTTPException(status_code=400, detail="Field 'user' must not be empty.")
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="Field 'input' must not be empty.")

    model_to_use = (req.model or DEFAULT_MODEL).strip()

    out = orchestrator.run(
        OrchestratorInput(
            user=req.user.strip(),
            input=req.input.strip(),
            model=model_to_use,
        )
    )

    created = int(time.time())
    return ChatCompletionsResponse(
        id=f"chatcmpl_poc_{created}",
        created=created,
        model=model_to_use,
        choices=[
            Choice(
                index=0,
                message=ChoiceMessage(role="assistant", content=out.answer),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=out.usage["prompt_tokens"],
            completion_tokens=out.usage["completion_tokens"],
            total_tokens=out.usage["total_tokens"],
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
