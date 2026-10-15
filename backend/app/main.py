from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import accounts, admin, auth, documents, research
from app.core.bootstrap import ensure_admin
from app.core.config import settings
from app.domain.workspace import (
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    Unauthorized,
    WorkspaceError,
)
from app.infrastructure.ingest.storage import UploadTooLarge


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    ensure_admin()
    yield


app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route in (auth.router, accounts.router, documents.router, research.router, admin.router):
    app.include_router(route, prefix=settings.api_prefix)


@app.exception_handler(WorkspaceError)
async def workspace_error_handler(_, error: WorkspaceError):
    codes = {
        NotFound: 404,
        Conflict: 409,
        Unauthorized: 401,
        Forbidden: 403,
        InvalidInput: 422,
        UploadTooLarge: 413,
    }
    return JSONResponse(status_code=codes.get(type(error), 400), content={"detail": str(error)})


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
