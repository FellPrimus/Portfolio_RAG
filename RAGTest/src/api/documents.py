"""
문서 관리 API 라우터

벡터DB에 저장된 문서의 조회, 삭제, 카테고리 변경 등을 처리합니다.
"""
from flask import Blueprint, request, jsonify
from src.services import DocumentService

# Blueprint 생성
documents_bp = Blueprint('documents', __name__, url_prefix='/api/documents')

# DocumentService 인스턴스 (app.py에서 주입받을 예정)
doc_service = None


def init_document_service(service: DocumentService):
    """DocumentService 인스턴스 주입"""
    global doc_service
    doc_service = service


@documents_bp.route('', methods=['GET'])
def get_documents():
    """
    청킹이 완료된 문서 목록 반환 (모든 컬렉션 스캔)

    Returns:
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
        result = doc_service.get_all_documents_from_vectordb()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('', methods=['DELETE'])
def delete_all_documents():
    """
    모든 문서 데이터 삭제 (모든 컬렉션 삭제)

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    try:
        result = doc_service.delete_all_documents()
        return jsonify(result)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"문서 삭제 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/category', methods=['PUT'])
def update_document_category():
    """
    벡터DB에 저장된 문서의 카테고리 변경

    Request JSON:
        {
            'filename': str,
            'collection': str,
            'category_id': str
        }

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        collection = data.get('collection')
        category_id = data.get('category_id')

        result = doc_service.update_document_category(filename, collection, category_id)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/text', methods=['POST'])
def load_text_document():
    """
    텍스트 직접 입력 및 벡터DB 저장 (의미 기준 청킹)

    Request JSON:
        {
            'title': str,           # 문서 제목
            'content': str,         # 텍스트 내용
            'category_id': str      # 카테고리 ID
        }

    Returns:
        {
            'success': bool,
            'chunk_count': int,
            'doc_id': str
        }
    """
    try:
        data = request.json
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        category_id = data.get('category_id', 'general')

        if not title:
            return jsonify({'success': False, 'error': '문서 제목을 입력해주세요.'}), 400

        if not content or len(content) < 50:
            return jsonify({'success': False, 'error': '텍스트가 너무 짧습니다. (최소 50자)'}), 400

        result = doc_service.load_text(
            title=title,
            content=content,
            category_id=category_id
        )

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@documents_bp.route('/<path:filename>', methods=['DELETE'])
def delete_document(filename: str):
    """
    벡터DB에서 특정 문서 삭제

    Args:
        filename: 삭제할 파일명

    Query Parameters:
        is_crawled: 크롤링된 문서 여부 (optional, default: false)

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    try:
        is_crawled = request.args.get('is_crawled', 'false').lower() == 'true'

        result = doc_service.delete_document(filename, is_crawled)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"문서 삭제 후처리 중 오류: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/load', methods=['POST'])
def load_documents():
    """
    문서 로드 및 벡터 스토어 생성 (벡터DB 재사용)

    Request JSON:
        {
            'files': [str],  # 파일 경로 리스트
            'chunk_size': int,  # optional
            'chunk_overlap': int  # optional
        }

    Returns:
        {
            'success': bool,
            'message': str,
            'stats': {...}
        }
    """
    try:
        data = request.json
        file_paths = data.get('files', [])

        if not file_paths:
            return jsonify({
                'success': False,
                'error': '파일을 선택해주세요.'
            }), 400

        # 청킹 설정
        chunk_config = {
            'size': data.get('chunk_size', 1000),
            'overlap': data.get('chunk_overlap', 200)
        }

        # 문서 서비스를 통해 로드
        result = doc_service.load_documents(file_paths, chunk_config)

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'{len(file_paths)}개 파일 로드 완료',
                'stats': result['stats']
            })
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(traceback.format_exc())

        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/load-collection/<collection_name>', methods=['POST'])
