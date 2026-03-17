"""
RAG 시스템 웹 애플리케이션

Flask 기반 웹 인터페이스로 RAG 시스템을 쉽게 사용할 수 있습니다.
"""

import os
import sys
import io
import logging
from flask import Flask, render_template, request as flask_request, jsonify
from dotenv import load_dotenv

# Windows 인코딩 문제 해결
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (AttributeError, ValueError):
        pass

# Segmentation fault 방지를 위한 환경 변수 설정
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# .env 로드 (override=True: .env 파일 값이 환경 변수를 덮어씀)
load_dotenv(override=True)

# 로깅 설정
file_handler = logging.FileHandler('app.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

handlers = [file_handler, console_handler]

logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("로깅 시스템 초기화 완료")
logger.info(f"  - 파일 로그: app.log")
logger.info(f"  - 콘솔 로그: stderr")
logger.info("=" * 60)

# 안전한 print 함수
import builtins
_original_print = builtins.print


def safe_print(*args, **kwargs):
    """I/O 에러를 방지하는 안전한 print 함수"""
    msg = ' '.join(str(arg) for arg in args)

    try:
        _original_print(*args, **kwargs)
        return
    except (ValueError, AttributeError, OSError):
        pass

    try:
        sys.stderr.write(msg + '\n')
        sys.stderr.flush()
        return
    except (ValueError, AttributeError, OSError):
        pass

    try:
        logger.info(msg)
    except:
        pass


builtins.print = safe_print

# 로컬 모듈 임포트
from src.category_manager import CategoryManager
from src.folder_manager import FolderManager
from src.services import FileService, DocumentService, CrawlingService
from src.vectorstore.faiss_store import FAISSVectorStore

app = Flask(__name__)

# ===== 서비스 레이어 초기화 =====
# 카테고리 관리자
category_manager = CategoryManager()

# 폴더 관리자
folder_manager = FolderManager()

# 파일 서비스
file_service = FileService(
    upload_folder='./uploads',
    metadata_path='./data/file_metadata.json',
    category_manager=category_manager
)

# 문서 서비스
doc_service = DocumentService(category_manager=category_manager)

# 삭제 서비스 (통합 삭제 처리)
from src.services import DeletionService
deletion_service = DeletionService(
    file_service=file_service,
    document_service=doc_service,
    documents_dir="./uploads",  # 실제 업로드 디렉토리
    faiss_dir="./data/faiss_web",
    html_dir="./html",
    file_metadata_path="./data/file_metadata.json"
)

# ===== 크롤링용 전역 변수 =====
current_vectorstore = None
crawling_service_instance = None


def get_embeddings():
    """임베딩 모델 가져오기"""
    from src.utils import get_embeddings as _get_embeddings
    return _get_embeddings()


def init_vectorstore():
    """벡터스토어 초기화"""
    global current_vectorstore
    if current_vectorstore is None:
        embeddings = get_embeddings()
        current_vectorstore = FAISSVectorStore(
            embedding_function=embeddings,
            collection_name="documents",
            persist_directory="./data/faiss_web"
        )
    return current_vectorstore


def get_crawling_service():
    """크롤링 서비스 가져오기"""
    vectorstore = init_vectorstore()
    return CrawlingService(
        vectorstore=vectorstore,
        category_manager=category_manager,
        file_metadata_handler={
            'metadata': file_service.file_metadata,
            'save_func': file_service._save_metadata
        },
        folder_manager=folder_manager
    )


def ensure_crawling_service():
    """크롤링 서비스 확인 및 초기화"""
    global crawling_service_instance
    if crawling_service_instance is None:
        crawling_service_instance = get_crawling_service()
        init_crawling_service(crawling_service_instance)


# ===== Blueprint 등록 =====
# 카테고리 API
from src.api.categories import categories_bp, init_category_manager
init_category_manager(category_manager)
app.register_blueprint(categories_bp)

# 폴더 API
from src.api.folders import folders_bp, init_folder_manager
init_folder_manager(folder_manager)
app.register_blueprint(folders_bp)

# 문서 관리 API
from src.api.documents import documents_bp, init_document_service
init_document_service(doc_service)
app.register_blueprint(documents_bp)

# 쿼리/질의응답 API
from src.api.query import query_bp, init_document_service as init_query_service
init_query_service(doc_service)
app.register_blueprint(query_bp)

# 파일 관리 API
from src.api.files import files_bp, init_file_service
init_file_service(file_service, category_manager)
app.register_blueprint(files_bp)

# 크롤링 API
from src.api.crawling import crawling_bp, init_crawling_service
app.register_blueprint(crawling_bp)


# 크롤링 API 요청 전에만 서비스 초기화
@app.before_request
def before_request():
    """크롤링 API 요청 전에만 크롤링 서비스 초기화"""
    # 크롤링 API 경로에만 적용
    if flask_request.path.startswith('/api/crawl'):
        ensure_crawling_service()


# ============================================
# 메인 페이지
# ============================================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')


# ============================================
# 시스템 상태 API
# ============================================

@app.route('/api/status', methods=['GET'])
def get_status():
    """시스템 상태 조회"""
    try:
        status = {
            'embedding_loaded': doc_service.embedding_model is not None,
            'rag_loaded': doc_service.rag is not None,
            'loaded_collection': getattr(doc_service, 'loaded_collection', None),  # 호환성 수정
            'crawl_vectorstore_loaded': current_vectorstore is not None
        }
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] /api/status 실패: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================
# 하위 호환성 라우트 (레거시 프론트엔드 지원)
# ============================================

