from fastapi import Header, HTTPException
import os

VALID_API_KEY = os.getenv("FRONTEND_API_KEY")

if not VALID_API_KEY:
    raise RuntimeError("Missing FRONTEND_API_KEY in .env")

def verify_api_key(x_api_key: str = Header(..., description="API Key for authentication")):
    """
    Dependency qui vérifie la présence et validité de l'API Key.
    À utiliser dans chaque endpoint protégé.
    """
    if x_api_key != VALID_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key  