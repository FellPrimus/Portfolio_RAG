"""
RAG API Service - Main Application

Combined RAG API service with Query, Document, and Admin endpoints
Port: 8000
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .utils.clients import EmbeddingClient, LLMClient, QdrantService, RedisService
from .services.rag_service import RAGService
from .services.document_service import DocumentService
from .routers import query, documents, admin
from .routers.compat import documents as compat_documents
from .routers.compat import query as compat_query
from .routers.compat import categories as compat_categories
from .routers.compat import folders as compat_folders
from .routers.compat import files as compat_files

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global service instances
embedding_client: Optional[EmbeddingClient] = None
llm_client: Optional[LLMClient] = None
qdrant_service: Optional[QdrantService] = None
redis_service: Optional[RedisService] = None
rag_service: Optional[RAGService] = None
document_service: Optional[DocumentService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global embedding_client, llm_client, qdrant_service, redis_service
    global rag_service, document_service

    logger.info("Starting RAG API Service...")

    # Initialize clients
    embedding_client = EmbeddingClient(
        base_url=os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8001")
    )

    llm_client = LLMClient(
        base_url=os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8002")
    )

    qdrant_service = QdrantService(
        host=os.getenv("QDRANT_HOST", "qdrant"),
        port=int(os.getenv("QDRANT_PORT", "6333")),
        collection_name=os.getenv("QDRANT_COLLECTION", "documents"),
        embedding_dim=int(os.getenv("EMBEDDING_DIMENSION", "1024"))
    )

    redis_service = RedisService(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        password=os.getenv("REDIS_PASSWORD")
    )

    # Initialize services
    rag_service = RAGService(
        embedding_client=embedding_client,
        llm_client=llm_client,
        qdrant_service=qdrant_service,
        redis_service=redis_service,
        retrieval_k=int(os.getenv("RAG_RETRIEVAL_K", "5")),
        min_quality_score=float(os.getenv("RAG_MIN_QUALITY_SCORE", "0.6"))
    )

    document_service = DocumentService(
        embedding_client=embedding_client,
        qdrant_service=qdrant_service,
        redis_service=redis_service
    )

    # Ensure default collection exists
    try:
        qdrant_service.ensure_collection()
        logger.info(f"Qdrant collection ready: {qdrant_service.collection_name}")
    except Exception as e:
        logger.warning(f"Could not initialize Qdrant collection: {e}")

    # Test Redis connection
    try:
        if redis_service.ping():
            logger.info("Redis connection ready")
        else:
            logger.warning("Redis ping failed")
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")

    logger.info("RAG API Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down RAG API Service...")


app = FastAPI(
    title="RAG API Service",
    description="Combined RAG API with Query, Document, and Admin endpoints",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (microservice API)
app.include_router(query.router)
app.include_router(documents.router)
app.include_router(admin.router)

# Include RAGTest compatibility routers
app.include_router(compat_documents.router)
app.include_router(compat_query.router)
app.include_router(compat_categories.router)
app.include_router(compat_folders.router)
app.include_router(compat_files.router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag-api",
        "version": "1.0.0"
    }


@app.get("/readyz")
async def readiness_check():
    """Kubernetes readiness probe"""
    # Check if critical services are available
    checks = {}

    try:
        if redis_service and redis_service.ping():
            checks["redis"] = "ready"
        else:
            checks["redis"] = "not_ready"
    except Exception:
        checks["redis"] = "not_ready"

    try:
        collections = qdrant_service.list_collections() if qdrant_service else []
        checks["qdrant"] = "ready" if collections is not None else "not_ready"
    except Exception:
        checks["qdrant"] = "not_ready"

    # Service is ready if at least Qdrant is available
    if checks.get("qdrant") == "ready":
        return {"status": "ready", "checks": checks}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})


@app.get("/livez")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "RAG API Service",
        "version": "1.0.0",
        "endpoints": {
            "query": "/api/v1/query",
            "documents": "/api/v1/documents",
            "admin": "/api/v1/admin"
        },
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
