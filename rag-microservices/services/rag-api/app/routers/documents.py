"""
Documents Router - Document Management Endpoints

/api/v1/documents
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel

from ..models.schemas import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDeleteResponse,
    DocumentInfo
)
from ..services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


def get_document_service() -> DocumentService:
    """Dependency injection for document service"""
    from ..main import document_service
    if document_service is None:
        raise HTTPException(status_code=503, detail="Document service not initialized")
    return document_service


class TextUploadRequest(BaseModel):
    text: str
    source: str
    category: str = "general"
    collection: str = "documents"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default="general"),
    collection: str = Form(default="documents"),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload and index a document

    Supports: txt, md, html files
    """
    try:
        result = await document_service.upload_document(
            file=file.file,
            filename=file.filename,
            category=category,
            collection=collection
        )

        return DocumentUploadResponse(
            document_id=result.get("document_id", ""),
            status=result.get("status", "error"),
            chunks_count=result.get("chunks_count", 0),
            message=result.get("message", "")
        )

    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/text", response_model=DocumentUploadResponse)
async def upload_text(
    request: TextUploadRequest,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Upload and index plain text
    """
    try:
        result = await document_service.upload_text(
            text=request.text,
            source=request.source,
            category=request.category,
            collection=request.collection
        )

        return DocumentUploadResponse(
            document_id=result.get("document_id", ""),
            status=result.get("status", "error"),
            chunks_count=result.get("chunks_count", 0),
            message=result.get("message", "")
        )

    except Exception as e:
        logger.error(f"Error uploading text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    List all documents with pagination
    """
    try:
        result = document_service.list_documents(
            category=category,
            page=page,
            page_size=page_size
        )

        documents = [
            DocumentInfo(
                id=doc.get("id", ""),
                filename=doc.get("filename", ""),
                category=doc.get("category", ""),
                chunk_count=int(doc.get("chunk_count", 0)),
                created_at=doc.get("created_at", ""),
                metadata={k: v for k, v in doc.items() if k not in ["id", "filename", "category", "chunk_count", "created_at"]}
            )
            for doc in result.get("documents", [])
        ]

        return DocumentListResponse(
            documents=documents,
            total=result.get("total", 0),
            page=result.get("page", 1),
            page_size=result.get("page_size", 20)
        )

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Get document details
    """
    try:
        doc = document_service.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    doc_id: str,
    collection: str = "documents",
    document_service: DocumentService = Depends(get_document_service)
):
    """
    Delete a document and all its chunks
    """
    try:
        result = document_service.delete_document(doc_id, collection)

        return DocumentDeleteResponse(
            success=result.get("success", False),
            deleted_chunks=result.get("deleted_chunks", 0),
            message=result.get("message", "")
        )

    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
