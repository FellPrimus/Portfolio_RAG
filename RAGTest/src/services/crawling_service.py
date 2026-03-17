"""
크롤링 서비스

웹 크롤링과 관련된 비즈니스 로직을 담당합니다.
"""
import logging
import os
import threading
import queue
import time
from typing import List, Dict, Optional, Callable, Generator
from urllib.parse import urlparse
from langchain_core.documents import Document  # LangChain 1.0+

# Clean Code 리팩토링: 설정 import
from src.config.settings import get_settings
from src.loaders.playwright_crawler import (
    get_all_services as crawler_get_all_services,
    crawl_all_services as crawler_crawl_all_services,
    get_section_links,
    get_base_url,
    extract_section_content,
    clean_text
)
from src.services.structure_collector import NCloudStructureCollector
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class CrawlingService:
    """
    크롤링 서비스

    웹 크롤링, 문서 청킹, 벡터 DB 저장을 처리합니다.
    """

    def __init__(self, vectorstore, category_manager, file_metadata_handler, folder_manager=None):
        """
        Args:
            vectorstore: FAISS 벡터스토어 인스턴스
            category_manager: 카테고리 매니저 인스턴스
            file_metadata_handler: 파일 메타데이터 핸들러 (딕셔너리와 저장 함수)
            folder_manager: 폴더 매니저 인스턴스 (선택)
        """
        self.vectorstore = vectorstore
        self.category_manager = category_manager
        self.file_metadata = file_metadata_handler['metadata']
        self.save_metadata = file_metadata_handler['save_func']
        self.folder_manager = folder_manager

    def _handle_duplicate_url(self, url: str) -> bool:
        """중복 URL 처리 - 기존 문서 삭제

        Args:
            url: 크롤링 URL

        Returns:
            기존 문서가 있었는지 여부
        """
        if url not in self.file_metadata:
            return False

        logger.info(f"기존 URL 발견, 덮어쓰기 진행: {url}")

        try:
            # 벡터 DB에서 해당 URL 청크 삭제
            self.vectorstore.delete_by_metadata({'source': url})
            logger.info(f"벡터 DB에서 기존 청크 삭제 완료")
        except Exception as e:
            logger.warning(f"벡터 DB 청크 삭제 실패 (무시): {e}")

        # 메타데이터 삭제
        del self.file_metadata[url]
        self.save_metadata()
        logger.info(f"메타데이터 삭제 완료")

        return True

    def _delete_service_documents(self, service_name: str, category_id: str) -> bool:
        """동일 서비스의 기존 문서 삭제 (덮어쓰기용)

        Args:
            service_name: 서비스명
            category_id: 카테고리 ID

        Returns:
            기존 문서가 있었는지 여부
        """
        metadata_key = f"{category_id}:{service_name}"

        if metadata_key not in self.file_metadata:
            return False

        logger.info(f"기존 서비스 문서 삭제: {service_name} (카테고리: {category_id})")

        try:
            # 벡터 DB에서 해당 서비스의 모든 청크 삭제
            self.vectorstore.delete_by_metadata({'service_name': service_name})
            logger.info(f"벡터 DB에서 서비스 '{service_name}' 청크 삭제 완료")
        except Exception as e:
            logger.warning(f"벡터 DB 청크 삭제 실패 (무시): {e}")

        # 메타데이터 삭제
        del self.file_metadata[metadata_key]
        self.save_metadata()
        logger.info(f"메타데이터 삭제 완료: {metadata_key}")

        return True

    def _generate_display_name(self, service_name: str) -> str:
        """직관적인 문서 표시명 생성

        Args:
            service_name: 서비스명

        Returns:
            표시명 (예: "VPC(Virtual Private Cloud)_가이드")
        """
        if not service_name or service_name == 'Unknown':
            return '문서_가이드'
        return f"{service_name}_가이드"

    def _assign_to_folder(self, url: str, doc_id: str) -> Optional[str]:
        """URL 기반 폴더 자동 할당

        Args:
            url: 크롤링 URL
            doc_id: 문서 ID

        Returns:
            할당된 폴더 ID (없으면 None)
        """
        if not self.folder_manager:
            return None

        folder_id = self.folder_manager.get_folder_for_url(url)
        if folder_id:
            self.folder_manager.assign_document_to_folder(doc_id, folder_id)
            logger.info(f"문서를 폴더 '{folder_id}'에 할당")
            return folder_id

        return None

    def _assign_to_category_folder(
        self,
        url: str,
        doc_id: str,
        category: str,
        service_name: str
    ) -> Optional[str]:
        """카테고리별 폴더 계층 구조로 문서 할당

        폴더 구조: NCP Guide > {category} > {service_name}
        예: NCP Guide > Networking > VPC

        Args:
            url: 크롤링 URL
            doc_id: 문서 ID
            category: 서비스 카테고리 (예: 'Networking')
            service_name: 서비스 이름 (예: 'VPC')

        Returns:
            할당된 폴더 ID (없으면 None)
        """
        if not self.folder_manager:
            return None

        # URL에서 기본 폴더 결정 (ncp-guide, ncp-fin-guide 등)
        base_folder_id = self.folder_manager.get_folder_for_url(url)
        if not base_folder_id:
            base_folder_id = 'ncp-guide'  # 기본값

        # 폴더 경로 생성: [category, service_name]
        folder_path = []
        if category:
            folder_path.append(category)
        if service_name:
            folder_path.append(service_name)

        if not folder_path:
            # 경로가 없으면 기본 폴더에 할당
            self.folder_manager.assign_document_to_folder(doc_id, base_folder_id)
            return base_folder_id

        # 폴더 경로 생성 또는 가져오기
        target_folder_id = self.folder_manager.get_or_create_folder_path(
            path=folder_path,
            base_folder_id=base_folder_id
        )

        # 문서를 폴더에 할당
        self.folder_manager.assign_document_to_folder(doc_id, target_folder_id)
        logger.info(f"문서를 폴더 경로에 할당: {base_folder_id} > {' > '.join(folder_path)}")

        return target_folder_id

    def crawl_and_store(
        self,
        url: str,
        crawler_type: str = 'ncloud',
        max_pages: Optional[int] = None,
        headless: bool = True,
        category_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict:
        """
        URL 크롤링 및 벡터 DB 저장

        Args:
            url: 크롤링할 URL
            crawler_type: 크롤러 타입 ('ncloud' 또는 'generic')
            max_pages: 최대 크롤링 페이지 수
            headless: 백그라운드 실행 여부
            category_id: 카테고리 ID
            progress_callback: 진행 상황 콜백 함수

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
            # 크롤러 클래스 임포트
            try:
                if crawler_type == 'generic':
                    from src.loaders import GenericWebCrawler as CrawlerClass
                else:
                    from src.loaders import PlaywrightCrawler as CrawlerClass
            except ImportError:
                return {
                    'success': False,
                    'error': 'Playwright가 설치되지 않았습니다. pip install playwright를 실행하고 playwright install chromium을 실행하세요.'
                }

            # 중복 URL 처리 (덮어쓰기)
            was_duplicate = self._handle_duplicate_url(url)
            if was_duplicate:
                logger.info(f"기존 문서 덮어쓰기 모드")

            # 크롤링 시작
            logger.info(f"웹 크롤링 시작 ({crawler_type}): {url}")

            # 크롤러 인스턴스 생성
            crawler = CrawlerClass(headless=headless)

            # 진행 상황 로깅
            def log_progress(msg):
                if progress_callback:
                    progress_callback(msg)
                logger.info(f"[크롤링] {msg}")

            # 크롤링 실행
            if crawler_type == 'generic':
                documents = crawler.crawl_url(
                    url,
                    progress_callback=log_progress,
                    category_id=category_id or 'general'
                )
            else:
                # 네이버 클라우드 크롤러
                documents = crawler.crawl_url(
                    url,
                    progress_callback=log_progress,
                    max_pages=max_pages,
                    category_id=category_id or 'guide'
                )

            if not documents:
                return {
                    'success': False,
                    'error': '크롤링된 문서가 없습니다.'
                }

            logger.info(f"크롤링 완료: {len(documents)}개 문서 수집")

            # Clean Code: 설정에서 청킹 값 가져오기
            settings = get_settings()
            from src.chunkers import TextChunker
            chunker = TextChunker(
                chunk_size=settings.chunking.default_chunk_size,
                chunk_overlap=settings.chunking.default_chunk_overlap
            )
            chunks = chunker.chunk_documents(documents)

            logger.info(f"청킹 완료: {len(chunks)}개 청크 생성")

            # 메타데이터 준비
            service_name = documents[0].metadata.get('service_name', 'Unknown')
            title = documents[0].metadata.get('title', service_name)

            # 카테고리 검증
            if category_id:
                category = self.category_manager.get_category(category_id)
                if not category:
                    return {
                        'success': False,
                        'error': f'유효하지 않은 카테고리 ID: {category_id}'
                    }

            # 청크에 category_id 추가
            for chunk in chunks:
                chunk.metadata['category_id'] = category_id or 'general'

            # 벡터 DB에 저장
            self.vectorstore.add_documents(chunks)
            logger.info(f"벡터 DB 저장 완료")

            # 벡터 DB 저장 성공 후에만 메타데이터 저장
            try:
                import time

                # 직관적 표시명 생성
                display_name = self._generate_display_name(service_name)

                # 메타데이터 저장
                self.file_metadata[url] = {
                    'filename': url,
                    'filepath': url,
                    'display_name': display_name,
                    'category_id': category_id,
                    'upload_time': time.time(),
                    'file_size': len(chunks),
                    'doc_type': 'web_crawled',
                    'service_name': service_name,
                    'title': title
                }
                self.save_metadata()

                # URL 기반 폴더 자동 할당 (doc_id는 파일명 사용 - 벡터DB 메타데이터와 일치)
                doc_filename = os.path.basename(urlparse(url).path)
                folder_id = self._assign_to_folder(url, doc_filename)

                # 카테고리 문서 수 증가
                if category_id:
                    self.category_manager.increment_document_count(category_id)
                    logger.info(f"카테고리 '{category_id}' 문서 수 증가")

                return {
                    'success': True,
                    'message': f'크롤링 완료: {len(documents)}개 문서, {len(chunks)}개 청크',
                    'documents_count': len(documents),
                    'chunks_count': len(chunks),
                    'service_name': service_name,
                    'display_name': display_name,
                    'folder_id': folder_id,
                    'title': title
                }

            except Exception as metadata_error:
                # 메타데이터 저장 실패
                logger.error(f"메타데이터 저장 실패: {str(metadata_error)}")
                return {
                    'success': False,
                    'error': f'벡터 DB 저장은 완료되었으나 메타데이터 저장 실패: {str(metadata_error)}',
                    'partial_success': True
                }

        except Exception as e:
            logger.error(f"크롤링 오류: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    def crawl_and_store_stream(
        self,
        url: str,
        crawler_type: str = 'ncloud',
        max_pages: Optional[int] = None,
        headless: bool = True,
        category_id: Optional[str] = None
    ) -> Generator[Dict, None, None]:
        """
        URL 크롤링 및 벡터 DB 저장 (스트리밍)

        실시간으로 크롤링 진행 상황을 전송합니다.

        Args:
            url: 크롤링할 URL
            crawler_type: 크롤러 타입 ('ncloud' 또는 'generic')
            max_pages: 최대 크롤링 페이지 수
            headless: 백그라운드 실행 여부
            category_id: 카테고리 ID

        Yields:
            {
                'type': 'status' | 'progress' | 'complete' | 'error',
                'message': str,
                'documents_count': int (optional),
                'chunks_count': int (optional),
                'service_name': str (optional)
            }
        """
        try:
            # 크롤러 클래스 임포트
            try:
                if crawler_type == 'generic':
                    from src.loaders import GenericWebCrawler as CrawlerClass
                else:
                    from src.loaders import PlaywrightCrawler as CrawlerClass
            except ImportError:
                yield {
                    'type': 'error',
                    'message': 'Playwright가 설치되지 않았습니다.'
                }
                return

            # 중복 URL 처리 (덮어쓰기)
            was_duplicate = self._handle_duplicate_url(url)
            if was_duplicate:
                yield {
                    'type': 'status',
                    'message': '기존 문서 발견, 덮어쓰기 진행...'
                }

            yield {
                'type': 'status',
                'message': f'{crawler_type} 크롤링 시작...'
            }

            # 크롤러 인스턴스 생성
            crawler = CrawlerClass(headless=headless)

            # Thread + Queue 패턴으로 실시간 스트리밍 구현
            progress_queue = queue.Queue()
            crawl_result = {'documents': None, 'error': None}

            # 진행 상황 콜백 - 큐에 메시지 추가
            def log_progress(msg):
                progress_queue.put({'type': 'progress', 'message': msg})

            # 크롤링을 별도 스레드에서 실행
            def crawl_thread():
                try:
                    if crawler_type == 'generic':
                        crawl_result['documents'] = crawler.crawl_url(
                            url,
                            progress_callback=log_progress,
                            category_id=category_id or 'general'
                        )
                    else:
                        crawl_result['documents'] = crawler.crawl_url(
                            url,
                            progress_callback=log_progress,
                            max_pages=max_pages,
                            category_id=category_id or 'guide'
                        )
                except Exception as e:
                    crawl_result['error'] = str(e)
                finally:
                    # 크롤링 완료 신호
                    progress_queue.put({'type': '_done'})

            # 크롤링 스레드 시작
            thread = threading.Thread(target=crawl_thread)
            thread.start()

            # 큐에서 메시지를 실시간으로 읽어서 yield
            while True:
                try:
                    msg = progress_queue.get(timeout=0.5)
                    if msg['type'] == '_done':
                        break
                    yield msg
                except queue.Empty:
                    # 스레드가 아직 살아있으면 계속 대기
                    if not thread.is_alive():
                        break
                    continue

            # 스레드 종료 대기
            thread.join(timeout=5)

            # 에러 체크
            if crawl_result['error']:
                yield {
                    'type': 'error',
                    'message': crawl_result['error']
                }
                return

            documents = crawl_result['documents']

            yield {
                'type': 'status',
                'message': f'크롤링 완료: {len(documents) if documents else 0}개 문서'
            }

            # 빈 문서 목록 체크
            if not documents:
                yield {
                    'type': 'error',
                    'message': '크롤링된 문서가 없습니다. URL을 확인하거나 다시 시도해주세요.'
                }
                return

            # Clean Code: 설정에서 청킹 값 가져오기
            settings = get_settings()
            from src.chunkers import TextChunker
            chunker = TextChunker(
                chunk_size=settings.chunking.default_chunk_size,
                chunk_overlap=settings.chunking.default_chunk_overlap
            )
            chunks = chunker.chunk_documents(documents)

            yield {
                'type': 'status',
                'message': f'청킹 완료: {len(chunks)}개 청크'
            }

            # 메타데이터 준비
            service_name = documents[0].metadata.get('service_name', 'Unknown')
            title = documents[0].metadata.get('title', service_name)

            # 카테고리 검증
            if category_id:
                category = self.category_manager.get_category(category_id)
                if not category:
                    raise ValueError(f"유효하지 않은 카테고리 ID: {category_id}")

            # 청크에 category_id 추가
            for chunk in chunks:
                chunk.metadata['category_id'] = category_id or 'general'

            yield {
                'type': 'status',
                'message': f'[정보] 카테고리: {category_id or "general"}'
            }

            # 벡터 DB 저장
            yield {
                'type': 'status',
                'message': '벡터 DB에 저장 중...'
            }

            self.vectorstore.add_documents(chunks)

            yield {
                'type': 'status',
                'message': '벡터 DB 저장 완료'
            }

            # 벡터 DB 저장 성공 후에만 메타데이터 저장
            try:
                import time

                # 직관적 표시명 생성
                display_name = self._generate_display_name(service_name)

                # 메타데이터 저장
                self.file_metadata[url] = {
                    'filename': url,
                    'filepath': url,
                    'display_name': display_name,
                    'category_id': category_id,
                    'upload_time': time.time(),
                    'file_size': len(chunks),
                    'doc_type': 'web_crawled',
                    'service_name': service_name,
                    'title': title
                }
                self.save_metadata()

                # URL 기반 폴더 자동 할당 (doc_id는 파일명 사용 - 벡터DB 메타데이터와 일치)
                doc_filename = os.path.basename(urlparse(url).path)
                folder_id = self._assign_to_folder(url, doc_filename)
                if folder_id:
                    yield {
                        'type': 'status',
                        'message': f'[정보] 폴더 자동 할당: {folder_id}'
                    }

                # 카테고리 문서 수 증가
                if category_id:
                    self.category_manager.increment_document_count(category_id)

                yield {
                    'type': 'complete',
                    'documents_count': len(documents),
                    'chunks_count': len(chunks),
                    'service_name': service_name,
                    'display_name': display_name,
                    'folder_id': folder_id,
                    'title': title
                }

            except Exception as metadata_error:
                yield {
                    'type': 'status',
                    'message': '메타데이터 저장 실패, 롤백 중...'
                }

                error_msg = f"벡터 DB 저장은 완료되었으나 메타데이터 저장 실패: {str(metadata_error)}"
                yield {
                    'type': 'error',
                    'message': error_msg
                }
                raise

        except Exception as e:
            yield {
                'type': 'error',
                'message': str(e)
            }

    # =========================================================================
    # 전체 가이드 크롤링 메서드
    # =========================================================================

    def get_all_services(self, categories: List[str] = None) -> List[Dict]:
        """
        홈 페이지에서 모든 서비스 목록 조회

        Args:
            categories: 조회할 카테고리 목록 (None이면 전체)

        Returns:
            List[Dict]: 서비스 목록
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )
                context = browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()

                try:
                    # 홈 페이지 로드
                    page.goto(
                        "https://guide.ncloud-docs.com/docs/home",
                        wait_until="domcontentloaded",
                        timeout=60000
                    )
                    page.wait_for_load_state("networkidle", timeout=60000)
                    page.wait_for_timeout(2000)

                    # 서비스 목록 수집
                    services = crawler_get_all_services(
                        page,
                        "https://guide.ncloud-docs.com",
                        categories
                    )
                    return services

                finally:
                    browser.close()

        except Exception as e:
            logger.error(f"서비스 목록 조회 실패: {str(e)}")
            raise

    def crawl_all_services_stream(
        self,
        categories: List[str] = None,
        progress_callback: Callable = None,
        save_callback: Callable = None,
        category_id: str = 'guide',
        base_url: str = 'https://guide.ncloud-docs.com'
    ) -> Generator[Dict, None, None]:
        """
        전체 가이드 크롤링 (스트리밍)

        Args:
            categories: 크롤링할 카테고리 목록
            progress_callback: 진행상황 콜백
            save_callback: 저장 콜백
            category_id: 저장할 카테고리 ID
            base_url: 크롤링 대상 base URL (존별로 다름)

        Yields:
            Dict: 진행상황 이벤트
        """
        try:
            # 디버깅: base_url 값 확인
            logger.info(f"[DEBUG] crawl_all_services_stream - base_url: {base_url}")
            yield {'type': 'status', 'message': f'구조 정보 수집 중... (base_url: {base_url})'}

            # 구조 수집기 초기화 (크롤링 세션 시작 시 1회, base_url 전달)
            structure_collector = NCloudStructureCollector(headless=True, base_url=base_url)
            structure_collector.collect_structure()

            # [DEBUG] 구조 수집기 상태 확인
            structure_debug = structure_collector.get_structure()
            total_services = sum(len(svcs) for svcs in structure_debug.values())
            logger.info(f"[DEBUG] 구조 수집기 완료: {len(structure_debug)}개 카테고리, {total_services}개 서비스")
            for cat, svcs in structure_debug.items():
                logger.info(f"[DEBUG]   {cat}: {len(svcs)}개 서비스")

            yield {'type': 'status', 'message': f'구조 수집 완료: {len(structure_debug)}개 카테고리, {total_services}개 서비스'}

            # [DEBUG] 요청된 카테고리 목록 확인
            if categories:
                logger.info(f"[DEBUG] 요청된 카테고리 ({len(categories)}개): {categories}")
                # 요청된 카테고리와 구조 수집기 카테고리 비교
                for cat in categories:
                    if cat not in structure_debug:
                        logger.warning(f"[DEBUG] 요청 카테고리 '{cat}'가 구조에 없음!")
                        logger.warning(f"[DEBUG]   요청 바이트: {list(cat.encode('utf-8'))}")
            else:
                logger.info(f"[DEBUG] 전체 카테고리 크롤링 (categories=None)")

            yield {'type': 'status', 'message': '홈 페이지 로딩 중...'}

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )
                context = browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                page = context.new_page()

                try:
                    # 홈 페이지 로드 (base_url 사용)
                    home_url = f"{base_url}/docs/home"
                    page.goto(
                        home_url,
                        wait_until="domcontentloaded",
                        timeout=60000
                    )
                    page.wait_for_load_state("networkidle", timeout=60000)
                    page.wait_for_timeout(2000)

                    yield {'type': 'status', 'message': '서비스 목록 수집 중...'}

                    # 서비스 목록 수집 (구조 수집기 전달, base_url 사용)
                    services = crawler_get_all_services(
                        page, base_url, categories,
                        structure_collector=structure_collector
                    )

                    if not services:
                        yield {'type': 'error', 'message': '서비스를 찾을 수 없습니다.'}
                        return

                    yield {
                        'type': 'status',
                        'message': f'총 {len(services)}개 서비스 발견',
                        'total_services': len(services)
                    }

                    if progress_callback:
                        progress_callback(f'총 {len(services)}개 서비스 발견', 0, len(services))

                    # 각 서비스 크롤링
                    for idx, service in enumerate(services, 1):
                        service_name = service['service_name']
                        service_url = service['service_url']
                        category = service['category']

                        yield {
                            'type': 'progress',
                            'message': f'[{idx}/{len(services)}] {category} > {service_name}',
                            'current': idx,
                            'total': len(services),
                            'service_name': service_name
                        }

                        if progress_callback:
                            progress_callback(
                                f'[{idx}/{len(services)}] {service_name}',
                                idx,
                                len(services)
                            )

                        try:
                            # 서비스 페이지로 이동
                            page.goto(service_url, wait_until="domcontentloaded", timeout=60000)
                            page.wait_for_load_state("networkidle", timeout=60000)
                            page.wait_for_timeout(1500)

                            # 사이드바 노드 로드 대기 (첫 페이지 이동 시 필수)
                            try:
                                page.wait_for_selector('[id^="node-"]', timeout=10000)
                            except Exception:
                                # 타임아웃 시에도 계속 진행 (이미 로드된 경우)
                                pass

                            # 서비스 내 페이지 URL 수집
                            service_pages = get_section_links(
                                page, base_url, service_url,
                                structure_collector=structure_collector
                            )

                            if not service_pages:
                                yield {
                                    'type': 'service_error',
                                    'service_name': service_name,
                                    'error': '페이지를 찾을 수 없습니다.'
                                }
                                continue

                            # 각 페이지를 별도 Document로 저장 (하위 문서 개별 수집)
                            documents = []
                            crawled_urls = []
                            service_title = service_name
                            is_api_guide = 'api.ncloud-docs.com' in base_url

                            for page_idx, page_info in enumerate(service_pages, 1):
                                page_url = page_info.get('url', '')
                                page_text = page_info.get('text', f'페이지 {page_idx}')

                                if not page_url:
                                    continue

                                try:
                                    response = page.goto(page_url, wait_until="domcontentloaded", timeout=60000)
                                    page.wait_for_load_state("networkidle", timeout=60000)
                                    page.wait_for_timeout(800)

                                    if response is None or response.status != 200:
                                        continue

                                    # 첫 페이지에서 서비스 제목 추출
                                    if page_idx == 1:
                                        raw_title = page.title() or ""
                                        if " - " in raw_title:
                                            service_title = raw_title.split(" - ")[0].strip()
                                        else:
                                            service_title = raw_title.strip() or service_name

                                    full_html = page.content()
                                    sections = extract_section_content(full_html)

                                    page_content_parts = []
                                    for section in sections:
                                        if section['content'].strip():
                                            section_text = f"## {section['heading']}\n\n{section['content']}"
                                            page_content_parts.append(section_text)

                                    if page_content_parts:
                                        page_content = f"# {page_text}\n\n" + "\n\n".join(page_content_parts)

                                        # API 가이드면 [API] 접두사 추가
                                        doc_title = f"[API] {page_text}" if is_api_guide else page_text

                                        # 각 페이지를 별도 Document로 생성
                                        doc = Document(
                                            page_content=clean_text(page_content),
                                            metadata={
                                                "source": page_url,
                                                "service_name": service_name,
                                                "service_title": service_title,
                                                "title": doc_title,
                                                "type": "web_crawled",
                                                "category": category_id,
                                                "category_id": category_id,
                                                "is_api_guide": is_api_guide
                                            }
                                        )
                                        documents.append(doc)
                                        crawled_urls.append(page_url)
                                        logger.info(f"페이지 수집: {doc_title} ({page_url})")

                                except Exception as page_error:
                                    logger.warning(f"페이지 크롤링 실패 ({page_url}): {str(page_error)}")
                                    continue

                            service_result = {
                                'name': service_name,
                                'category': category,
                                'service_id': service['service_id'],
                                'url': service_url,
                                'pages': service_pages,
                                'page_count': len(crawled_urls),
                                'documents': documents,  # 각 페이지별 Document 객체 리스트
                                'title': service_title,
                                'is_api_guide': is_api_guide
                            }

                            yield {
                                'type': 'service_complete',
                                'service_name': service_name,
                                'page_count': len(crawled_urls),
                                'document_count': len(documents),
                                'is_api_guide': is_api_guide
                            }

                            # 저장 콜백 호출 (documents가 있는 경우만)
                            if save_callback and documents:
                                save_callback(service_result)

                        except Exception as e:
                            yield {
                                'type': 'service_error',
                                'service_name': service_name,
                                'error': str(e)
                            }
                            logger.error(f"서비스 크롤링 실패 ({service_name}): {str(e)}")

                        # 서버 부하 방지
                        page.wait_for_timeout(500)

                finally:
                    browser.close()

        except Exception as e:
            yield {'type': 'error', 'message': str(e)}
            logger.error(f"전체 크롤링 실패: {str(e)}")

    def store_service_pages(
        self,
        service_result: Dict,
        category_id: str = 'guide',
        doc_type: str = 'user_guide'
    ) -> Dict:
        """
        서비스 페이지들을 벡터 DB에 저장 (이미 수집된 Document 객체 사용)

        Args:
            service_result: 서비스 크롤링 결과
                - name: 서비스 이름
                - category: 카테고리 이름 (예: 'Networking')
                - url: 서비스 메인 URL
                - documents: 이미 수집된 Document 객체 리스트
                - title: 문서 제목
            category_id: 카테고리 ID
            doc_type: 문서 유형 ('user_guide' 또는 'api_guide')

        Returns:
            Dict: 저장 결과
        """
        service_name = service_result['name']
        service_url = service_result['url']
        service_category = service_result.get('category', '')  # 예: 'Networking'
        documents = service_result.get('documents', [])
        title = service_result.get('title', service_name)

        if not documents:
            return {'success': False, 'error': '저장할 문서가 없습니다.'}

        try:
            # 메타데이터 키: 카테고리:서비스명 (서비스 단위 통합)
            metadata_key = f"{category_id}:{service_name}"

            # 기존 동일 서비스 문서 삭제 (덮어쓰기)
            is_overwrite = self._delete_service_documents(service_name, category_id)
            if is_overwrite:
                logger.info(f"기존 문서 덮어쓰기 완료: {service_name}")

            logger.info(f"문서 저장 시작: {service_name} ({len(documents)}개 페이지)")

            # 청킹
            settings = get_settings()
            from src.chunkers import TextChunker
            chunker = TextChunker(
                chunk_size=settings.chunking.default_chunk_size,
                chunk_overlap=settings.chunking.default_chunk_overlap
            )
            chunks = chunker.chunk_documents(documents)

            logger.info(f"청킹 완료: {len(chunks)}개 청크")

            # 청크에 category_id, doc_type 추가
            for chunk in chunks:
                chunk.metadata['category_id'] = category_id
                chunk.metadata['doc_type'] = doc_type  # user_guide 또는 api_guide

            # 벡터 DB에 저장
            self.vectorstore.add_documents(chunks)

            # 메타데이터 저장 (서비스 단위로 통합)
            # doc_type에 따른 display_name 접두사
            doc_type_prefix = '[API] ' if doc_type == 'api_guide' else ''
            display_name = doc_type_prefix + service_name  # 서비스명으로 통일

            self.file_metadata[metadata_key] = {
                'filename': metadata_key,
                'filepath': service_url,  # 대표 URL
                'display_name': display_name,
                'category_id': category_id,
                'upload_time': time.time(),
                'file_size': len(chunks),
                'doc_type': doc_type,
                'service_name': service_name,
                'title': title,
                'page_count': len(documents)  # 수집된 페이지 수
            }
            self.save_metadata()

            # 카테고리별 폴더 자동 생성 및 할당
            self._assign_to_category_folder(
                service_url,      # url - 폴더 결정에 사용
                metadata_key,     # doc_id - 문서 식별자
                service_category, # category - 예: 'Compute'
                service_name      # service_name - 예: 'Server'
            )

            # 카테고리 문서 수 증가
            if category_id:
                self.category_manager.increment_document_count(category_id)

            logger.info(f"서비스 '{service_name}' 저장 완료: {len(documents)}개 문서, {len(chunks)}개 청크")

            return {
                'success': True,
                'message': f'서비스 저장 완료',
                'documents_count': len(documents),
                'chunks_count': len(chunks),
                'service_name': service_name
            }

        except Exception as e:
            logger.error(f"서비스 저장 실패 ({service_name}): {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}
