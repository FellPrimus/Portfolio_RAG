"""
RAGTest 호환 Documents API

RAGTest의 /api/documents 엔드포인트들을 동일한 형식으로 제공합니다.
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["compat-documents"])


# ============================================================
# Request/Response Models (RAGTest 형식)
# ============================================================

class TextDocumentRequest(BaseModel):
    title: str
    content: str
    category_id: str = "general"


class CategoryUpdateRequest(BaseModel):
    filename: str
    collection: str
    category_id: str


class LoadDocumentsRequest(BaseModel):
    files: List[str]
    chunk_size: int = 1000
    chunk_overlap: int = 200


class LoadCollectionsRequest(BaseModel):
    collections: List[str]
    filenames: Optional[List[str]] = None


# ============================================================
# 서비스 접근 헬퍼
# ============================================================

def get_services():
    """메인 앱에서 초기화된 서비스들 가져오기"""
    from ...main import qdrant_service, redis_service, document_service, embedding_client
    return qdrant_service, redis_service, document_service, embedding_client


# ============================================================
# 세션 상태 관리 (활성화된 문서)
# ============================================================

# 전역 세션 상태 (간단한 구현 - 실제로는 Redis 등 사용 권장)
_session_state = {
    "active_documents": [],  # 활성화된 문서 목록
    "active_collections": set(),  # 활성화된 컬렉션
}


def get_session_state():
    return _session_state


# ============================================================
# API Endpoints
# ============================================================

@router.get("")
async def get_documents():
    """
    벡터DB에 저장된 문서 목록 반환

    RAGTest 응답 형식:
    {
        'success': bool,
        'documents': [
            {
                'filename': str,
                'chunk_count': int,
                'added_at': str,
                'collection': str,
                'category': {...}
            }
        ]
    }
    """
    try:
        qdrant_service, redis_service, _, _ = get_services()

        documents = []

        # Qdrant에서 모든 포인트 가져오기
        try:
            # 컬렉션 존재 확인
            collections = qdrant_service.list_collections()

            for collection_name in collections:
                # 각 컬렉션에서 문서 메타데이터 가져오기
                points = qdrant_service.client.scroll(
                    collection_name=collection_name,
                    limit=1000,
                    with_payload=True,
                    with_vectors=False
                )[0]

                # 파일별로 그룹화
                file_chunks = {}
                for point in points:
                    payload = point.payload or {}
                    filename = payload.get("filename", payload.get("source", "unknown"))

                    if filename not in file_chunks:
                        file_chunks[filename] = {
                            "filename": filename,
                            "chunk_count": 0,
                            "added_at": payload.get("added_at", payload.get("created_at", "")),
                            "collection": collection_name,
                            "category": {
                                "id": payload.get("category_id", "general"),
                                "name": payload.get("category_name", "일반"),
                                "icon": payload.get("category_icon", "📄")
                            }
                        }
                    file_chunks[filename]["chunk_count"] += 1

                documents.extend(file_chunks.values())

        except Exception as e:
            logger.warning(f"문서 목록 조회 중 오류: {e}")

        return {
            "success": True,
            "documents": documents
        }

    except Exception as e:
        logger.error(f"문서 목록 조회 실패: {e}")
        return {
            "success": False,
            "error": str(e),
            "documents": []
        }


@router.delete("")
async def delete_all_documents():
    """모든 문서 삭제"""
    try:
        qdrant_service, _, _, _ = get_services()

        # 모든 컬렉션 삭제 후 재생성
        collections = qdrant_service.list_collections()
        for collection_name in collections:
            qdrant_service.client.delete_collection(collection_name)

        # 기본 컬렉션 재생성
        qdrant_service.ensure_collection()

        # 세션 상태 초기화
        _session_state["active_documents"] = []
        _session_state["active_collections"] = set()

        return {
            "success": True,
            "message": "모든 문서가 삭제되었습니다."
        }

    except Exception as e:
        logger.error(f"문서 전체 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/text")
async def load_text_document(request: TextDocumentRequest):
    """
    텍스트 직접 입력 및 벡터DB 저장
    """
    try:
        _, _, document_service, _ = get_services()

        if not request.title.strip():
            return {"success": False, "error": "문서 제목을 입력해주세요."}

        if len(request.content) < 50:
            return {"success": False, "error": "텍스트가 너무 짧습니다. (최소 50자)"}

        # 텍스트 문서 저장
        result = await document_service.upload_text(
            text=request.content,
            source=request.title,
            category=request.category_id
        )

        return {
            "success": True,
            "chunk_count": result.get("chunks_count", 0),
            "doc_id": result.get("document_id", request.title)
        }

    except Exception as e:
        logger.error(f"텍스트 문서 저장 실패: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/{filename:path}")
async def delete_document(
    filename: str,
    scope: str = Query("all"),  # all, vector_only, file_only
    collection: str = Query(None),
    is_crawled: bool = Query(False)
):
    """특정 문서 삭제"""
    try:
        qdrant_service, _, _, _ = get_services()

        # 해당 파일의 모든 청크 삭제
        collections = [collection] if collection else qdrant_service.list_collections()
        deleted_count = 0

        for coll_name in collections:
            # source 필드와 filename 필드 모두 시도
            for field_name in ["source", "filename"]:
                try:
                    count = qdrant_service.delete_by_filter(
                        filter_key=field_name,
                        filter_value=filename,
                        collection_name=coll_name
                    )
                    deleted_count += count
                except Exception as e:
                    logger.warning(f"컬렉션 {coll_name}의 {field_name} 필드 삭제 실패: {e}")

        # 파일 저장소에서도 삭제
        from .files import _uploaded_files
        if filename in _uploaded_files:
            del _uploaded_files[filename]

        logger.info(f"문서 '{filename}' 삭제 완료: {deleted_count}개 청크 삭제")
        return {"success": True, "message": f"'{filename}' 문서가 삭제되었습니다.", "deleted_chunks": deleted_count}

    except Exception as e:
        logger.error(f"문서 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """
    시스템 상태 확인

    RAGTest 응답 형식:
    {
        'ready': bool,
        'documents_loaded': int,
        'llm_provider': str,
        'stats': {...}
    }
    """
    try:
        qdrant_service, redis_service, _, _ = get_services()

        # 활성화된 문서 수
        active_docs = len(_session_state.get("active_documents", []))

        # 전체 문서 수
        total_docs = 0
        try:
            collections = qdrant_service.list_collections()
            for coll in collections:
                info = qdrant_service.client.get_collection(coll)
                total_docs += info.points_count
        except:
            pass

        return {
            "ready": active_docs > 0,
            "documents_loaded": active_docs,
            "llm_provider": "CLOVA",
            "stats": {
                "total_documents": total_docs,
                "active_documents": active_docs,
                "collections": len(qdrant_service.list_collections()) if qdrant_service else 0
            }
        }

    except Exception as e:
        logger.error(f"상태 확인 실패: {e}")
        return {
            "ready": False,
            "documents_loaded": 0,
            "llm_provider": "CLOVA",
            "error": str(e)
        }


@router.get("/loaded")
async def get_loaded_documents():
    """
    현재 세션에 로드(활성화)된 문서 목록
    """
    return {
        "success": True,
        "documents": _session_state.get("active_documents", [])
    }


@router.post("/load-multiple-collections")
async def load_multiple_collections(request: LoadCollectionsRequest):
    """
    여러 컬렉션/문서를 동시에 활성화
    """
    try:
        qdrant_service, _, _, _ = get_services()

        loaded = 0
        failed = 0
        failed_collections = []

        for collection_name in request.collections:
            try:
                # 컬렉션 존재 확인
                collections = qdrant_service.list_collections()
                if collection_name in collections:
                    _session_state["active_collections"].add(collection_name)
                    loaded += 1
                else:
                    failed += 1
                    failed_collections.append(collection_name)
            except Exception as e:
                logger.warning(f"컬렉션 {collection_name} 로드 실패: {e}")
                failed += 1
                failed_collections.append(collection_name)

        # 활성화된 문서 목록 갱신
        from .categories import get_category

        if request.filenames:
            _session_state["active_documents"] = [
                {"filename": f, "collection": c, "category": get_category("general")}
                for c in _session_state["active_collections"]
                for f in request.filenames
            ]
        else:
            # 컬렉션의 모든 문서 활성화
            docs = []
            for coll in _session_state["active_collections"]:
                try:
                    points = qdrant_service.client.scroll(
                        collection_name=coll,
                        limit=1000,
                        with_payload=True,
                        with_vectors=False
                    )[0]

                    # 파일별로 그룹화하고 카테고리 정보 수집
                    file_info = {}
                    for p in points:
                        fn = p.payload.get("filename", p.payload.get("source"))
                        if fn and fn not in file_info:
                            cat_id = p.payload.get("category", p.payload.get("category_id", "general"))
                            file_info[fn] = {
                                "filename": fn,
                                "collection": coll,
                                "category": get_category(cat_id)
                            }

                    docs.extend(file_info.values())
                except Exception as e:
                    logger.warning(f"컬렉션 {coll} 문서 로드 실패: {e}")

            _session_state["active_documents"] = docs

        return {
            "success": True,
            "loaded": loaded,
            "failed": failed,
            "failed_collections": failed_collections,
            "active_collections": list(_session_state["active_collections"]),
            "message": f"{loaded}개 컬렉션 로드 완료"
        }

    except Exception as e:
        logger.error(f"다중 컬렉션 로드 실패: {e}")
        return {"success": False, "error": str(e)}


@router.post("/load-collection/{collection_name}")
async def load_collection(collection_name: str):
    """단일 컬렉션 활성화"""
    try:
        qdrant_service, _, _, _ = get_services()

        collections = qdrant_service.list_collections()
        if collection_name not in collections:
            return {"success": False, "message": f"컬렉션 '{collection_name}'을 찾을 수 없습니다."}

        _session_state["active_collections"].add(collection_name)

        return {
            "success": True,
            "message": f"컬렉션 '{collection_name}' 로드 완료",
            "stats": {"collection": collection_name}
        }

    except Exception as e:
        logger.error(f"컬렉션 로드 실패: {e}")
        return {"success": False, "error": str(e)}


@router.put("/category")
async def update_document_category(request: CategoryUpdateRequest):
    """문서 카테고리 변경"""
    try:
        qdrant_service, _, _, _ = get_services()

        # 해당 문서의 모든 청크 메타데이터 업데이트
        qdrant_service.client.set_payload(
            collection_name=request.collection,
            payload={"category_id": request.category_id},
            points={
                "filter": {
                    "must": [
                        {"key": "filename", "match": {"value": request.filename}}
                    ]
                }
            }
        )

        return {
            "success": True,
            "message": f"'{request.filename}' 카테고리가 변경되었습니다."
        }

    except Exception as e:
        logger.error(f"카테고리 변경 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{filename:path}/chunks/preview")
async def get_chunk_preview(
    filename: str,
    collection: str = Query(...),
    limit: int = Query(3)
):
    """문서 청크 미리보기"""
    try:
        qdrant_service, _, _, _ = get_services()

        # 해당 문서의 청크 조회 (source 또는 filename 키 사용)
        points = qdrant_service.client.scroll(
            collection_name=collection,
            scroll_filter={
                "should": [
                    {"key": "source", "match": {"value": filename}},
                    {"key": "filename", "match": {"value": filename}}
                ]
            },
            limit=limit,
            with_payload=True,
            with_vectors=False
        )[0]

        # 전체 청크 수 조회
        total_count = qdrant_service.client.count(
            collection_name=collection,
            count_filter={
                "should": [
                    {"key": "source", "match": {"value": filename}},
                    {"key": "filename", "match": {"value": filename}}
                ]
            }
        ).count

        preview_chunks = []
        for i, point in enumerate(points):
            # chunk_index는 payload에서 가져오거나 순서대로 부여
            chunk_idx = point.payload.get("chunk_index", i)
            preview_chunks.append({
                "chunk_index": chunk_idx,
                "content": point.payload.get("text", point.payload.get("content", ""))[:500],
                "length": len(point.payload.get("text", point.payload.get("content", ""))),
                "metadata": {k: v for k, v in point.payload.items() if k not in ["text", "content"]}
            })

        return {
            "success": True,
            "filename": filename,
            "total_chunks": total_count,
            "preview_chunks": preview_chunks
        }

    except Exception as e:
        logger.error(f"청크 미리보기 조회 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{filename:path}/chunks")
async def get_all_chunks(
    filename: str,
    collection: str = Query(...),
    page: int = Query(1),
    per_page: int = Query(10)
):
    """문서 전체 청크 조회 (페이지네이션)"""
    try:
        qdrant_service, _, _, _ = get_services()

        # 전체 청크 조회 (source 또는 filename 키 사용)
        all_points = qdrant_service.client.scroll(
            collection_name=collection,
            scroll_filter={
                "should": [
                    {"key": "source", "match": {"value": filename}},
                    {"key": "filename", "match": {"value": filename}}
                ]
            },
            limit=10000,
            with_payload=True,
            with_vectors=False
        )[0]

        # chunk_index로 정렬
        all_points = sorted(all_points, key=lambda p: p.payload.get("chunk_index", 0))

        total_chunks = len(all_points)
        total_pages = (total_chunks + per_page - 1) // per_page

        # 페이지네이션
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_points = all_points[start_idx:end_idx]

        chunks = []
        for point in page_points:
            chunk_idx = point.payload.get("chunk_index", 0)
            chunks.append({
                "chunk_index": chunk_idx,
                "content": point.payload.get("text", point.payload.get("content", "")),
                "length": len(point.payload.get("text", point.payload.get("content", ""))),
                "metadata": {k: v for k, v in point.payload.items() if k not in ["text", "content"]}
            })

        return {
            "success": True,
            "filename": filename,
            "total_chunks": total_chunks,
            "current_page": page,
            "total_pages": total_pages,
            "chunks": chunks
        }

    except Exception as e:
        logger.error(f"전체 청크 조회 실패: {e}")
        return {"success": False, "error": str(e)}
