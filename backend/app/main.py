"""FastAPI main application entry point for Enterprise Knowledge Agent.

Initializes application lifecycle, middleware stack, global error handlers,
and registers API routers.
"""

import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure backend directory is in sys.path when invoked directly
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import CorrelationIdMiddleware, get_logger, setup_logging
from app.core.telemetry import init_telemetry

settings = get_settings()
setup_logging(log_level=settings.log_level, log_format=settings.log_format)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle events."""
    logger.info(
        "Starting Enterprise Knowledge Agent",
        app_name=settings.app_name,
        env=settings.app_env,
        debug=settings.app_debug,
    )
    init_telemetry(settings)

    # Initialize database schemas
    try:
        from app.db.session import init_db
        await init_db()
    except Exception as exc:
        logger.warning("Database schema auto-init warning", error=str(exc))

    # Auto-index sample corpus if available
    try:
        from pathlib import Path

        corpus_path = Path(settings.sample_corpus_dir)
        if corpus_path.exists():
            from app.domain.models import DocumentChunk
            from app.ingestion.chunkers.structure_chunker import StructureChunker
            from app.ingestion.connectors.local_folder import LocalFolderConnector
            from app.retrieval.qdrant_client import QdrantService

            connector = LocalFolderConnector(folder_path=str(corpus_path))
            chunker = StructureChunker()
            all_chunks: list[DocumentChunk] = []

            for file_path in corpus_path.rglob("*.md"):
                try:
                    doc = connector._build_raw_document(file_path)
                    all_chunks.extend(chunker.chunk_document(doc))
                except Exception:
                    pass

            if all_chunks:
                qdrant = QdrantService(settings)
                qdrant.upsert_chunks_sync(all_chunks)
                logger.info("Indexed sample corpus into Qdrant", chunk_count=len(all_chunks))
    except Exception as exc:
        logger.warning("Could not auto-index sample corpus on startup", error=str(exc))

    yield
    logger.info("Shutting down Enterprise Knowledge Agent cleanly")


def create_app() -> FastAPI:
    """Application factory for FastAPI instance."""
    app = FastAPI(
        title=settings.app_name,
        description="Production-grade, permission-aware, agentic RAG platform",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    # Middleware Stack (Execution order is bottom to top)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

    # Register Error Handlers
    register_error_handlers(app)

    # Register Routers
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