@app.route('/api/upload', methods=['POST'])
def upload_file_legacy():
    """하위 호환성: /api/upload -> /api/files/upload로 리다이렉트"""
    from src.api.files import upload_file
    return upload_file()


@app.route('/api/load', methods=['POST'])
def load_documents_legacy():
    """하위 호환성: /api/load -> /api/documents/load로 리다이렉트"""
    from src.api.documents import load_documents
    return load_documents()


@app.route('/api/load-collection/<collection_name>', methods=['POST'])
def load_collection_legacy(collection_name: str):
    """하위 호환성: /api/load-collection -> /api/documents/load-collection로 리다이렉트"""
    from src.api.documents import load_collection
    return load_collection(collection_name)


@app.route('/api/debug-filter-state', methods=['GET'])
def get_debug_filter_state():
    """디버그: 필터 상태 확인"""
    from flask import jsonify
    return jsonify({
        'active_filenames': list(doc_service.active_filenames) if doc_service.active_filenames else None,
        'active_vectorstores': list(doc_service.active_vectorstores.keys()) if doc_service.active_vectorstores else [],
        'rag_exists': doc_service.rag is not None,
        'rag_has_doc_service': hasattr(doc_service.rag, 'doc_service') and doc_service.rag.doc_service is not None if doc_service.rag else False,
        'rag_doc_service_same': doc_service.rag.doc_service is doc_service if doc_service.rag and hasattr(doc_service.rag, 'doc_service') else False,
        'rag_doc_service_filenames': list(doc_service.rag.doc_service.active_filenames) if doc_service.rag and hasattr(doc_service.rag, 'doc_service') and doc_service.rag.doc_service and doc_service.rag.doc_service.active_filenames else None,
        'doc_service_id': id(doc_service)
    })


@app.route('/api/loaded-documents', methods=['GET'])
def get_loaded_documents_legacy():
    """하위 호환성: /api/loaded-documents -> /api/documents/loaded로 리다이렉트"""
    from src.api.documents import get_loaded_documents
    return get_loaded_documents()


# ========== 삭제 API ==========

