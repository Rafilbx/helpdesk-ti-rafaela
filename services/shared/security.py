import os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Header, HTTPException

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
ALGORITHM = "HS256"

def create_access_token(user_id: int, email: str, role: str) -> str:
    if len(SECRET_KEY) < 32:
        raise RuntimeError("JWT_SECRET_KEY precisa ter pelo menos 32 caracteres.")
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "email": email, "role": role,
               "iat": now, "exp": now + timedelta(hours=8)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Autenticação necessária.")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], SECRET_KEY, algorithms=[ALGORITHM])
        return {"id": int(payload["sub"]), "email": payload["email"], "role": payload["role"]}
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

def require_roles(*roles):
    def dependency(user=__import__("fastapi").Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return user
    return dependency