def load_collection(collection_name: str):
    """
    저장된 컬렉션을 활성화 (세션에 로드)

    Args:
        collection_name: 로드할 컬렉션 이름

    Returns:
        {
            'success': bool,
            'message': str,
            'stats': {...}
        }
    """
    try:
        result = doc_service.load_collection(collection_name)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        print(f"[ERROR] 컬렉션 로드 실패: {e}")
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/load-multiple-collections', methods=['POST'])
def load_multiple_collections():
    """
    여러 컬렉션을 동시에 활성화 (다중 문서 활성화)

    Request JSON:
        {
            'collections': [str, str, ...],  # 컬렉션 이름 리스트
            'filenames': [str, str, ...]  # 선택: 활성화할 특정 파일명 리스트
        }

    Returns:
        {
            'success': bool,
            'loaded': int,
            'failed': int,
            'failed_collections': [str],
            'active_collections': [str],
            'message': str
        }
    """
    try:
        data = request.get_json()
        collection_names = data.get('collections', [])
        filenames = data.get('filenames', None)  # 선택적 파일명 필터

        if not collection_names:
            return jsonify({
                'success': False,
                'error': '컬렉션 목록이 비어 있습니다.'
            }), 400

        # 다중 컬렉션 로드 (파일명 필터 전달)
        result = doc_service.load_multiple_collections(collection_names, filenames=filenames)

        if result['success']:
            return jsonify({
                'success': True,
                'loaded': result['loaded'],
                'failed': result['failed'],
                'failed_collections': result.get('failed_collections', []),
                'active_collections': result['active_collections'],
                'message': f'{result["loaded"]}개 컬렉션 로드 완료'
            })
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"[ERROR] 다중 컬렉션 로드 실패: {e}")
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/loaded', methods=['GET'])
def get_loaded_documents():
    """
    현재 세션에 로드된 문서 목록 반환 (카테고리 정보 포함)

    Returns:
        {
            'success': bool,
            'documents': [
                {
                    'filename': str,
                    'category': {...}
                }
            ]
        }
    """
    result = doc_service.get_loaded_documents()
    return jsonify(result)


@documents_bp.route('/status', methods=['GET'])
def get_status():
    """
    현재 시스템 상태 확인

    Returns:
        {
            'ready': bool,
            'documents_loaded': int,
            'llm_provider': str,
            'stats': {...}
        }
    """
    status_info = doc_service.get_status()
    return jsonify(status_info)


@documents_bp.route('/debug-state', methods=['GET'])
def get_debug_state():
    """디버그용: 현재 활성화 상태 확인"""
    return jsonify({
        'active_filenames': list(doc_service.active_filenames) if doc_service.active_filenames else None,
        'active_vectorstores_keys': list(doc_service.active_vectorstores.keys()) if doc_service.active_vectorstores else [],
        'rag_exists': doc_service.rag is not None,
        'rag_doc_service_exists': doc_service.rag.doc_service is not None if doc_service.rag else False,
        'rag_doc_service_is_same': doc_service.rag.doc_service is doc_service if doc_service.rag and doc_service.rag.doc_service else False,
        'rag_doc_service_active_filenames': list(doc_service.rag.doc_service.active_filenames) if doc_service.rag and doc_service.rag.doc_service and doc_service.rag.doc_service.active_filenames else None,
        'doc_service_id': id(doc_service),
        'rag_doc_service_id': id(doc_service.rag.doc_service) if doc_service.rag and doc_service.rag.doc_service else None
    })


@documents_bp.route('/<path:filename>/chunks/preview', methods=['GET'])
def get_chunk_preview(filename: str):
    """
    특정 문서의 청크 미리보기 조회 (처음 N개)

    Args:
        filename: 파일명

    Query Parameters:
        collection: 컬렉션 이름 (required)
        limit: 미리보기 청크 개수 (optional, default: 3)

    Returns:
        {
            'success': bool,
            'filename': str,
            'total_chunks': int,
            'preview_chunks': [
                {
                    'chunk_index': int,
                    'content': str,
                    'length': int,
                    'metadata': dict
                },
                ...
            ],
            'error': str (optional)
        }
    """
    try:
        collection = request.args.get('collection')
        limit = request.args.get('limit', 3, type=int)

        if not collection:
            return jsonify({
                'success': False,
                'error': '컬렉션 이름이 필요합니다.'
            }), 400

        result = doc_service.get_document_chunks_preview(filename, collection, limit)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"청크 미리보기 조회 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@documents_bp.route('/<path:filename>/chunks', methods=['GET'])
def get_all_chunks(filename: str):
    """
    특정 문서의 전체 청크 조회 (페이지네이션)

    Args:
        filename: 파일명

    Query Parameters:
        collection: 컬렉션 이름 (required)
        page: 페이지 번호 (optional, default: 1)
        per_page: 페이지당 청크 개수 (optional, default: 10)

    Returns:
        {
            'success': bool,
            'filename': str,
            'total_chunks': int,
            'current_page': int,
            'total_pages': int,
            'chunks': [
                {
                    'chunk_index': int,
                    'content': str,
                    'length': int,
                    'metadata': dict
                },
                ...
            ],
            'error': str (optional)
        }
    """
    try:
        collection = request.args.get('collection')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        if not collection:
            return jsonify({
                'success': False,
                'error': '컬렉션 이름이 필요합니다.'
            }), 400

        result = doc_service.get_document_chunks_all(filename, collection, page, per_page)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"전체 청크 조회 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
