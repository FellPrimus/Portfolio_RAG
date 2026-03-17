"""
RAGTest 호환 Folders API - Redis 기반 영속 저장소

설계 원칙:
- 폴더 데이터는 Redis에 영속 저장 (파드 재시작 후에도 유지)
- 문서는 최대 하나의 폴더에만 속함 (exclusive membership)
- 문서 이동은 백엔드에서 원자적으로 처리 (remove + add가 하나의 연산)
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/folders", tags=["compat-folders"])


# ============================================================
# Redis key 설계
# ============================================================
# folders:all          → Set: 모든 folder_id
# folder:{id}          → Hash: 폴더 메타데이터
# folder:{id}:docs     → Set: 해당 폴더에 속한 doc_id들
# doc_folder:{doc_id}  → String: 해당 문서가 속한 folder_id (없으면 키 없음)

def _folder_key(folder_id: str) -> str:
    return f"folder:{folder_id}"

def _folder_docs_key(folder_id: str) -> str:
    return f"folder:{folder_id}:docs"

def _doc_folder_key(doc_id: str) -> str:
    return f"doc_folder:{doc_id}"


# ============================================================
# Redis 클라이언트
# ============================================================

_redis_client = None

def _get_redis():
    """Redis 클라이언트 반환 (지연 초기화)"""
    global _redis_client
    if _redis_client is None:
        from app.utils.clients import RedisService
        svc = RedisService()
        _redis_client = svc.client
    return _redis_client


# ============================================================
# Redis CRUD 헬퍼
# ============================================================

def _get_folder(folder_id: str) -> Optional[dict]:
    """폴더 메타데이터 조회"""
    r = _get_redis()
    data = r.hgetall(_folder_key(folder_id))
    if not data:
        return None
    folder = dict(data)
    # parent_id가 빈 문자열이면 None으로 복원
    if folder.get("parent_id") == "":
        folder["parent_id"] = None
    return folder


def _save_folder(folder: dict):
    """폴더 메타데이터 저장"""
    r = _get_redis()
    folder_id = folder["id"]
    # None 값을 빈 문자열로 변환 (Redis hash는 None 미지원)
    serialized = {k: ("" if v is None else str(v)) for k, v in folder.items()}
    r.hset(_folder_key(folder_id), mapping=serialized)
    r.sadd("folders:all", folder_id)


def _delete_folder(folder_id: str):
    """폴더와 관련 데이터 삭제"""
    r = _get_redis()
    # 폴더에 속한 문서들의 doc_folder 역인덱스 제거
    for doc_id in r.smembers(_folder_docs_key(folder_id)):
        current = r.get(_doc_folder_key(doc_id))
        if current == folder_id:
            r.delete(_doc_folder_key(doc_id))
    r.delete(_folder_key(folder_id))
    r.delete(_folder_docs_key(folder_id))
    r.srem("folders:all", folder_id)


def _get_all_folder_ids() -> List[str]:
    """모든 폴더 ID 목록"""
    r = _get_redis()
    return list(r.smembers("folders:all"))


def _folder_exists(folder_id: str) -> bool:
    return _get_redis().exists(_folder_key(folder_id)) > 0


def _get_folder_doc_ids(folder_id: str) -> List[str]:
    """폴더에 속한 문서 ID 목록"""
    r = _get_redis()
    return list(r.smembers(_folder_docs_key(folder_id)))


def _move_doc_to_folder(doc_id: str, new_folder_id: str):
    """
    문서를 폴더로 이동 (원자적).
    - 기존 폴더에서 자동 제거
    - 새 폴더에 추가
    - doc_folder 역인덱스 갱신
    """
    r = _get_redis()
    old_folder_id = r.get(_doc_folder_key(doc_id))
    if old_folder_id and old_folder_id != new_folder_id:
        r.srem(_folder_docs_key(old_folder_id), doc_id)
    r.sadd(_folder_docs_key(new_folder_id), doc_id)
    r.set(_doc_folder_key(doc_id), new_folder_id)


def _remove_doc_from_folder(doc_id: str, folder_id: str):
    """폴더에서 문서 제거"""
    r = _get_redis()
    r.srem(_folder_docs_key(folder_id), doc_id)
    current = r.get(_doc_folder_key(doc_id))
    if current == folder_id:
        r.delete(_doc_folder_key(doc_id))


def _get_doc_folder_id(doc_id: str) -> Optional[str]:
    """문서가 속한 폴더 ID 반환 (없으면 None)"""
    return _get_redis().get(_doc_folder_key(doc_id))


# ============================================================
# Request/Response Models
# ============================================================

class FolderCreateRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None


class FolderUpdateRequest(BaseModel):
    name: Optional[str] = None


class FolderMoveRequest(BaseModel):
    parent_id: Optional[str] = None


class AssignDocumentRequest(BaseModel):
    doc_id: str
    collection: str = "documents"


# ============================================================
# 트리 빌더
# ============================================================

def _build_folder_tree(folder_id: str) -> dict:
    """폴더 트리를 재귀적으로 구성"""
    folder = _get_folder(folder_id)
    if not folder:
        return {}

    doc_ids = _get_folder_doc_ids(folder_id)

    # 하위 폴더 찾기
    children = []
    for fid in _get_all_folder_ids():
        f = _get_folder(fid)
        if f and f.get("parent_id") == folder_id:
            children.append(_build_folder_tree(fid))

    return {
        **folder,
        "document_count": len(doc_ids),
        "documents": doc_ids,
        "children_data": children,
        "color": folder.get("color", "#6366f1"),
        "icon": folder.get("icon", "folder"),
        "is_system": folder.get("is_system", "false") == "true",
    }


# ============================================================
# API Endpoints
# ============================================================

@router.get("")
async def get_folders():
    """
    루트 폴더 목록 + 전체 트리 반환
    """
    try:
        root_folders = []
        for folder_id in _get_all_folder_ids():
            folder = _get_folder(folder_id)
            if folder and folder.get("parent_id") is None:
                root_folders.append(_build_folder_tree(folder_id))

        return {"success": True, "folders": root_folders}

    except Exception as e:
        logger.error(f"폴더 목록 조회 실패: {e}")
        return {"success": False, "error": str(e), "folders": []}


@router.get("/all")
async def get_all_folders():
    """모든 폴더 목록 (평면 리스트)"""
    try:
        all_folders = []
        for folder_id in _get_all_folder_ids():
            folder = _get_folder(folder_id)
            if folder:
                folder["document_count"] = len(_get_folder_doc_ids(folder_id))
                all_folders.append(folder)

        return {"success": True, "folders": all_folders}

    except Exception as e:
        logger.error(f"전체 폴더 목록 조회 실패: {e}")
        return {"success": False, "error": str(e), "folders": []}


@router.post("")
async def create_folder(request: FolderCreateRequest):
    """새 폴더 생성"""
    try:
        if request.parent_id and not _folder_exists(request.parent_id):
            return {"success": False, "error": "부모 폴더를 찾을 수 없습니다."}

        folder_id = str(uuid.uuid4())[:8]
        folder = {
            "id": folder_id,
            "name": request.name,
            "parent_id": request.parent_id,
            "created_at": datetime.now().isoformat(),
        }
        _save_folder(folder)

        # parent_id None 복원 후 반환
        folder["parent_id"] = request.parent_id
        return {
            "success": True,
            "message": f"폴더 '{request.name}'이(가) 생성되었습니다.",
            "folder": folder,
        }

    except Exception as e:
        logger.error(f"폴더 생성 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/document/{doc_id}")
async def get_document_folder(doc_id: str):
    """문서가 속한 폴더 조회"""
    try:
        folder_id = _get_doc_folder_id(doc_id)
        if folder_id:
            folder = _get_folder(folder_id)
            return {"success": True, "folder": folder}

        return {
            "success": True,
            "folder": None,
            "message": "문서가 어떤 폴더에도 속하지 않습니다.",
        }

    except Exception as e:
        logger.error(f"문서 폴더 조회 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{folder_id}")
async def get_folder(folder_id: str):
    """특정 폴더 정보"""
    try:
        folder = _get_folder(folder_id)
        if not folder:
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        folder["document_count"] = len(_get_folder_doc_ids(folder_id))

        # 하위 폴더 목록
        children = []
        for fid in _get_all_folder_ids():
            f = _get_folder(fid)
            if f and f.get("parent_id") == folder_id:
                f["document_count"] = len(_get_folder_doc_ids(fid))
                children.append(f)
        folder["children"] = children

        return {"success": True, "folder": folder}

    except Exception as e:
        logger.error(f"폴더 조회 실패: {e}")
        return {"success": False, "error": str(e)}


@router.put("/{folder_id}")
async def update_folder(folder_id: str, request: FolderUpdateRequest):
    """폴더 이름 수정"""
    try:
        folder = _get_folder(folder_id)
        if not folder:
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        if request.name:
            folder["name"] = request.name
            _save_folder(folder)

        return {"success": True, "message": "폴더가 수정되었습니다.", "folder": folder}

    except Exception as e:
        logger.error(f"폴더 수정 실패: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{folder_id}")
async def delete_folder(folder_id: str, recursive: bool = False):
    """폴더 삭제"""
    try:
        if not _folder_exists(folder_id):
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        has_children = any(
            _get_folder(fid) and _get_folder(fid).get("parent_id") == folder_id
            for fid in _get_all_folder_ids()
        )
        has_documents = len(_get_folder_doc_ids(folder_id)) > 0

        if (has_children or has_documents) and not recursive:
            return {
                "success": False,
                "error": "폴더에 하위 항목이 있습니다. recursive=true로 삭제하세요.",
            }

        def delete_recursive(fid: str):
            for child_id in list(_get_all_folder_ids()):
                f = _get_folder(child_id)
                if f and f.get("parent_id") == fid:
                    delete_recursive(child_id)
            _delete_folder(fid)

        if recursive:
            delete_recursive(folder_id)
        else:
            _delete_folder(folder_id)

        return {"success": True, "message": "폴더가 삭제되었습니다."}

    except Exception as e:
        logger.error(f"폴더 삭제 실패: {e}")
        return {"success": False, "error": str(e)}


@router.post("/{folder_id}/move")
async def move_folder(folder_id: str, request: FolderMoveRequest):
    """폴더를 다른 위치로 이동"""
    try:
        folder = _get_folder(folder_id)
        if not folder:
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        if request.parent_id and not _folder_exists(request.parent_id):
            return {"success": False, "error": "대상 부모 폴더를 찾을 수 없습니다."}

        # 순환 참조 방지: folder_id가 request.parent_id의 조상이면 안 됨
        if request.parent_id:
            check_id = request.parent_id
            while check_id:
                if check_id == folder_id:
                    return {"success": False, "error": "순환 폴더 구조가 됩니다."}
                parent = _get_folder(check_id)
                check_id = parent.get("parent_id") if parent else None

        folder["parent_id"] = request.parent_id
        _save_folder(folder)

        return {"success": True, "message": "폴더가 이동되었습니다.", "folder": folder}

    except Exception as e:
        logger.error(f"폴더 이동 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{folder_id}/documents")
async def get_folder_documents(folder_id: str):
    """폴더 내 문서 목록"""
    try:
        if not _folder_exists(folder_id):
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        doc_ids = _get_folder_doc_ids(folder_id)
        documents = [{"doc_id": d, "collection": "documents"} for d in doc_ids]

        return {
            "success": True,
            "folder": _get_folder(folder_id),
            "documents": documents,
        }

    except Exception as e:
        logger.error(f"폴더 문서 목록 조회 실패: {e}")
        return {"success": False, "error": str(e)}


@router.post("/{folder_id}/documents")
async def assign_document_to_folder(folder_id: str, request: AssignDocumentRequest):
    """
    문서를 폴더에 할당 (이동).
    - 기존 폴더에서 자동으로 제거 (exclusive membership 보장)
    - 이미 같은 폴더에 있으면 성공 반환
    """
    try:
        if not _folder_exists(folder_id):
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        _move_doc_to_folder(request.doc_id, folder_id)

        return {"success": True, "message": "문서가 폴더로 이동되었습니다."}

    except Exception as e:
        logger.error(f"문서 폴더 할당 실패: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{folder_id}/documents/{doc_id}")
async def remove_document_from_folder(folder_id: str, doc_id: str):
    """폴더에서 문서 제거 (루트로 이동)"""
    try:
        if not _folder_exists(folder_id):
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        _remove_doc_from_folder(doc_id, folder_id)

        return {"success": True, "message": "문서가 폴더에서 제거되었습니다."}

    except Exception as e:
        logger.error(f"문서 폴더 제거 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{folder_id}/path")
async def get_folder_path(folder_id: str):
    """폴더 경로 (브레드크럼)"""
    try:
        if not _folder_exists(folder_id):
            return {"success": False, "error": "폴더를 찾을 수 없습니다."}

        path = []
        current_id = folder_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            folder = _get_folder(current_id)
            if folder:
                path.insert(0, {"id": current_id, "name": folder["name"]})
                current_id = folder.get("parent_id")
            else:
                break

        return {"success": True, "path": path}

    except Exception as e:
        logger.error(f"폴더 경로 조회 실패: {e}")
        return {"success": False, "error": str(e)}
