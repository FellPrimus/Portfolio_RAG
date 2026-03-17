"""
RAGTest 호환 Query API

RAGTest의 /api/query 엔드포인트들을 동일한 형식으로 제공합니다.
"""
import json
import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...services.document_service import correct_korean_spacing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["compat-query"])


# ============================================================
# RAG System Prompt
# ============================================================

RAG_SYSTEM_PROMPT = """당신은 제공된 문서를 기반으로 질문에 답변하는 RAG 어시스턴트입니다.

## 원칙
- 반드시 [참고 문서]의 내용을 바탕으로 답변하세요.
- 문서에 관련 정보가 있으면 그 내용을 활용해 답변하세요.
- 문서에 없는 외부 지식이나 추측은 사용하지 마세요.

## 답변 형식
- 자연스럽고 읽기 쉬운 한국어로 작성하세요.
- 필요시 불릿 포인트나 번호 목록을 사용하세요.
- 핵심 정보는 **굵게** 강조할 수 있습니다."""


# ============================================================
# Request/Response Models
# ============================================================

class QueryRequest(BaseModel):
    question: str
    secure_mode: bool = False
    web_search: bool = False


class FeedbackRequest(BaseModel):
    session_id: str
    feedback_type: str  # 'positive' or 'negative'
    comment: str = ""


# ============================================================
# 서비스 접근 헬퍼
# ============================================================

def get_services():
    """메인 앱에서 초기화된 서비스들 가져오기"""
    from ...main import rag_service, embedding_client, llm_client, qdrant_service
    return rag_service, embedding_client, llm_client, qdrant_service


def get_active_documents():
    """활성화된 문서 가져오기"""
    from .documents import get_session_state
    return get_session_state().get("active_documents", [])


def get_active_collections():
    """활성화된 컬렉션 가져오기"""
    from .documents import get_session_state
    return get_session_state().get("active_collections", set())


# ============================================================
# API Endpoints
# ============================================================

@router.post("")
async def query(request: QueryRequest):
    """
    RAG 질의응답 (비스트리밍)

    RAGTest 응답 형식:
    {
        'success': bool,
        'answer': str,
        'sources': [...],
        'quality_score': float,
        'confidence': str,
        'processing_time': float
    }
    """
    try:
        rag_service, _, _, _ = get_services()

        if not request.question.strip():
            return {"success": False, "error": "질문을 입력해주세요."}

        # 활성화된 문서 확인
        active_docs = get_active_documents()
        if not active_docs:
            return {"success": False, "error": "먼저 문서를 활성화해주세요."}

        # RAG 쿼리 실행
        import time
        start_time = time.time()

        result = await rag_service.query(
            question=request.question,
            collection=list(get_active_collections())[0] if get_active_collections() else "documents"
        )

        processing_time = time.time() - start_time

        return {
            "success": True,
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "quality_score": result.get("quality_score", 0.8),
            "confidence": result.get("confidence", "high"),
            "processing_time": processing_time
        }

    except Exception as e:
        logger.error(f"질의 처리 실패: {e}")
        return {"success": False, "error": str(e)}


