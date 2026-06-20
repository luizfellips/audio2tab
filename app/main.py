from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.outputs import router as outputs_router
from app.api.routes.transcribe import router as transcribe_router
from app.core.config import settings


def create_app() -> FastAPI:
    settings.ensure_directories()

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(transcribe_router)
    app.include_router(outputs_router)

    static_dir = settings.frontend_dir / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        index_path = settings.frontend_dir / "index.html"
        if not index_path.exists():
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Frontend not found")
        return FileResponse(index_path, media_type="text/html")

    return app


app = create_app()
