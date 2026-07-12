from fastapi import FastAPI, Depends, HTTPException, Header
from .config import get_or_create_token, warm_up_model

app = FastAPI(title="Vina Backend")

# Eagerly warm up model on startup so we know immediately if packaging failed
print("[Vina] Starting backend...")
model = warm_up_model()

async def verify_token(x_vina_token: str = Header(None)):
    """Dependency to enforce the local shared secret."""
    expected_token = get_or_create_token()
    if x_vina_token != expected_token:
        raise HTTPException(status_code=403, detail="Unauthorized: Invalid or missing token.")
    return True

@app.get("/api/health")
async def health():
    """Unauthenticated health check for Phase 0 VM testing."""
    return {"status": "ok", "model_loaded": model is not None}

@app.get("/api/secure-health")
async def secure_health(authorized: bool = Depends(verify_token)):
    """Authenticated health check to verify token logic."""
    return {"status": "authorized ok"}