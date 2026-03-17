"""
API 응답 모델 정의

일관된 응답 형식을 위한 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class BaseResponse(BaseModel):
    """기본 응답 모델"""
    success: bool = Field(..., description="요청 성공 여부")
    message: Optional[str] = Field(None, description="응답 메시지")
    error: Optional[str] = Field(None, description="에러 메시지")
    timestamp: datetime = Field(default_factory=datetime.now)


class DocumentInfo(BaseModel):
    """문서 정보"""
    filename: str
    source: str
    category_id: str = "general"
    chunk_count: Optional[int] = None


class SourceDocument(BaseModel):
    """출처 문서 정보"""
    content: str = Field(..., description="문서 내용 미리보기")
    source: str = Field(..., description="파일명")


class QueryResponse(BaseResponse):
    """질의응답 응답 모델"""
    answer: str = Field(default="", description="생성된 답변")
    sources: List[SourceDocument] = Field(default_factory=list)
    quality_score: float = Field(default=0.0, ge=0, le=1)
    confidence: str = Field(default="unknown")
    processing_time: float = Field(default=0.0)
    session_id: str = Field(default="")
    retry_count: int = Field(default=0)
    warnings: List[str] = Field(default_factory=list)

    # LLM 정보
    used_model: str = Field(default="N/A")
    model_selection_reason: str = Field(default="")

    # 상세 정보
    hybrid_search_used: bool = Field(default=False)
    rerank_scores: Optional[List[float]] = None


class LoadDocumentsResponse(BaseResponse):
    """문서 로드 응답 모델"""
    stats: Optional[Dict[str, Any]] = None
    collection_id: Optional[str] = None


class FileListResponse(BaseResponse):
    """파일 목록 응답 모델"""
    files: List[Dict[str, Any]] = Field(default_factory=list)
    count: int = Field(default=0)


class CategoryResponse(BaseResponse):
    """카테고리 응답 모델"""
    categories: List[Dict[str, Any]] = Field(default_factory=list)


class StatusResponse(BaseResponse):
    """시스템 상태 응답 모델"""
    ready: bool = Field(default=False)
    documents_loaded: int = Field(default=0)
    llm_provider: str = Field(default="")
    stats: Dict[str, Any] = Field(default_factory=dict)
