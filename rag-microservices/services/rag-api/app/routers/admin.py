"""
Admin Router - Admin and System Management Endpoints

/api/v1/admin
"""

import logging

from fastapi import APIRouter, HTTPException, Depends

from ..models.schemas import (
    CategoryInfo,
    CategoryListResponse,
    CategoryCreateRequest,
    SystemStatus
)
from ..utils.clients import RedisService, QdrantService, EmbeddingClient, LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def get_services():
    """Get all service instances"""
    from ..main import redis_service, qdrant_service, embedding_client, llm_client
    return {
        "redis": redis_service,
        "qdrant": qdrant_service,
        "embedding": embedding_client,
        "llm": llm_client
    }


@router.get("/status", response_model=SystemStatus)
async def system_status():
    """
    Get system status and health of all services
    """
    services = get_services()
    service_status = {}

    # Check Redis
    try:
        if services["redis"].ping():
            service_status["redis"] = "healthy"
        else:
            service_status["redis"] = "unhealthy"
    except Exception:
        service_status["redis"] = "unhealthy"

    # Check Qdrant
    try:
        collections = services["qdrant"].list_collections()
        service_status["qdrant"] = "healthy"
    except Exception:
        service_status["qdrant"] = "unhealthy"
        collections = []

    # Check Embedding Service
    try:
        if await services["embedding"].health_check():
            service_status["embedding"] = "healthy"
        else:
            service_status["embedding"] = "unhealthy"
    except Exception:
        service_status["embedding"] = "unhealthy"

    # Check LLM Gateway
    try:
        if await services["llm"].health_check():
            service_status["llm_gateway"] = "healthy"
        else:
            service_status["llm_gateway"] = "unhealthy"
    except Exception:
        service_status["llm_gateway"] = "unhealthy"

    # Get total documents
    total_docs = 0
    try:
        for coll in collections:
            info = services["qdrant"].get_collection_info(coll)
            total_docs += info.get("points_count", 0)
    except Exception:
        pass

    overall = "healthy" if all(s == "healthy" for s in service_status.values()) else "degraded"

    return SystemStatus(
        status=overall,
        services=service_status,
        collections=collections,
        total_documents=total_docs
    )


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories():
    """
    List all document categories
    """
    services = get_services()
    try:
        categories = services["redis"].list_categories()

        category_list = [
            CategoryInfo(
                id=cat.get("id", ""),
                name=cat.get("name", ""),
                description=cat.get("description", ""),
                document_count=int(cat.get("doc_count", 0))
            )
            for cat in categories
        ]

        return CategoryListResponse(
            categories=category_list,
            total=len(category_list)
        )

    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/categories")
async def create_category(request: CategoryCreateRequest):
    """
    Create a new category
    """
    services = get_services()
    try:
        import uuid
        category_id = str(uuid.uuid4())[:8]

        services["redis"].add_category(
            category_id=category_id,
            name=request.name,
            description=request.description or ""
        )

        return {
            "id": category_id,
            "name": request.name,
            "description": request.description,
            "document_count": 0
        }

    except Exception as e:
        logger.error(f"Error creating category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str):
    """
    Delete a category
    """
    services = get_services()
    try:
        cat = services["redis"].get_category(category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

        services["redis"].client.delete(f"category:{category_id}")

        return {"success": True, "message": f"Category {category_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def list_collections():
    """
    List all Qdrant collections
    """
    services = get_services()
    try:
        collections = services["qdrant"].list_collections()
        collection_info = []

        for coll in collections:
            info = services["qdrant"].get_collection_info(coll)
            collection_info.append(info)

        return {"collections": collection_info}

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections/{collection_name}")
async def create_collection(collection_name: str):
    """
    Create a new Qdrant collection
    """
    services = get_services()
    try:
        services["qdrant"].ensure_collection(collection_name)
        return {"success": True, "collection": collection_name}

    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """
    Delete a Qdrant collection
    """
    services = get_services()
    try:
        services["qdrant"].client.delete_collection(collection_name)
        return {"success": True, "message": f"Collection {collection_name} deleted"}

    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear all cached data
    """
    services = get_services()
    try:
        # Delete all cache keys
        keys = services["redis"].client.keys("cache:*")
        if keys:
            services["redis"].client.delete(*keys)

        return {"success": True, "cleared_keys": len(keys)}

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