@router.post("/stream")
async def query_stream(request: Request):
    """
    스트리밍 방식의 RAG 질의응답

    Server-Sent Events (SSE) 형식으로 응답:
    - event: status (상태 메시지)
    - event: answer (답변 청크)
    - event: sources (출처 정보)
    - event: done (완료)
    - event: error (오류)
    """
    try:
        body = await request.json()
        question = body.get("question", "").strip()
        secure_mode = body.get("secure_mode", False)
        web_search = body.get("web_search", False)

        if not question:
            async def error_stream():
                yield f'event: error\ndata: {{"error": "질문을 입력해주세요."}}\n\n'
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        # 활성화된 문서 확인
        active_docs = get_active_documents()
        if not active_docs:
            async def error_stream():
                yield f'event: error\ndata: {{"error": "먼저 문서를 활성화해주세요."}}\n\n'
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        rag_service, embedding_client, llm_client, qdrant_service = get_services()

        async def generate():
            import time
            start_time = time.time()

            try:
                # 0. 모델 정보 조회
                model_info = await llm_client.get_model_info()
                model_name = model_info.get("model", "LLM")

                # 1. 상태: 검색 시작
                yield f'event: status\ndata: {json.dumps({"message": "문서 검색 중..."}, ensure_ascii=False)}\n\n'

                # 2. 임베딩 생성
                query_embedding = await embedding_client.embed_query(question)

                # 3. 벡터 검색 (활성화된 문서만 검색)
                active_collections = get_active_collections()
                active_docs = get_active_documents()
                collection = list(active_collections)[0] if active_collections else "documents"

                # 활성화된 문서 파일명 목록
                active_filenames = [doc.get("filename") for doc in active_docs if doc.get("filename")]

                # 디버그 로깅
                logger.info(f"[DEBUG] Active collections: {active_collections}")
                logger.info(f"[DEBUG] Active documents: {active_docs}")
                logger.info(f"[DEBUG] Active filenames for filtering: {active_filenames}")
                logger.info(f"[DEBUG] Using collection: {collection}")

                # 검색 수행 (더 많은 결과를 가져온 후 필터링)
                raw_results = qdrant_service.search(
                    query_vector=query_embedding,
                    collection_name=collection,
                    top_k=20  # 더 많이 가져와서 필터링
                )

                logger.info(f"[DEBUG] Raw search results count: {len(raw_results)}")
                for i, r in enumerate(raw_results[:5]):
                    payload = r.get("payload", {})
                    fn = payload.get("filename", payload.get("source", "N/A"))
                    logger.info(f"[DEBUG] Result {i}: filename={fn}, score={r.get('score', 0):.4f}")

                # 활성화된 문서만 필터링
                search_results = []
                for result in raw_results:
                    payload = result.get("payload", {})
                    filename = payload.get("filename", payload.get("source", ""))
                    # 활성 파일명 목록이 있으면 필터링, 없으면 모두 포함
                    if not active_filenames or filename in active_filenames:
                        search_results.append(result)
                        if len(search_results) >= 5:
                            break
                    else:
                        logger.info(f"[DEBUG] Filtered out: {filename} (not in active list)")

                logger.info(f"[DEBUG] Filtered results count: {len(search_results)}")

                # 4. 컨텍스트 구성
                context_parts = []
                sources = []
                total_score = 0

                for i, result in enumerate(search_results):
                    payload = result.get("payload", {})
                    text = payload.get("text", payload.get("content", ""))
                    score = result.get("score", 0)
                    total_score += score
                    context_parts.append(f"[문서 {i+1}]\n{text}")

                    sources.append({
                        "filename": payload.get("filename", payload.get("source", "unknown")),
                        "chunk_index": payload.get("chunk_index", i),
                        "score": score,
                        "content_preview": text[:200] + "..." if len(text) > 200 else text
                    })

                context = "\n\n".join(context_parts)

                # 평균 점수 계산
                avg_score = total_score / len(search_results) if search_results else 0

                # 5. 출처 정보 전송
                yield f'event: sources\ndata: {json.dumps({"sources": sources}, ensure_ascii=False)}\n\n'

                # 5.5 유사도 점수 임계값 체크 - 낮으면 LLM 호출 없이 바로 응답
                MIN_RELEVANCE_SCORE = 0.78
                if avg_score < MIN_RELEVANCE_SCORE:
                    logger.info(f"[DEBUG] Low relevance score ({avg_score:.4f} < {MIN_RELEVANCE_SCORE}), skipping LLM call")
                    no_info_msg = "제공된 문서에서 해당 정보를 찾을 수 없습니다."
                    yield f'event: answer\ndata: {json.dumps({"content": no_info_msg}, ensure_ascii=False)}\n\n'

                    processing_time = time.time() - start_time
                    done_data = {
                        "success": True,
                        "total_length": len(no_info_msg),
                        "processing_time": processing_time,
                        "quality_score": avg_score,
                        "confidence": "low",
                        "used_model": model_name,
                        "sources_count": len(sources),
                        "original_question": question,
                        "search_queries": [question],
                        "hybrid_search_used": False,
                        "hallucination_detected": False,
                        "low_relevance": True
                    }
                    yield f'event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n'
                    return

                # 6. 상태: LLM 생성 시작
                yield f'event: status\ndata: {json.dumps({"message": "답변 생성 중..."}, ensure_ascii=False)}\n\n'

                # 7. LLM 스트리밍 응답 생성 (시스템 프롬프트 + 사용자 메시지)
                user_message = f"""[참고 문서]
{context}

[질문]
{question}"""

                messages = [
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ]

                # LLM 스트리밍 호출 (버퍼링 + 실시간 띄어쓰기 보정)
                full_answer = ""
                buffer = ""
                # 청크 분리 기준: 구두점, 불릿, 괄호 닫힘 등
                delimiters = {'.', '!', '?', ':', '-', ')', '>', '\n', '—', '·'}
                min_buffer_size = 20  # 최소 버퍼 크기 (너무 짧으면 보정 품질 저하)
                max_buffer_size = 100  # 최대 버퍼 크기 (너무 길면 지연 발생)

                async for chunk in llm_client.stream(messages):
                    if chunk:
                        buffer += chunk
                        full_answer += chunk

                        # 버퍼가 충분히 크고, 구두점이 있으면 보정 후 전송
                        should_flush = False
                        if len(buffer) >= min_buffer_size:
                            # 구두점 위치 찾기
                            for i, char in enumerate(buffer):
                                if char in delimiters and i >= min_buffer_size - 1:
                                    should_flush = True
                                    break

                        # 버퍼가 너무 크면 강제 전송
                        if len(buffer) >= max_buffer_size:
                            should_flush = True

                        if should_flush:
                            # 띄어쓰기 보정 적용
                            corrected_chunk = correct_korean_spacing(buffer)
                            yield f'event: answer\ndata: {json.dumps({"content": corrected_chunk}, ensure_ascii=False)}\n\n'
                            buffer = ""
                            await asyncio.sleep(0.01)

                # 남은 버퍼 처리
                if buffer:
                    corrected_chunk = correct_korean_spacing(buffer)
                    yield f'event: answer\ndata: {json.dumps({"content": corrected_chunk}, ensure_ascii=False)}\n\n'

                # 8. 완료 - 품질 메타데이터 포함
                processing_time = time.time() - start_time

                # 신뢰도 계산 (평균 유사도 점수 기반)
                if avg_score >= 0.8:
                    confidence = "high"
                elif avg_score >= 0.5:
                    confidence = "medium"
                else:
                    confidence = "low"

                # 품질 점수 (유사도 기반)
                quality_score = min(avg_score * 1.2, 1.0)  # 0~1 범위

                done_data = {
                    "success": True,
                    "total_length": len(full_answer),
                    "processing_time": processing_time,
                    "quality_score": quality_score,
                    "confidence": confidence,
                    "used_model": model_name,
                    "sources_count": len(sources),
                    "original_question": question,
                    "search_queries": [question],
                    "hybrid_search_used": False,
                    "hallucination_detected": False
                }

                yield f'event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n'

            except Exception as e:
                logger.error(f"스트리밍 쿼리 실패: {e}")
                yield f'event: error\ndata: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"스트리밍 쿼리 요청 처리 실패: {e}")
        async def error_stream():
            yield f'event: error\ndata: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'
        return StreamingResponse(error_stream(), media_type="text/event-stream")


@router.post("/feedback")
async def add_feedback(request: FeedbackRequest):
    """질의응답 피드백 저장"""
    try:
        # Redis에 피드백 저장 (간단 구현)
        from ...main import redis_service

        feedback_key = f"feedback:{request.session_id}"
        feedback_data = {
            "type": request.feedback_type,
            "comment": request.comment
        }

        if redis_service:
            redis_service.set(feedback_key, json.dumps(feedback_data), ex=86400 * 30)  # 30일 보관

        return {
            "success": True,
            "message": "피드백이 저장되었습니다."
        }

    except Exception as e:
        logger.error(f"피드백 저장 실패: {e}")
        return {"success": False, "error": str(e)}


@router.get("/feedback/stats")
async def get_feedback_stats():
    """피드백 통계"""
    try:
        # 간단 구현 - 실제로는 Redis에서 집계
        return {
            "success": True,
            "stats": {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "positive_rate": 0.0
            }
        }

    except Exception as e:
        logger.error(f"피드백 통계 조회 실패: {e}")
        return {"success": False, "error": str(e)}