@app.route('/api/documents/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    """
    문서 삭제 (원본 파일 + 벡터 DB)

    Query Parameters:
        scope: 삭제 범위 ('all', 'vector_only', 'file_only') - 기본값: 'all'
        collection: 특정 컬렉션 지정 (optional)

    Returns:
        {
            'success': bool,
            'message': str,
            'deleted': {
                'original_file': bool,
                'vector_chunks': bool,
                'file_metadata': bool,
                'document_metadata': bool
            },
            'details': dict
        }
    """
    from urllib.parse import unquote
    from src.services import DeletionScope

    # URL 디코딩
    filename = unquote(filename)

    # Query 파라미터 파싱
    scope_str = request.args.get('scope', 'all')
    collection = request.args.get('collection')

    # scope 변환
    try:
        scope = DeletionScope(scope_str)
    except ValueError:
        scope = DeletionScope.ALL

    logger.info(f"문서 삭제 요청: {filename}, scope={scope.value}, collection={collection}")

    # 통합 삭제 서비스 호출
    result = deletion_service.delete_document(
        filename=filename,
        collection=collection,
        scope=scope
    )

    if result['success']:
        # 삭제된 항목에 따른 메시지 생성
        deleted_items = []
        if result['deleted'].get('original_file'):
            deleted_items.append('원본 파일')
        if result['deleted'].get('vector_chunks'):
            deleted_items.append('벡터 DB 청크')
        if result['deleted'].get('file_metadata'):
            deleted_items.append('파일 메타데이터')

        message = f'문서 "{filename}"이(가) 삭제되었습니다.'
        if deleted_items:
            message += f' (삭제됨: {", ".join(deleted_items)})'

        return jsonify({
            'success': True,
            'message': message,
            'deleted': result['deleted'],
            'details': result.get('details', {})
        })
    else:
        return jsonify({
            'success': False,
            'error': result.get('errors', ['삭제 실패'])[0] if result.get('errors') else '삭제 실패',
            'errors': result.get('errors', []),
            'deleted': result['deleted']
        }), 400 if not any(result['deleted'].values()) else 200


@app.route('/api/documents', methods=['DELETE'])
def delete_documents():
    """
    모든 문서 데이터 삭제 (원본 파일 + 벡터 DB)

    Query Parameters:
        scope: 삭제 범위 ('all', 'vector_only', 'file_only') - 기본값: 'all'
        confirm: 확인 플래그 ('true' 필수)

    Returns:
        {
            'success': bool,
            'message': str,
            'deleted_count': {
                'original_files': int,
                'collections': int,
                'html_files': int
            }
        }
    """
    from src.services import DeletionScope

    # 안전장치: confirm 파라미터 필수
    confirm = request.args.get('confirm', '').lower() == 'true'
    if not confirm:
        return jsonify({
            'success': False,
            'error': '전체 삭제를 수행하려면 confirm=true 파라미터가 필요합니다.',
            'hint': 'DELETE /api/documents?confirm=true'
        }), 400

    # scope 파싱
    scope_str = request.args.get('scope', 'all')
    try:
        scope = DeletionScope(scope_str)
    except ValueError:
        scope = DeletionScope.ALL

    logger.info(f"전체 문서 삭제 요청: scope={scope.value}")

    try:
        result = deletion_service.delete_all_documents(scope=scope)

        if result['success']:
            counts = result['deleted_count']
            message = f'모든 문서가 삭제되었습니다. '
            message += f'(파일: {counts["original_files"]}개, '
            message += f'HTML: {counts["html_files"]}개, '
            message += f'컬렉션: {counts["collections"]}개)'

            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': counts
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '삭제 실패'),
                'errors': result.get('errors', []),
                'deleted_count': result.get('deleted_count', {})
            }), 500

    except Exception as e:
        logger.error(f"전체 문서 삭제 실패: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """
    업로드된 파일 삭제 (원본 파일 + 벡터 DB 연동)

    Query Parameters:
        include_vectors: 벡터 DB도 함께 삭제 ('true'/'false') - 기본값: 'true'
    """
    from src.services import DeletionScope

    include_vectors = request.args.get('include_vectors', 'true').lower() == 'true'

    try:
        if include_vectors:
            # 통합 삭제 (원본 + 벡터)
            result = deletion_service.delete_document(
                filename=filename,
                scope=DeletionScope.ALL
            )
        else:
            # 파일만 삭제
            result = file_service.delete_file(filename)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




if __name__ == '__main__':
    print("=" * 60)
    print("RAG 웹 애플리케이션 시작")
    print("=" * 60)
    print(f"\nLLM Provider: {os.getenv('LLM_PROVIDER', 'claude')}")
    print(f"Embedding: {os.getenv('EMBEDDING_PROVIDER', 'huggingface')}")
    print("\n브라우저에서 http://localhost:5000 으로 접속하세요.")
    print("=" * 60)

    # 임베딩 모델 사전 로드
    doc_service.init_embedding_model()

    # 크롤링된 문서 벡터스토어 로드 (있는 경우)
    try:
        crawl_persist_dir = "./data/faiss_web"
        crawl_index_path = os.path.join(crawl_persist_dir, "documents")

        if os.path.exists(f"{crawl_index_path}.faiss"):
            print("\n🔄 문서 벡터스토어 로딩 중...")
            embedding_model = doc_service.embedding_model
            current_vectorstore = FAISSVectorStore(
                embedding_function=embedding_model,
                collection_name="documents",
                persist_directory=crawl_persist_dir
            )
            current_vectorstore.load()
            print(f"✅ 크롤링 문서 벡터스토어 로드 완료\n")
        else:
            print("\n📝 크롤링된 문서 없음\n")
    except Exception as e:
        print(f"\n⚠️  크롤링 문서 로드 실패: {e}\n")

    # Flask 애플리케이션 실행
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)
