"""
크롤링 API 라우터

웹 크롤링 및 벡터 DB 저장을 처리합니다.
"""
from flask import Blueprint, request, jsonify, Response, stream_with_context
from src.services import CrawlingService
from src.services.structure_collector import NCloudStructureCollector
import json
import time
import threading

# Blueprint 생성
crawling_bp = Blueprint('crawling', __name__, url_prefix='/api/crawl')

# 존(Zone) URL 매핑 - 사용자 가이드
ZONE_BASE_URLS = {
    'standard': 'https://guide.ncloud-docs.com',
    'finance': 'https://guide-fin.ncloud-docs.com',
    'gov': 'https://guide-gov.ncloud-docs.com'
}

# 존(Zone) URL 매핑 - API 가이드
API_ZONE_BASE_URLS = {
    'standard': 'https://api.ncloud-docs.com',
    'finance': 'https://api-fin.ncloud-docs.com',
    'gov': 'https://api-gov.ncloud-docs.com'
}

# 문서 유형별 URL 매핑
DOC_TYPE_URLS = {
    'user_guide': ZONE_BASE_URLS,
    'api_guide': API_ZONE_BASE_URLS
}

# Zone별 기본 카테고리 목록 - 사용자 가이드 (폴백용)
_DEFAULT_USER_GUIDE_CATEGORIES = {
    'standard': [
        "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "Application Services", "AI·NAVER API",
        "Big Data & Analytics", "Blockchain", "Business Applications",
        "Content Delivery", "Developer Tools", "Digital Twin", "Gaming",
        "Hybrid & Private Cloud", "Management & Governance", "Media", "Migration"
    ],
    'finance': [
        "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "Application Services", "AI·NAVER API",
        "Big Data & Analytics", "Content Delivery", "Developer Tools",
        "Hybrid & Private Cloud", "Management & Governance", "Media", "Migration"
    ],
    'gov': [
        "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "Application Services", "AI·NAVER API",
        "Big Data & Analytics", "Business Applications", "Content Delivery",
        "Developer Tools", "Hybrid & Private Cloud", "Management & Governance",
        "Media", "Tools"
    ]
}

# Zone별 기본 카테고리 목록 - API 가이드 (폴백용)
_DEFAULT_API_GUIDE_CATEGORIES = {
    'standard': [
        "Platform", "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "Application Services", "AI·NAVER API",
        "Big Data & Analytics", "Blockchain", "Business Applications",
        "Content Delivery", "Developer Tools", "Digital Twin", "Gaming",
        "Hybrid & Private Cloud", "Management & Governance", "Media", "Migration"
    ],
    'finance': [
        "Platform", "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "Application Services", "AI·NAVER API",
        "Big Data & Analytics", "Content Delivery", "Developer Tools",
        "Hybrid & Private Cloud", "Management & Governance", "Media"
    ],
    'gov': [
        "Platform", "Compute", "Containers", "Storage", "Networking", "Database",
        "Security", "AI Services", "AI·NAVER API", "Application Services",
        "Big Data & Analytics", "Business Applications", "Developer Tools",
        "Content Delivery", "Management & Governance", "Media", "Hybrid & Private Cloud"
    ]
}

# 문서 유형별 기본 카테고리 매핑
_DEFAULT_CATEGORIES_BY_DOC_TYPE = {
    'user_guide': _DEFAULT_USER_GUIDE_CATEGORIES,
    'api_guide': _DEFAULT_API_GUIDE_CATEGORIES
}

# 호환성을 위한 기본 카테고리 (user_guide standard 기준)
_DEFAULT_CATEGORIES_BY_ZONE = _DEFAULT_USER_GUIDE_CATEGORIES
_DEFAULT_CATEGORIES = _DEFAULT_USER_GUIDE_CATEGORIES['standard']

# 카테고리 캐시 시스템 (doc_type + Zone별 독립 캐시)
def _init_zone_cache(zone: str = 'standard', doc_type: str = 'user_guide'):
    """Zone + doc_type 캐시 초기값 생성"""
    doc_type_categories = _DEFAULT_CATEGORIES_BY_DOC_TYPE.get(doc_type, _DEFAULT_USER_GUIDE_CATEGORIES)
    categories = doc_type_categories.get(zone, doc_type_categories.get('standard', _DEFAULT_CATEGORIES))
    return {
        'data': categories.copy(),
        'timestamp': time.time(),
        'ttl': 3600,  # 1시간
        'is_refreshing': False,
        'last_refresh_error': None
    }

