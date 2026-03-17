"""
Query Router - RAG Query Endpoints

/api/v1/query
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from ..models.schemas import QueryRequest, QueryResponse
from ..services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/query", tags=["Query"])


def get_rag_service() -> RAGService:
    """Dependency injection for RAG service"""
    from ..main import rag_service
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG service not initialized")
    return rag_service


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Process RAG query

    Returns AI-generated answer based on retrieved documents
    """
    try:
        if request.stream:
            # Return streaming response
            async def generate():
                async for chunk in rag_service.query_stream(
                    question=request.question,
                    collection=request.collection,
                    top_k=request.top_k,
                    filter_conditions=request.filter
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )

        # Non-streaming response
        result = await rag_service.query(
            question=request.question,
            collection=request.collection,
            top_k=request.top_k,
            filter_conditions=request.filter
        )

        return QueryResponse(**result)

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def query_stream(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """
    Stream RAG query response

    Returns Server-Sent Events with answer chunks
    """
    async def generate():
        try:
            async for chunk in rag_service.query_stream(
                question=request.question,
                collection=request.collection,
                top_k=request.top_k,
                filter_conditions=request.filter
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )
