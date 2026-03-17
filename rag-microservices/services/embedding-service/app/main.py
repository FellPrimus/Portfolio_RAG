"""
Embedding Service API

FastAPI service for E5 embeddings generation
Port: 8001
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .embeddings import embedding_model

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Request/Response Models
class DocumentEmbeddingRequest(BaseModel):
    texts: List[str] = Field(..., description="List of document texts to embed")
    batch_size: int = Field(default=32, ge=1, le=128, description="Batch size for encoding")
    normalize: bool = Field(default=True, description="Normalize embeddings to unit length")


class QueryEmbeddingRequest(BaseModel):
    text: str = Field(..., description="Query text to embed")
    normalize: bool = Field(default=True, description="Normalize embedding to unit length")


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    dimension: int
    count: int


class QueryEmbeddingResponse(BaseModel):
    embedding: List[float]
    dimension: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: str
    dimension: Optional[int]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: Pre-load the model
    logger.info("Starting Embedding Service...")
    try:
        embedding_model.load_model()
        logger.info("Model pre-loaded successfully")
    except Exception as e:
        logger.error(f"Failed to pre-load model: {e}")
        # Continue anyway - model will load on first request

    yield

    # Shutdown
    logger.info("Shutting down Embedding Service...")


app = FastAPI(
    title="Embedding Service",
    description="E5 Multilingual Embedding Service for RAG System",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if embedding_model.is_ready() else "loading",
        model_loaded=embedding_model.is_ready(),
        model_name=embedding_model.model_name,
        dimension=embedding_model.dimension if embedding_model.is_ready() else None
    )


@app.get("/readyz")
async def readiness_check():
    """Kubernetes readiness probe"""
    if embedding_model.is_ready():
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Model not loaded yet")


@app.get("/livez")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}


@app.post("/embed/documents", response_model=EmbeddingResponse)
async def embed_documents(request: DocumentEmbeddingRequest):
    """
    Generate embeddings for documents

    Uses "passage:" prefix for E5 model compatibility
    """
    try:
        if not request.texts:
            return EmbeddingResponse(
                embeddings=[],
                dimension=embedding_model.dimension,
                count=0
            )

        embeddings = embedding_model.embed_documents(
            texts=request.texts,
            batch_size=request.batch_size,
            normalize=request.normalize
        )

        return EmbeddingResponse(
            embeddings=embeddings,
            dimension=embedding_model.dimension,
            count=len(embeddings)
        )
    except Exception as e:
        logger.error(f"Error embedding documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/query", response_model=QueryEmbeddingResponse)
async def embed_query(request: QueryEmbeddingRequest):
    """
    Generate embedding for a search query

    Uses "query:" prefix for E5 model compatibility
    """
    try:
        embedding = embedding_model.embed_query(
            text=request.text,
            normalize=request.normalize
        )

        return QueryEmbeddingResponse(
            embedding=embedding,
            dimension=embedding_model.dimension
        )
    except Exception as e:
        logger.error(f"Error embedding query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/info")
async def model_info():
    """Get model information"""
    return {
        "model_name": embedding_model.model_name,
        "dimension": embedding_model.dimension if embedding_model.is_ready() else None,
        "device": embedding_model.device,
        "ready": embedding_model.is_ready()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
