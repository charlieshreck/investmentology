"""Single-port server: FastAPI API + PWA static files on port 80."""
import json
import logging
import uvicorn
from pathlib import Path
from fastapi import Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware

from investmentology.api.app import create_app


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge extra fields (request_id, method, path, status, duration_ms)
        for key in ("request_id", "method", "path", "status", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                log_data[key] = val
        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

PWA_DIR = Path(__file__).parent / "pwa" / "dist"

app = create_app(use_lifespan=True)


class ImmutableAssetHeaders(BaseHTTPMiddleware):
    """Set long-lived cache headers for content-hashed assets."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


app.add_middleware(ImmutableAssetHeaders)

# PWA static assets
app.mount("/assets", StaticFiles(directory=PWA_DIR / "assets"), name="assets")


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(
        PWA_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/sw.js")
async def sw():
    return FileResponse(
        PWA_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
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
    # Configure structured JSON logging
    logging.basicConfig(level=logging.INFO)
    for handler in logging.root.handlers:
        handler.setFormatter(JSONFormatter())

    uvicorn.run(app, host="0.0.0.0", port=80)