# doc_type별, Zone별 캐시 구조
_categories_cache = {
    'user_guide': {
        'standard': _init_zone_cache('standard', 'user_guide'),
        'finance': _init_zone_cache('finance', 'user_guide'),
        'gov': _init_zone_cache('gov', 'user_guide')
    },
    'api_guide': {
        'standard': _init_zone_cache('standard', 'api_guide'),
        'finance': _init_zone_cache('finance', 'api_guide'),
        'gov': _init_zone_cache('gov', 'api_guide')
    }
}
_cache_lock = threading.Lock()  # 스레드 안전성


def _refresh_categories_background(zone: str = 'standard', doc_type: str = 'user_guide', timeout_seconds: int = 120):
    """
    백그라운드에서 Zone + doc_type별 카테고리 캐시 갱신 (non-blocking, 타임아웃 적용)

    Args:
        zone: 갱신할 Zone ('standard', 'finance', 'gov')
        doc_type: 문서 유형 ('user_guide', 'api_guide')
        timeout_seconds: 최대 실행 시간 (기본 2분)
    """
    global _categories_cache

    # 유효성 검사
    if zone not in ZONE_BASE_URLS:
        zone = 'standard'
    if doc_type not in DOC_TYPE_URLS:
        doc_type = 'user_guide'

    zone_cache = _categories_cache[doc_type][zone]

    with _cache_lock:
        if zone_cache['is_refreshing']:
            return  # 이미 갱신 중이면 스킵
        zone_cache['is_refreshing'] = True

    def do_refresh():
        global _categories_cache
        try:
            # doc_type에 따른 base_url 선택
            url_map = DOC_TYPE_URLS.get(doc_type, ZONE_BASE_URLS)
            base_url = url_map.get(zone, url_map['standard'])
            print(f"[카테고리 캐시] 백그라운드 갱신 시작... (doc_type={doc_type}, zone={zone}, url={base_url})")
            collector = NCloudStructureCollector(headless=True, base_url=base_url)
            collector.collect_structure()
            categories = collector.get_categories()

            if categories and len(categories) > 0:
                with _cache_lock:
                    _categories_cache[doc_type][zone]['data'] = categories
                    _categories_cache[doc_type][zone]['timestamp'] = time.time()
                    _categories_cache[doc_type][zone]['last_refresh_error'] = None
                print(f"[카테고리 캐시] 갱신 완료 (doc_type={doc_type}, zone={zone}): {len(categories)}개 카테고리")
            else:
                print(f"[카테고리 캐시] 갱신 실패 (doc_type={doc_type}, zone={zone}): 빈 결과, 기존 캐시 유지")
                with _cache_lock:
                    _categories_cache[doc_type][zone]['last_refresh_error'] = "빈 결과 반환됨"

        except Exception as e:
            print(f"[카테고리 캐시] 갱신 실패 (doc_type={doc_type}, zone={zone}): {e}, 기존 캐시 유지")
            with _cache_lock:
                _categories_cache[doc_type][zone]['last_refresh_error'] = str(e)
        finally:
            with _cache_lock:
                _categories_cache[doc_type][zone]['is_refreshing'] = False

    def do_refresh_with_timeout():
        """타임아웃이 적용된 갱신 래퍼"""
        refresh_thread = threading.Thread(target=do_refresh, daemon=True)
        refresh_thread.start()
        refresh_thread.join(timeout=timeout_seconds)

        if refresh_thread.is_alive():
            # 타임아웃 발생 - 스레드는 daemon이므로 자동 종료됨
            print(f"[카테고리 캐시] 갱신 타임아웃 (doc_type={doc_type}, zone={zone}, {timeout_seconds}초 초과)")
            with _cache_lock:
                _categories_cache[doc_type][zone]['is_refreshing'] = False
                _categories_cache[doc_type][zone]['last_refresh_error'] = f"갱신 타임아웃 ({timeout_seconds}초)"

    # 타임아웃 관리 스레드 실행
    thread = threading.Thread(target=do_refresh_with_timeout, daemon=True)
    thread.start()

# 전체 크롤링 상태 추적
full_crawl_status = {
    'is_running': False,
    'current_service': None,
    'current_index': 0,
    'total_services': 0,
    'completed_services': [],
    'errors': [],
    'total_pages': 0,
    'message': ''
}

# CrawlingService 인스턴스 (app.py에서 주입받을 예정)
crawling_service = None


