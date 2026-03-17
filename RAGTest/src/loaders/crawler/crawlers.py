"""
크롤러 클래스 모듈

PlaywrightCrawler와 GenericWebCrawler 파사드 클래스를 제공합니다.
"""

from typing import List, Dict, Optional, Callable
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from langchain_core.documents import Document

from src.config.settings import get_settings

from .utils import (
    clean_text,
    get_base_url,
    get_service_name_from_url,
    extract_section_content
)
from .navigation import get_section_links
from .extraction import ContentExtractor


class PlaywrightCrawler:
    """
    Playwright 기반 NCloud 문서 크롤러

    동적 웹페이지를 크롤링하여 LangChain Document 객체로 변환합니다.
    """

    def __init__(
        self,
        headless: bool = None,
        timeout: int = None,
        wait_time: int = None
    ):
        """
        Args:
            headless: 브라우저를 백그라운드에서 실행할지 여부
            timeout: 페이지 로딩 타임아웃 (ms)
            wait_time: JavaScript 실행 대기 시간 (ms)
        """
        settings = get_settings()
        self.headless = headless if headless is not None else settings.crawling.headless
        self.timeout = timeout if timeout is not None else settings.crawling.timeout
        self.wait_time = wait_time if wait_time is not None else settings.crawling.wait_time

    def _create_log_function(self, progress_callback: Optional[Callable[[str], None]]):
        """로그 함수 생성"""
        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            else:
                print(msg)
        return log

    def crawl_url(
        self,
        start_url: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        max_pages: Optional[int] = None,
        category_id: str = 'guide'
    ) -> List[Document]:
        """
        주어진 URL부터 시작하여 좌측 메뉴의 모든 페이지를 크롤링

        Args:
            start_url: 시작 URL
            progress_callback: 진행 상황 콜백 함수
            max_pages: 최대 크롤링 페이지 수 (None이면 제한 없음)
            category_id: 카테고리 ID (general, api, guide, spec)

        Returns:
            List[Document]: LangChain Document 객체 리스트
        """
        documents = []
        visited = set()
        log = self._create_log_function(progress_callback)

        log(f"[크롤링 시작] {start_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            settings = get_settings()
            page.set_viewport_size({
                "width": settings.crawling.viewport_width,
                "height": settings.crawling.viewport_height
            })

            try:
                log("[단계 1/5] 시작 페이지 로딩 중...")
                page.goto(start_url, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                page.wait_for_timeout(self.wait_time)

                raw_page_title = page.title() or ""
                if " - " in raw_page_title:
                    document_title = raw_page_title.split(" - ")[0].strip()
                else:
                    document_title = raw_page_title.strip()
                log(f"[정보] 문서 제목: {document_title}")

                log("[단계 2/5] 현재 섹션 링크 수집 중...")
                base_url = get_base_url(start_url)
                menu_links = get_section_links(page, base_url, start_url)

                if not menu_links:
                    log("[경고] 섹션 링크를 찾을 수 없습니다. 현재 페이지만 크롤링합니다.")
                    service_name = get_service_name_from_url(start_url)
                    menu_links = [{
                        'url': start_url,
                        'text': service_name,
                        'serviceName': service_name
                    }]

                service_name = menu_links[0]['serviceName']
                if not service_name:
                    service_name = get_service_name_from_url(start_url)
                log(f"[정보] 섹션명: {service_name}")
                log(f"[정보] 섹션 내 페이지 수: {len(menu_links)}")

                if max_pages:
                    menu_links = menu_links[:max_pages]
                    log(f"[정보] 최대 {max_pages}개 페이지만 크롤링합니다.")

                log("[단계 3/5] 페이지 크롤링 시작...")
                total = len(menu_links)
                all_content_parts = []
                crawled_urls = []

                for idx, link in enumerate(menu_links, 1):
                    if link['url'] in visited:
                        log(f"[건너뜀 {idx}/{total}] 이미 방문한 페이지: {link['text']}")
                        continue
                    visited.add(link['url'])

                    log(f"[크롤링 {idx}/{total}] 페이지: {link['text']}")

                    try:
                        response = page.goto(link['url'], wait_until="domcontentloaded", timeout=self.timeout)
                        page.wait_for_load_state("networkidle", timeout=self.timeout)
                        page.wait_for_timeout(self.wait_time)

                        if response is None or response.status != 200:
                            status_code = response.status if response else 'None'
                            log(f"  [FAIL] HTTP {status_code}")
                            continue

                        full_html = page.content()
                        sections = extract_section_content(full_html)

                        if not sections:
                            log(f"  [WARN] 섹션 추출 실패")
                            continue

                        page_content_parts = []
                        for section in sections:
                            if section['content'].strip():
                                section_text = f"## {section['heading']}\n\n{section['content']}"
                                page_content_parts.append(section_text)

                        if page_content_parts:
                            page_title = f"# {link['text']}\n\n"
                            page_full_content = page_title + "\n\n".join(page_content_parts)
                            all_content_parts.append(page_full_content)
                            crawled_urls.append(link['url'])

                            content_length = len(page_full_content)
                            log(f"  [OK] {len(sections)}개 섹션, {content_length:,}자 추출")

                    except PlaywrightTimeoutError:
                        log(f"  [FAIL] 타임아웃")
                    except Exception as e:
                        log(f"  [FAIL] 오류: {str(e)}")

                if all_content_parts:
                    combined_content = "\n\n---\n\n".join(all_content_parts)

                    metadata = {
                        "source": start_url,
                        "service_name": service_name,
                        "title": document_title,
                        "crawled_urls": crawled_urls,
                        "page_count": len(crawled_urls),
                        "type": "web_crawled",
                        "category": category_id
                    }

                    doc = Document(
                        page_content=clean_text(combined_content),
                        metadata=metadata
                    )
                    documents.append(doc)

                log(f"[단계 4/5] 크롤링 완료: {len(crawled_urls)}개 페이지를 1개 문서로 통합")

            except Exception as e:
                log(f"[오류] 크롤링 중 오류 발생: {str(e)}")
                import traceback
                log(f"[상세] {traceback.format_exc()}")

            finally:
                browser.close()
                log("[단계 5/5] 브라우저 종료")

        return documents

    def crawl_pages_direct(
        self,
        page_urls: List[Dict[str, str]],
        service_name: str,
        service_url: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        category_id: str = 'guide'
    ) -> List[Document]:
        """
        사전 수집된 페이지 URL 목록을 직접 크롤링

        Args:
            page_urls: 페이지 URL 목록 [{'url': '...', 'text': '...'}]
            service_name: 서비스 이름
            service_url: 서비스 메인 URL
            progress_callback: 진행 상황 콜백 함수
            category_id: 카테고리 ID

        Returns:
            List[Document]: LangChain Document 객체 리스트
        """
        documents = []
        log = self._create_log_function(progress_callback)

        if not page_urls:
            log("[경고] 크롤링할 페이지 URL이 없습니다.")
            return documents

        log(f"[크롤링 시작] {service_name} - {len(page_urls)}개 페이지")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            settings = get_settings()
            page.set_viewport_size({
                "width": settings.crawling.viewport_width,
                "height": settings.crawling.viewport_height
            })

            try:
                all_content_parts = []
                crawled_urls = []
                document_title = service_name

                total = len(page_urls)
                for idx, link_info in enumerate(page_urls, 1):
                    link_url = link_info.get('url', '')
                    link_text = link_info.get('text', f'페이지 {idx}')

                    if not link_url:
                        continue

                    log(f"[크롤링 {idx}/{total}] {link_text}")

                    try:
                        response = page.goto(link_url, wait_until="domcontentloaded", timeout=self.timeout)
                        page.wait_for_load_state("networkidle", timeout=self.timeout)
                        page.wait_for_timeout(self.wait_time)

                        if response is None or response.status != 200:
                            log(f"  [FAIL] HTTP {response.status if response else 'None'}")
                            continue

                        if idx == 1:
                            raw_title = page.title() or ""
                            if " - " in raw_title:
                                document_title = raw_title.split(" - ")[0].strip()
                            else:
                                document_title = raw_title.strip() or service_name

                        full_html = page.content()
                        sections = extract_section_content(full_html)

                        if not sections:
                            log(f"  [WARN] 콘텐츠 추출 실패")
                            continue

                        page_content_parts = []
                        for section in sections:
                            if section['content'].strip():
                                section_text = f"## {section['heading']}\n\n{section['content']}"
                                page_content_parts.append(section_text)

                        if page_content_parts:
                            page_title = f"# {link_text}\n\n"
                            page_full_content = page_title + "\n\n".join(page_content_parts)
                            all_content_parts.append(page_full_content)
                            crawled_urls.append(link_url)
                            log(f"  [OK] {len(sections)}개 섹션, {len(page_full_content):,}자")

                    except PlaywrightTimeoutError:
                        log(f"  [FAIL] 타임아웃")
                    except Exception as e:
                        log(f"  [FAIL] 오류: {str(e)}")

                if all_content_parts:
                    combined_content = "\n\n---\n\n".join(all_content_parts)

                    metadata = {
                        "source": service_url,
                        "service_name": service_name,
                        "title": document_title,
                        "crawled_urls": crawled_urls,
                        "page_count": len(crawled_urls),
                        "type": "web_crawled",
                        "category": category_id,
                        "category_id": category_id
                    }

                    doc = Document(
                        page_content=clean_text(combined_content),
                        metadata=metadata
                    )
                    documents.append(doc)

                log(f"[완료] {len(crawled_urls)}개 페이지 크롤링 완료")

            except Exception as e:
                log(f"[오류] {str(e)}")
                import traceback
                log(traceback.format_exc())

            finally:
                browser.close()

        return documents

    def crawl_single_page(self, url: str) -> List[Document]:
        """
        단일 페이지만 크롤링

        Args:
            url: 크롤링할 URL

        Returns:
            List[Document]: LangChain Document 객체 리스트
        """
        documents = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                page.wait_for_timeout(self.wait_time)

                full_html = page.content()
                sections = extract_section_content(full_html)

                service_name = get_service_name_from_url(url)

                for section in sections:
                    if section['content'].strip():
                        metadata = {
                            "source": url,
                            "service_name": service_name,
                            "page_category": section['heading'],
                            "type": "web_crawled"
                        }

                        doc = Document(
                            page_content=clean_text(section['content']),
                            metadata=metadata
                        )
                        documents.append(doc)

            except Exception as e:
                print(f"페이지 크롤링 오류: {str(e)}")

            finally:
                browser.close()

        return documents


class GenericWebCrawler:
    """
    범용 웹 크롤러

    일반적인 웹페이지를 크롤링하여 LangChain Document 객체로 변환합니다.
    네이버 클라우드 플랫폼 전용이 아닌, 모든 웹사이트에 사용 가능합니다.
    """

    def __init__(
        self,
        headless: bool = None,
        timeout: int = None,
        wait_time: int = None
    ):
        """
        Args:
            headless: 브라우저를 백그라운드에서 실행할지 여부
            timeout: 페이지 로딩 타임아웃 (ms)
            wait_time: JavaScript 실행 대기 시간 (ms)
        """
        settings = get_settings()
        self.headless = headless if headless is not None else settings.crawling.headless
        self.timeout = timeout if timeout is not None else settings.crawling.timeout
        self.wait_time = wait_time if wait_time is not None else settings.crawling.wait_time
        self._content_extractor = ContentExtractor()

    def extract_main_content(self, html: str) -> str:
        """
        HTML에서 메인 콘텐츠 추출 (범용)

        Args:
            html: HTML 문자열

        Returns:
            추출된 콘텐츠 (마크다운 형식)
        """
        return self._content_extractor.extract_main_content(html)

    def crawl_url(
        self,
        url: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        max_depth: int = 0,
        category_id: str = 'general'
    ) -> List[Document]:
        """
        주어진 URL을 크롤링 (단일 페이지 또는 같은 도메인 내 링크 탐색)

        Args:
            url: 크롤링할 URL
            progress_callback: 진행 상황 콜백 함수
            max_depth: 링크 탐색 깊이 (0: 단일 페이지만, 1+: 하위 링크도 크롤링)
            category_id: 카테고리 ID

        Returns:
            List[Document]: LangChain Document 객체 리스트
        """
        documents = []

        def log(msg: str):
            if progress_callback:
                progress_callback(msg)
            else:
                print(msg)

        log(f"[크롤링 시작] {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            settings = get_settings()
            page.set_viewport_size({
                "width": settings.crawling.viewport_width,
                "height": settings.crawling.viewport_height
            })

            try:
                log("[단계 1/3] 페이지 로딩 중...")
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                page.wait_for_timeout(self.wait_time)

                log("[단계 2/3] 콘텐츠 추출 중...")
                html = page.content()
                content = self.extract_main_content(html)

                if content.strip():
                    page_title = page.title() or url

                    log(f"[정보] 카테고리: {category_id}")

                    metadata = {
                        "source": url,
                        "title": page_title,
                        "type": "web_crawled_generic",
                        "category": category_id
                    }

                    doc = Document(
                        page_content=clean_text(content),
                        metadata=metadata
                    )
                    documents.append(doc)
                    log(f"[성공] 콘텐츠 추출 완료: {len(content)} 문자")
                else:
                    log("[경고] 추출된 콘텐츠가 없습니다")

                log("[단계 3/3] 완료")

            except Exception as e:
                log(f"[오류] 크롤링 중 오류 발생: {str(e)}")
                import traceback
                log(f"[상세] {traceback.format_exc()}")

            finally:
                browser.close()
                log("[단계 3/3] 브라우저 종료")

        return documents
