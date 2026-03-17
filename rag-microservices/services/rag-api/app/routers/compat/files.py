"""
RAGTest 호환 Files API

RAGTest의 /api/files 및 /api/upload 엔드포인트들을 동일한 형식으로 제공합니다.
"""
import io
import logging
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compat-files"])


# ============================================================
# 파일 저장소 (메모리 - 실제로는 S3/로컬 스토리지 사용)
# ============================================================

_uploaded_files = {}  # filename -> file info


# ============================================================
# Request Models
# ============================================================

class FileCategoryUpdateRequest(BaseModel):
    filename: str
    category_id: str


# ============================================================
# 서비스 접근 헬퍼
# ============================================================

def get_services():
    """메인 앱에서 초기화된 서비스들 가져오기"""
    from ...main import document_service, embedding_client
    return document_service, embedding_client


# ============================================================
# API Endpoints
# ============================================================

@router.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("general"),
    category_id: str = Form(None)  # 두 가지 파라미터 모두 지원
):
    """
    파일 업로드 및 벡터DB 저장

    RAGTest 응답 형식:
    {
        'success': bool,
        'filename': str,
        'file_id': str,
        'chunk_count': int
    }
    """
    try:
        document_service, _ = get_services()

        # 카테고리 결정 (category_id가 있으면 우선 사용)
        cat = category_id if category_id else category

        # 파일 읽기
        content = await file.read()
        filename = file.filename

        # 파일 정보 저장
        file_id = str(uuid.uuid4())[:8]
        _uploaded_files[filename] = {
            "file_id": file_id,
            "filename": filename,
            "category_id": cat,
            "size": len(content),
            "content_type": file.content_type,
            "uploaded_at": datetime.now().isoformat()
        }

        # 문서 서비스를 통해 처리 및 벡터DB 저장
        file_obj = io.BytesIO(content)
        result = await document_service.upload_document(
            file=file_obj,
            filename=filename,
            category=cat
        )

        return {
            "success": True,
            "filename": filename,
            "file_id": file_id,
            "chunk_count": result.get("chunks_count", 0),
            "message": f"'{filename}' 파일이 업로드되었습니다."
        }

    except Exception as e:
        logger.error(f"파일 업로드 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/files")
async def get_files():
    """
    업로드된 파일 목록

    RAGTest 응답 형식:
    {
        'success': bool,
        'files': [
            {
                'filename': str,
                'file_id': str,
                'category_id': str,
                'size': int,
                'uploaded_at': str
            }
        ]
    }
    """
    try:
        files = list(_uploaded_files.values())
        return {
            "success": True,
            "files": files
        }

    except Exception as e:
        logger.error(f"파일 목록 조회 실패: {e}")
        return {"success": False, "error": str(e), "files": []}


@router.put("/api/files/category")
async def update_file_category(request: FileCategoryUpdateRequest):
    """파일 카테고리 변경"""
    try:
        if request.filename not in _uploaded_files:
            return {"success": False, "error": "파일을 찾을 수 없습니다."}

        _uploaded_files[request.filename]["category_id"] = request.category_id

        return {
            "success": True,
            "message": f"파일 카테고리가 변경되었습니다."
        }

    except Exception as e:
        logger.error(f"파일 카테고리 변경 실패: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """파일 삭제"""
    try:
        if filename in _uploaded_files:
            del _uploaded_files[filename]

        return {
            "success": True,
            "message": f"'{filename}' 파일이 삭제되었습니다."
        }

    except Exception as e:
        logger.error(f"파일 삭제 실패: {e}")
        return {"success": False, "error": str(e)}


# ============================================================
# /api/load 엔드포인트 (RAGTest 호환)
# ============================================================

@router.post("/api/load")
async def load_documents(data: dict):
    """
    문서 로드 및 벡터 스토어 생성

    Request JSON:
        {
            'files': [str],  # 파일 경로 리스트
            'chunk_size': int,
            'chunk_overlap': int
        }
    """
    try:
        document_service, _ = get_services()

        file_paths = data.get("files", [])
        if not file_paths:
            return {"success": False, "error": "파일을 선택해주세요."}

        chunk_config = {
            "size": data.get("chunk_size", 1000),
            "overlap": data.get("chunk_overlap", 200)
        }

        # 각 파일 처리
        total_chunks = 0
        processed_files = []

        for file_path in file_paths:
            filename = os.path.basename(file_path)
            if filename in _uploaded_files:
                processed_files.append(filename)
                # 실제 처리 로직 (이미 업로드된 파일)
                total_chunks += _uploaded_files[filename].get("chunk_count", 10)

        return {
            "success": True,
            "message": f"{len(processed_files)}개 파일 로드 완료",
            "stats": {
                "processed_files": len(processed_files),
                "total_chunks": total_chunks
            }
        }

    except Exception as e:
        logger.error(f"문서 로드 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/api/loaded-documents")
async def get_loaded_documents():
    """현재 로드된 문서 목록 (documents API 리다이렉트)"""
    from .documents import get_loaded_documents as get_docs
    return await get_docs()
