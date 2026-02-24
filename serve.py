"""Single-port server: FastAPI API + PWA static files on port 80."""
import os
import uvicorn
from pathlib import Path
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from investmentology.api.app import create_app

PWA_DIR = Path(__file__).parent / "pwa" / "dist"

app = create_app(use_lifespan=True)


# Temporary: force-clear PWA caches on mobile. Remove after users update.
NUKE_CACHES = os.environ.get("NUKE_PWA_CACHES", "1") == "1"


class ClearSiteDataMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if NUKE_CACHES and not request.url.path.startswith("/api/invest/auth"):
            response.headers["Clear-Site-Data"] = '"cache", "storage"'
        return response


if NUKE_CACHES:
    app.add_middleware(ClearSiteDataMiddleware)

# PWA static assets
app.mount("/assets", StaticFiles(directory=PWA_DIR / "assets"), name="assets")


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(PWA_DIR / "manifest.webmanifest")


@app.get("/sw.js")
async def sw():
    return FileResponse(
        PWA_DIR / "sw.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Clear-Site-Data": '"cache", "storage"',
        },
    )


@app.get("/registerSW.js")
async def register_sw():
    return FileResponse(PWA_DIR / "registerSW.js", media_type="application/javascript")


@app.get("/workbox-{rest:path}")
async def workbox(rest: str):
    return FileResponse(PWA_DIR / f"workbox-{rest}", media_type="application/javascript")


# SPA fallback: all non-API, non-asset routes serve index.html
@app.get("/{full_path:path}")
async def spa_fallback(request: Request, full_path: str):
    file_path = PWA_DIR / full_path
    if full_path and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(
        PWA_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