def init_crawling_service(service: CrawlingService):
    """CrawlingService 인스턴스 주입"""
    global crawling_service
    crawling_service = service


@crawling_bp.route('', methods=['POST'])
def crawl_url():
    """
    URL을 크롤링하여 벡터 DB에 저장

    Request JSON:
        {
            "url": "https://...",
            "max_pages": 10,  # 선택: 최대 크롤링 페이지 수
            "headless": true,  # 선택: 백그라운드 실행 여부
            "category_id": "cat_xxx",  # 선택: 카테고리 ID
            "crawler_type": "ncloud"  # 선택: 크롤러 타입 (ncloud/generic)
        }

    Returns:
        {
            'success': bool,
            'message': str,
            'documents_count': int,
            'chunks_count': int,
            'service_name': str
        }
    """
    try:
        data = request.get_json()
        url = data.get('url')
        max_pages = data.get('max_pages')
        headless = data.get('headless', True)
        category_id = data.get('category_id')
        crawler_type = data.get('crawler_type', 'ncloud')

        if not url:
            return jsonify({
                'success': False,
                'error': 'URL이 필요합니다.'
            }), 400

        # 크롤링 서비스를 통해 실행
        result = crawling_service.crawl_and_store(
            url=url,
            crawler_type=crawler_type,
            max_pages=max_pages,
            headless=headless,
            category_id=category_id
        )

        if result['success']:
            return jsonify(result)
        else:
            status_code = 500
            if 'partial_success' in result:
                status_code = 500
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@crawling_bp.route('/stream', methods=['POST'])
def crawl_url_stream():
    """
    URL을 크롤링하여 벡터 DB에 저장 (스트리밍)

    실시간으로 크롤링 진행 상황을 전송합니다.

    Request JSON:
        {
            "url": "https://...",
            "max_pages": 10,  # 선택: 최대 크롤링 페이지 수
            "headless": true,  # 선택: 백그라운드 실행 여부
            "category_id": "cat_xxx",  # 선택: 카테고리 ID
            "crawler_type": "ncloud"  # 선택: 크롤러 타입 (ncloud/generic)
        }

    Returns:
        Server-Sent Events stream:
            data: {"type": "status", "message": "..."}
            data: {"type": "progress", "message": "..."}
            data: {"type": "complete", "documents_count": 5, "chunks_count": 42, ...}
            data: {"type": "error", "message": "..."}
    """
    try:
        data = request.get_json()
        url = data.get('url')
        max_pages = data.get('max_pages')
        headless = data.get('headless', True)
        category_id = data.get('category_id')
        crawler_type = data.get('crawler_type', 'ncloud')

        if not url:
            return jsonify({
                'success': False,
                'error': 'URL이 필요합니다.'
            }), 400

        def generate():
            """SSE 스트림 생성"""
            try:
                # 크롤링 서비스 스트림 실행
                for event in crawling_service.crawl_and_store_stream(
                    url=url,
                    crawler_type=crawler_type,
                    max_pages=max_pages,
                    headless=headless,
                    category_id=category_id
                ):
                    yield f"data: {json.dumps(event)}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# 전체 가이드 크롤링 API
# =============================================================================

