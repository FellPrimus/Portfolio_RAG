"""
RAGTest 호환 Categories API

RAGTest의 /api/categories 엔드포인트들을 동일한 형식으로 제공합니다.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/categories", tags=["compat-categories"])


# ============================================================
# 기본 카테고리 정의 (RAGTest와 동일)
# ============================================================

DEFAULT_CATEGORIES = [
    {"id": "general", "name": "일반", "icon": "📄", "description": "일반 문서", "color": "#64748b"},
    {"id": "compute", "name": "Compute", "icon": "💻", "description": "서버, VM 관련", "color": "#3b82f6"},
    {"id": "storage", "name": "Storage", "icon": "💾", "description": "스토리지 관련", "color": "#8b5cf6"},
    {"id": "network", "name": "Networking", "icon": "🌐", "description": "네트워크 관련", "color": "#06b6d4"},
    {"id": "database", "name": "Database", "icon": "🗄️", "description": "데이터베이스 관련", "color": "#f59e0b"},
    {"id": "security", "name": "Security", "icon": "🔒", "description": "보안 관련", "color": "#ef4444"},
    {"id": "ai", "name": "AI/ML", "icon": "🤖", "description": "AI/ML 서비스", "color": "#10b981"},
    {"id": "container", "name": "Container", "icon": "📦", "description": "컨테이너/K8s", "color": "#6366f1"},
    {"id": "management", "name": "Management", "icon": "⚙️", "description": "관리/모니터링", "color": "#78716c"},
    {"id": "api", "name": "API 문서", "icon": "🔌", "description": "API 가이드", "color": "#ec4899"},
    {"id": "guide", "name": "가이드", "icon": "📖", "description": "사용자 가이드", "color": "#14b8a6"},
]


def get_category(category_id: str) -> dict:
    """카테고리 ID로 카테고리 정보 반환"""
    return _categories.get(category_id, {
        "id": category_id,
        "name": category_id,
        "icon": "📄",
        "description": "",
        "color": "#64748b"
    })

# 카테고리 저장소 (메모리 - 실제로는 Redis 사용 권장)
_categories = {cat["id"]: cat for cat in DEFAULT_CATEGORIES}


# ============================================================
# Request/Response Models
# ============================================================

class CategoryCreateRequest(BaseModel):
    id: str
    name: str
    icon: str = "📄"
    description: str = ""


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# API Endpoints
# ============================================================

@router.get("")
async def get_categories():
    """
    카테고리 목록 반환

    RAGTest 응답 형식:
    {
        'success': bool,
        'categories': [
            {
                'id': str,
                'name': str,
                'icon': str,
                'description': str,
                'document_count': int
            }
        ]
    }
    """
    try:
        # 문서 수 계산 (옵션)
        categories_with_count = []
        for cat_id, cat in _categories.items():
            cat_copy = cat.copy()
            cat_copy["document_count"] = 0  # 실제로는 Qdrant에서 카운트
            categories_with_count.append(cat_copy)

        return {
            "success": True,
            "categories": categories_with_count
        }

    except Exception as e:
        logger.error(f"카테고리 목록 조회 실패: {e}")
        return {"success": False, "error": str(e), "categories": []}


@router.post("")
async def create_category(request: CategoryCreateRequest):
    """새 카테고리 생성"""
    try:
        if request.id in _categories:
            return {"success": False, "error": f"카테고리 '{request.id}'가 이미 존재합니다."}

        _categories[request.id] = {
            "id": request.id,
            "name": request.name,
            "icon": request.icon,
            "description": request.description
        }

        return {
            "success": True,
            "message": f"카테고리 '{request.name}'이(가) 생성되었습니다.",
            "category": _categories[request.id]
        }

    except Exception as e:
        logger.error(f"카테고리 생성 실패: {e}")
        return {"success": False, "error": str(e)}


@router.put("/{category_id}")
async def update_category(category_id: str, request: CategoryUpdateRequest):
    """카테고리 수정"""
    try:
        if category_id not in _categories:
            return {"success": False, "error": f"카테고리 '{category_id}'를 찾을 수 없습니다."}

        cat = _categories[category_id]
        if request.name is not None:
            cat["name"] = request.name
        if request.icon is not None:
            cat["icon"] = request.icon
        if request.description is not None:
            cat["description"] = request.description

        return {
            "success": True,
            "message": f"카테고리가 수정되었습니다.",
            "category": cat
        }

    except Exception as e:
        logger.error(f"카테고리 수정 실패: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{category_id}")
async def delete_category(category_id: str):
    """카테고리 삭제"""
    try:
        if category_id not in _categories:
            return {"success": False, "error": f"카테고리 '{category_id}'를 찾을 수 없습니다."}

        if category_id == "general":
            return {"success": False, "error": "'일반' 카테고리는 삭제할 수 없습니다."}

        del _categories[category_id]

        return {
            "success": True,
            "message": f"카테고리가 삭제되었습니다."
        }

    except Exception as e:
        logger.error(f"카테고리 삭제 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{category_id}/stats")
async def get_category_stats(category_id: str):
    """카테고리 통계"""
    try:
        if category_id not in _categories:
            return {"success": False, "error": f"카테고리 '{category_id}'를 찾을 수 없습니다."}

        return {
            "success": True,
            "category": _categories[category_id],
            "stats": {
                "document_count": 0,
                "chunk_count": 0
            }
        }

    except Exception as e:
        logger.error(f"카테고리 통계 조회 실패: {e}")
        return {"success": False, "error": str(e)}
