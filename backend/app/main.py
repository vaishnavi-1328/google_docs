from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    startup_assertions,
)
from .routes import attachments as attachments_routes
from .routes import auth as auth_routes
from .routes import docs as docs_routes
from .routes import export as export_routes
from .routes import sharing as sharing_routes
from .routes import versions as versions_routes
from .settings import get_settings
from .ws import docs as docs_ws

settings = get_settings()
startup_assertions()

# FastAPI mounts Swagger at /docs by default, which shadows our /docs router.
# Move the API docs UI to /api-docs so /docs serves the document list.
app = FastAPI(title="Collab Docs", version="0.1.0", docs_url="/api-docs", redoc_url="/api-redoc")

# Middleware runs in reverse registration order. We want CORS outermost so
# its headers are attached even to 429 / 500 responses returned early by
# RateLimit and SecurityHeaders below it. Registering CORS LAST here puts
# it at the top of the stack.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(docs_routes.router)
app.include_router(sharing_routes.router)
app.include_router(export_routes.router)
app.include_router(versions_routes.router)
app.include_router(attachments_routes.router)
app.include_router(docs_ws.router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
