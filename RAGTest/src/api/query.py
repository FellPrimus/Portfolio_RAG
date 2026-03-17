"""
질의응답 API 라우터

RAG 기반 질의응답 및 피드백 처리를 담당합니다.
"""
from flask import Blueprint, request, jsonify, Response, stream_with_context
from src.services import DocumentService
import os
import logging

logger = logging.getLogger(__name__)

# Blueprint 생성
query_bp = Blueprint('query', __name__, url_prefix='/api/query')

# DocumentService 인스턴스 (app.py에서 주입받을 예정)
doc_service = None


def init_document_service(service: DocumentService):
    """DocumentService 인스턴스 주입"""
    global doc_service
    doc_service = service


@query_bp.route('', methods=['POST'])
def query():
    """
    Quality RAG 질의응답 (LangGraph 기반)

    Request JSON:
        {
            'question': str
        }

    Returns:
        {
            'success': bool,
            'answer': str,
            'sources': [...],
            'quality_score': float,
            'confidence': str,
            'retry_count': int,
            'steps': [...],
            'warnings': [...],
            'session_id': str,
            'processing_time': float
        }
    """
    try:
        data = request.json
        question = data.get('question', '').strip()

        if not question:
            return jsonify({
                'success': False,
                'error': '질문을 입력해주세요.'
            }), 400

        # 문서 서비스를 통해 질의
        result = doc_service.query(question)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@query_bp.route('/stream', methods=['POST'])
def query_stream():
    """
    스트리밍 방식의 Quality RAG 질의응답

    Request JSON:
        {
            'question': str,
            'secure_mode': bool (optional),
            'web_search': bool (optional) - 웹 검색 교차 검증 활성화
        }

    Returns:
        Server-Sent Events (SSE) stream:
            event: answer
            data: {"chunk": "텍스트"}

            event: sources
            data: {"sources": [...]}

            event: web_verification
            data: {"status": "confirmed|enhanced|conflicting|no_data", ...}

            event: done
            data: {"success": true, ...}
    """
    if doc_service.rag is None:
        return jsonify({
            'success': False,
            'error': '먼저 문서를 로드해주세요.'
        }), 400

    data = request.json
    question = data.get('question', '').strip()
    secure_mode = data.get('secure_mode', False)
    web_search_enabled = data.get('web_search', False)

    if not question:
        return jsonify({
            'success': False,
            'error': '질문을 입력해주세요.'
        }), 400

    def generate():
        """SSE 스트림 생성"""
        try:
            # RAG 스트리밍 쿼리 실행 (웹 검색 파라미터 추가)
            for event in doc_service.rag.query_stream(
                question,
                secure_mode=secure_mode,
                web_search_enabled=web_search_enabled
            ):
                event_type = event.get('type')

                if event_type == 'status':
                    yield f"event: status\ndata: {event['data']}\n\n"
                elif event_type == 'answer_chunk':
                    yield f"event: answer\ndata: {event['data']}\n\n"
                elif event_type == 'sources':
                    yield f"event: sources\ndata: {event['data']}\n\n"
                elif event_type == 'web_verification':
                    yield f"event: web_verification\ndata: {event['data']}\n\n"
                elif event_type == 'done':
                    yield f"event: done\ndata: {event['data']}\n\n"
                elif event_type == 'error':
                    yield f"event: error\ndata: {event['data']}\n\n"

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            yield f"event: error\ndata: {{\"error\": \"{str(e)}\"}}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@query_bp.route('/feedback', methods=['POST'])
def add_feedback():
    """
    질의응답에 대한 피드백 추가

    Request JSON:
        {
            'session_id': str,
            'feedback_type': str,  # 'positive', 'negative'
            'comment': str  # optional
        }

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    if doc_service.rag is None:
        return jsonify({
            'success': False,
            'error': 'RAG가 초기화되지 않았습니다.'
        }), 400

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        feedback_type = data.get('feedback_type')
        comment = data.get('comment', '')

        if not session_id or not feedback_type:
            return jsonify({
                'success': False,
                'error': 'session_id와 feedback_type이 필요합니다.'
            }), 400

        # RAG에 피드백 추가
        doc_service.rag.add_feedback(session_id, feedback_type, comment)

        return jsonify({
            'success': True,
            'message': '피드백이 저장되었습니다.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@query_bp.route('/feedback/stats', methods=['GET'])
def get_feedback_stats():
    """
    피드백 통계 조회

    Returns:
        {
            'success': bool,
            'stats': {
                'total': int,
                'positive': int,
                'negative': int,
                'positive_rate': float
            }
        }
    """
    if doc_service.rag is None:
        return jsonify({
            'success': False,
            'error': 'RAG가 초기화되지 않았습니다.'
        }), 400

    try:
        stats = doc_service.rag.get_feedback_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
