import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="HelpDesk API Gateway", version="1.1.0")

STATIC_DIR = Path(__file__).parent / "static"

ROUTES = [
    ("/auth", "USERS_URL"),
    ("/users", "USERS_URL"),
    ("/assets", "INVENTORY_URL"),
    ("/tickets", "TICKETS_URL"),
]
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def frontend_script():
    return FileResponse(STATIC_DIR / "app.js", media_type="application/javascript")


@app.get("/style.css", include_in_schema=False)
def frontend_styles():
    return FileResponse(STATIC_DIR / "style.css", media_type="text/css")


@app.get("/health")
def health():
    return {"service": "gateway", "status": "ok"}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request):
    full_path = "/" + path
    match = next(
        ((prefix, env) for prefix, env in ROUTES
         if full_path == prefix or full_path.startswith(prefix + "/")),
        None,
    )
    if not match:
        raise HTTPException(404, "Rota não encontrada.")

    prefix, env = match
    base = os.getenv(env)
    if not base:
        raise HTTPException(503, "Serviço indisponível.")

    url = f"{base}{full_path}"
    if request.url.query:
        url += f"?{request.url.query}"

    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP
    }
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            upstream = await client.request(
                request.method, url, headers=headers, content=body
            )
    except httpx.HTTPError:
        raise HTTPException(503, "Falha na comunicação com o serviço.")

    response_headers = {
        key: value for key, value in upstream.headers.items()
        if key.lower() not in HOP_BY_HOP
    }
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