@crawling_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    사용 가능한 NCloud 카테고리 목록 반환 (논블로킹, 항상 즉시 응답)

    핵심 원칙:
    - API는 절대 블로킹되지 않음 (항상 즉시 응답)
    - 캐시 만료 시 백그라운드에서 갱신, 기존 데이터 즉시 반환
    - 스크래핑 실패해도 서비스 영향 없음 (기본 카테고리 사용)

    Query Parameters:
        zone: Zone 선택 ('standard', 'finance', 'gov'), 기본값 'standard'
        doc_type: 문서 유형 ('user_guide', 'api_guide'), 기본값 'user_guide'
        refresh: 'true'면 백그라운드 갱신 트리거

    Returns:
        {
            'success': True,
            'categories': ['Compute', 'Containers', ...],
            'zone': 'standard',
            'doc_type': 'user_guide',
            'cached': True/False,
            'refreshing': True/False  # 백그라운드 갱신 중 여부
        }
    """
    # Zone 파라미터 확인 (기본값: standard)
    zone = request.args.get('zone', 'standard')
    if zone not in ZONE_BASE_URLS:
        zone = 'standard'

    # doc_type 파라미터 확인 (기본값: user_guide)
    doc_type = request.args.get('doc_type', 'user_guide')
    if doc_type not in DOC_TYPE_URLS:
        doc_type = 'user_guide'

    # 강제 새로고침 파라미터 확인
    force_refresh = request.args.get('refresh', '').lower() == 'true'

    # doc_type + Zone별 캐시 유효성 확인
    zone_cache = _categories_cache[doc_type][zone]
    current_time = time.time()
    with _cache_lock:
        cache_age = current_time - zone_cache['timestamp']
        cache_expired = cache_age >= zone_cache['ttl']
        is_refreshing = zone_cache['is_refreshing']
        cached_data = zone_cache['data']
        last_error = zone_cache['last_refresh_error']

    # 캐시 만료 또는 강제 새로고침 시 백그라운드 갱신 트리거
    if (cache_expired or force_refresh) and not is_refreshing:
        _refresh_categories_background(zone=zone, doc_type=doc_type)
        is_refreshing = True

    # doc_type + Zone별 기본 카테고리 (폴백용)
    doc_type_defaults = _DEFAULT_CATEGORIES_BY_DOC_TYPE.get(doc_type, _DEFAULT_USER_GUIDE_CATEGORIES)
    zone_defaults = doc_type_defaults.get(zone, doc_type_defaults.get('standard', _DEFAULT_CATEGORIES))

    # 항상 즉시 응답 (캐시된 데이터 또는 기본값)
    response_data = {
        'success': True,
        'categories': cached_data if cached_data else zone_defaults,
        'count': len(cached_data) if cached_data else len(zone_defaults),
        'zone': zone,
        'doc_type': doc_type,
        'cached': not cache_expired,
        'refreshing': is_refreshing
    }

    # 캐시 만료 경고 추가
    if cache_expired:
        response_data['warning'] = '캐시가 만료되어 백그라운드에서 갱신 중입니다.'

    # 마지막 갱신 에러가 있으면 정보 추가
    if last_error:
        response_data['last_refresh_error'] = last_error

    return jsonify(response_data)


@crawling_bp.route('/services', methods=['GET'])
def get_services():
    """
    홈 페이지에서 모든 서비스 목록 조회

    Query Parameters:
        categories: 쉼표로 구분된 카테고리 목록 (선택)

    Returns:
        {
            'success': True,
            'services': [
                {'category': 'Compute', 'service_name': 'Server', 'service_url': '...'},
                ...
            ],
            'total': 50
        }
    """
    try:
        categories_param = request.args.get('categories', '')
        categories = [c.strip() for c in categories_param.split(',') if c.strip()] if categories_param else None

        # 서비스 목록 조회
        services = crawling_service.get_all_services(categories=categories)

        return jsonify({
            'success': True,
            'services': services,
            'total': len(services)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@crawling_bp.route('/all/status', methods=['GET'])
def get_full_crawl_status():
    """
    전체 크롤링 진행 상태 조회

    Returns:
        {
            'is_running': bool,
            'current_service': str,
            'current_index': int,
            'total_services': int,
            'completed_services': [...],
            'errors': [...],
            'total_pages': int,
            'message': str
        }
    """
    return jsonify(full_crawl_status)


@crawling_bp.route('/all', methods=['POST'])
def start_full_crawl():
    """
    전체 가이드 크롤링 시작 (스트리밍)

    Request JSON:
        {
            "categories": ["Compute", "Storage"],  # 선택: 카테고리 목록 (비어있으면 전체)
            "category_id": "guide",  # 선택: 저장할 카테고리 ID
            "zone": "standard",  # 선택: 존 (standard, finance, gov)
            "doc_types": ["user_guide", "api_guide"]  # 선택: 문서 유형 (기본: user_guide만)
        }

    Returns:
        Server-Sent Events stream
    """
    global full_crawl_status

    try:
        # 이미 실행 중인지 확인
        if full_crawl_status['is_running']:
            return jsonify({
                'success': False,
                'error': '전체 크롤링이 이미 실행 중입니다.'
            }), 400

        data = request.get_json() or {}
        categories = data.get('categories', [])
        category_id = data.get('category_id', 'guide')
        zone = data.get('zone', 'standard')
        doc_types = data.get('doc_types', ['user_guide'])

        # doc_types 유효성 검사
        valid_doc_types = [dt for dt in doc_types if dt in DOC_TYPE_URLS]
        if not valid_doc_types:
            valid_doc_types = ['user_guide']

        # 존 이름 매핑 (로그용)
        zone_names = {'standard': '일반', 'finance': '금융', 'gov': '공공'}
        zone_name = zone_names.get(zone, '일반')

        # 문서 유형 이름 매핑 (로그용)
        doc_type_names = {'user_guide': '사용자 가이드', 'api_guide': 'API 가이드'}

        # 빈 리스트면 None으로 변환 (전체 카테고리)
        if not categories:
            categories = None

        def generate():
            global full_crawl_status

            try:
                # 상태 초기화
                full_crawl_status = {
                    'is_running': True,
                    'current_service': None,
                    'current_index': 0,
                    'total_services': 0,
                    'completed_services': [],
                    'errors': [],
                    'total_pages': 0,
                    'message': '크롤링 시작 중...',
                    'current_doc_type': None
                }

                doc_type_count = len(valid_doc_types)
                yield f"data: {json.dumps({'type': 'status', 'message': f'[{zone_name}] 전체 크롤링 시작... ({doc_type_count}개 문서 유형)'})}\n\n"

                # 각 문서 유형에 대해 크롤링 실행
                for doc_type_idx, doc_type in enumerate(valid_doc_types):
                    doc_type_name = doc_type_names.get(doc_type, doc_type)
                    full_crawl_status['current_doc_type'] = doc_type

                    # 문서 유형에 따른 base_url 설정
                    url_map = DOC_TYPE_URLS.get(doc_type, ZONE_BASE_URLS)
                    base_url = url_map.get(zone, url_map['standard'])

                    yield f"data: {json.dumps({'type': 'doc_type_start', 'doc_type': doc_type, 'doc_type_name': doc_type_name, 'index': doc_type_idx + 1, 'total': doc_type_count})}\n\n"

                    # 진행상황 콜백
                    def progress_callback(msg, current=0, total=0):
                        full_crawl_status['message'] = f"[{doc_type_name}] {msg}"
                        if total > 0:
                            full_crawl_status['current_index'] = current
                            full_crawl_status['total_services'] = total

                    # 저장 콜백 (doc_type 메타데이터 추가)
                    def save_callback(service_result):
                        service_name = service_result['name']
                        page_count = service_result['page_count']

                        # doc_type 메타데이터 추가
                        service_result['doc_type'] = doc_type

                        # doc_type에 따라 실제 저장할 category_id 결정
                        # - api_guide → 'api'
                        # - user_guide → 'guide'
                        effective_category_id = 'api' if doc_type == 'api_guide' else 'guide'

                        # 크롤링 서비스를 통해 저장
                        try:
                            crawling_service.store_service_pages(
                                service_result,
                                category_id=effective_category_id,
                                doc_type=doc_type
                            )
                            full_crawl_status['completed_services'].append(f"[{doc_type_name}] {service_name}")
                            full_crawl_status['total_pages'] += page_count
                        except Exception as e:
                            full_crawl_status['errors'].append(f"[{doc_type_name}] {service_name}: {str(e)}")

                    # 해당 문서 유형 크롤링 실행
                    for event in crawling_service.crawl_all_services_stream(
                        categories=categories,
                        progress_callback=progress_callback,
                        save_callback=save_callback,
                        category_id=category_id,
                        base_url=base_url
                    ):
                        # 이벤트에 doc_type 정보 추가
                        event['doc_type'] = doc_type
                        event['doc_type_name'] = doc_type_name
                        yield f"data: {json.dumps(event)}\n\n"

                    yield f"data: {json.dumps({'type': 'doc_type_complete', 'doc_type': doc_type, 'doc_type_name': doc_type_name})}\n\n"

                # 완료
                full_crawl_status['is_running'] = False
                full_crawl_status['message'] = '크롤링 완료'
                full_crawl_status['current_doc_type'] = None

                yield f"data: {json.dumps({'type': 'complete', 'status': full_crawl_status})}\n\n"

            except Exception as e:
                full_crawl_status['is_running'] = False
                full_crawl_status['errors'].append(str(e))
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@crawling_bp.route('/all/stop', methods=['POST'])
def stop_full_crawl():
    """
    전체 크롤링 중지 요청

    Returns:
        {'success': True, 'message': '...'}
    """
    global full_crawl_status

    if not full_crawl_status['is_running']:
        return jsonify({
            'success': False,
            'error': '실행 중인 크롤링이 없습니다.'
        }), 400

    # 중지 플래그 설정 (실제 중지는 크롤링 루프에서 확인)
    full_crawl_status['is_running'] = False
    full_crawl_status['message'] = '크롤링 중지 요청됨'

    return jsonify({
        'success': True,
        'message': '크롤링 중지 요청이 전송되었습니다.'
    })
