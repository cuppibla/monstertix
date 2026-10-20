"""The MonsterTix workbench: one server, one port.

    /                 the page (web/dist), with client-side routes
    /api/…            content, checks, processes, files      (workbench/api.py)
    /svc/<name>/…     the venue, the agent's dev UI, MonsterTix, forwarded
    /content-images/  images the steps show
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from workbench import config
from workbench.api import router
from workbench.services import learning, procs, proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The venue is the world every step happens in, so it is always on: it
    # starts with the workbench and has no switch. A venue on Cloud Run
    # (VENUE_URL in .env) needs nothing started here.
    asyncio.get_running_loop().run_in_executor(None, procs.start, "venue")
    yield
    learning.shutdown()
    # Ctrl-C on the workbench stops everything it started, so no agent is
    # left holding sessions.db or a port.
    procs.stop_all()


app = FastAPI(title="MonsterTix workbench", lifespan=lifespan)


@app.middleware("http")
async def never_cache_the_api(request: Request, call_next):
    """Every /api answer describes this moment. Cloud Shell's proxy caching one
    is a process that looks stopped while it runs."""
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(router)


@app.api_route("/svc/{name}", methods=["GET"])
async def service_root(name: str, request: Request):
    return await proxy.forward(name, "", request)


@app.api_route("/svc/{name}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def service(name: str, path: str, request: Request):
    return await proxy.forward(name, path, request)


IMAGES = config.CONTENT / "images"
IMAGES.mkdir(parents=True, exist_ok=True)
app.mount("/content-images", StaticFiles(directory=IMAGES), name="content-images")
# The codelab's own figures, so a step can show them without a copy.
app.mount("/docs-img", StaticFiles(directory=config.ROOT / "docs" / "img"), name="docs-img")

if (config.WEB_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = config.WEB_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(config.WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})
else:
    @app.get("/", include_in_schema=False)
    def not_built():
        return PlainTextResponse("The page is not built. Run: cd web && npm install && npm run build")
