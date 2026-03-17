"""
Pydantic models for RAG API
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# Query Models
class QueryRequest(BaseModel):
    question: str = Field(..., description="User's question")
    collection: str = Field(default="documents", description="Qdrant collection name")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    stream: bool = Field(default=False, description="Enable streaming response")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Filter conditions")


class SourceDocument(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceDocument]
    quality_score: float
    processing_time: float


# Document Models
class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    chunks_count: int
    message: str


class DocumentInfo(BaseModel):
    id: str
    filename: str
    category: str
    chunk_count: int
    created_at: datetime
    metadata: Dict[str, Any]


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int
    page: int
    page_size: int


class DocumentDeleteResponse(BaseModel):
    success: bool
    deleted_chunks: int
    message: str


# Admin Models
class CategoryInfo(BaseModel):
    id: str
    name: str
    description: Optional[str]
    document_count: int


class CategoryListResponse(BaseModel):
    categories: List[CategoryInfo]
    total: int


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


# Crawl Models
class CrawlRequest(BaseModel):
    url: str = Field(..., description="URL to crawl")
    depth: int = Field(default=1, ge=1, le=5, description="Crawl depth")
    category: str = Field(default="web", description="Category for crawled content")
    max_pages: int = Field(default=50, ge=1, le=200, description="Maximum pages to crawl")


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    message: str


class CrawlStatusResponse(BaseModel):
    task_id: str
    status: str
    pages_crawled: int
    pages_indexed: int
    errors: List[str]


# System Models
class SystemStatus(BaseModel):
    status: str
    services: Dict[str, str]
    collections: List[str]
    total_documents: int
