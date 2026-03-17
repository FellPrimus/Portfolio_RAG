"""
서비스 수집 모듈

NCloud 문서 사이트의 전체 서비스 목록을 수집합니다.
"""

from typing import List, Dict, Callable
from playwright.sync_api import sync_playwright, Page

from src.loaders.crawler.utils import (
    get_base_url,
    extract_url_prefix,
    crawl_logger
)
from .section_navigator import get_section_links


def get_all_services(
    page: Page,
    base_url: str = "https://guide.ncloud-docs.com",
    categories: List[str] = None,
    progress_callback: Callable = None,
    structure_collector=None
) -> List[Dict]:
    """
    홈 페이지에서 모든 서비스 목록 수집

    Args:
        page: Playwright Page 객체
        base_url: 기본 URL
        categories: 수집할 카테고리 목록 (None이면 전체)
        progress_callback: 진행상황 콜백 함수
        structure_collector: NCloud 구조 수집기

    Returns:
        List[Dict]: 서비스 목록
    """
    def log(msg: str):
        if progress_callback:
            progress_callback(msg)
        else:
            print(msg)

    services = []

    # 구조 수집기 초기화
    if structure_collector is None:
        from src.services.structure_collector import NCloudStructureCollector
        structure_collector = NCloudStructureCollector(headless=True)
        structure_collector.collect_structure()

    if not structure_collector._collected:
        log(f"[ERROR] 구조 수집기가 수집되지 않음! 다시 수집 시도...")
        structure_collector.collect_structure()

    all_categories = structure_collector.get_categories()
    structure = structure_collector.get_structure()
    total_svc_count = sum(len(svcs) for svcs in structure.values())

    if not structure or total_svc_count == 0:
        log(f"[ERROR] 구조 수집기에 데이터가 없음! 재수집 시도...")
        structure_collector.refresh_structure()
        structure = structure_collector.get_structure()
        total_svc_count = sum(len(svcs) for svcs in structure.values())

    target_categories = categories if categories else all_categories

    crawl_logger.log(f"대상 카테고리: {len(target_categories)}개")
    crawl_logger.info(f"구조 수집기: {len(structure)}개 카테고리, {total_svc_count}개 서비스")

    try:
        page.wait_for_selector('[id^="node-"]', timeout=15000)
        page.wait_for_timeout(2000)

        for cat_idx, category in enumerate(target_categories):
            log(f"  카테고리 탐색: {category} ({cat_idx + 1}/{len(target_categories)})")

            category_service_names = structure_collector.get_services(category)

            # 서비스를 찾지 못한 경우 유사 카테고리 검색
            if not category_service_names and category not in structure:
                for stored_cat in structure.keys():
                    if category.lower() == stored_cat.lower():
                        category_service_names = structure_collector.get_services(stored_cat)
                        break
                    if category.lower().replace(' ', '') == stored_cat.lower().replace(' ', ''):
                        category_service_names = structure_collector.get_services(stored_cat)
                        break

            category_services = [
                {'service_name': svc_name, 'category': category}
                for svc_name in category_service_names
            ]

            if category_services:
                for svc in category_services:
                    service_name = svc['service_name']

                    try:
                        page.goto(base_url + "/docs/home", wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_selector('[id^="node-"]', timeout=10000)
                        page.wait_for_timeout(1000)

                        # 카테고리 확장
                        page.evaluate('''
                            (categoryName) => {
                                const nodes = document.querySelectorAll('[id^="node-"]');
                                for (const node of nodes) {
                                    const link = node.querySelector('a.data-title');
                                    if (link && link.textContent.trim() === categoryName) {
                                        const expandBtn = node.querySelector('.tree-arrow[role="button"]');
                                        if (expandBtn) {
                                            const icon = expandBtn.querySelector('i');
                                            const isExpanded = icon && icon.classList.contains('fa-angle-down');
                                            if (!isExpanded) {
                                                expandBtn.click();
                                            }
                                        }
                                        break;
                                    }
                                }
                            }
                        ''', category)
                        page.wait_for_timeout(800)

                        # 서비스 폴더 확장 후 첫 번째 페이지 URL 가져오기
                        first_page_url = page.evaluate('''
                            (serviceName) => {
                                const nodes = document.querySelectorAll('[id^="node-"]');
                                let serviceNode = null;
                                let serviceIndex = -1;

                                for (let i = 0; i < nodes.length; i++) {
                                    const node = nodes[i];
                                    const link = node.querySelector('a.data-title');
                                    if (link && link.textContent.trim() === serviceName) {
                                        serviceNode = node;
                                        serviceIndex = i;

                                        const expandBtn = node.querySelector('.tree-arrow[role="button"]');
                                        if (expandBtn) {
                                            const icon = expandBtn.querySelector('i');
                                            const isExpanded = icon && icon.classList.contains('fa-angle-down');
                                            if (!isExpanded) {
                                                expandBtn.click();
                                            }
                                        }
                                        break;
                                    }
                                }

                                if (!serviceNode) return null;

                                return new Promise(resolve => {
                                    setTimeout(() => {
                                        const updatedNodes = document.querySelectorAll('[id^="node-"]');

                                        for (let i = serviceIndex + 1; i < updatedNodes.length; i++) {
                                            const node = updatedNodes[i];
                                            const link = node.querySelector('a');
                                            if (link) {
                                                const href = link.getAttribute('href');
                                                if (href && href.startsWith('/docs/')) {
                                                    resolve(href);
                                                    return;
                                                }
                                                if (href === '' || href === null) {
                                                    break;
                                                }
                                            }
                                        }
                                        resolve(null);
                                    }, 800);
                                });
                            }
                        ''', service_name)

                        if first_page_url:
                            full_url = base_url + first_page_url
                            service_id = extract_url_prefix(first_page_url)
                            services.append({
                                'category': category,
                                'service_name': service_name,
                                'service_url': full_url,
                                'service_id': service_id
                            })
                            log(f"    + {service_name}: {full_url}")
                        else:
                            crawl_logger.warn(f"URL을 찾지 못함: {service_name}")

                    except Exception as e:
                        crawl_logger.error(f"서비스 URL 가져오기 실패 ({service_name}): {e}")

                log(f"    -> {len([s for s in services if s['category'] == category])}개 서비스 발견")

            page.wait_for_timeout(500)

        crawl_logger.log(f"서비스 목록 수집 완료: 총 {len(services)}개 서비스")
        return services

    except Exception as e:
        crawl_logger.error(f"서비스 목록 수집 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return services


def crawl_all_services(
    start_url: str = "https://guide.ncloud-docs.com/docs/home",
    categories: List[str] = None,
    progress_callback: Callable = None,
    save_callback: Callable = None
) -> Dict:
    """
    전체 가이드 크롤링

    Args:
        start_url: 홈 페이지 URL
        categories: 크롤링할 카테고리 목록 (None이면 전체)
        progress_callback: 진행상황 콜백 (message, current, total)
        save_callback: 서비스별 저장 콜백 (service_data)

    Returns:
        Dict: 크롤링 결과
    """
    def log(msg: str, current: int = 0, total: int = 0):
        if progress_callback:
            progress_callback(msg, current, total)
        else:
            print(msg)

    result = {
        'total_services': 0,
        'total_pages': 0,
        'services': [],
        'errors': []
    }

    crawl_logger.log("전체 크롤링 시작")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--no-sandbox'
            ]
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        try:
            log("[1/3] 홈 페이지 로딩 중...")
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(2000)

            log("[2/3] 서비스 목록 수집 중...")
            base_url = get_base_url(start_url)
            services = get_all_services(page, base_url, categories, progress_callback)

            if not services:
                crawl_logger.warn("서비스를 찾을 수 없습니다.")
                return result

            result['total_services'] = len(services)
            crawl_logger.info(f"총 {len(services)}개 서비스 발견")

            log("[3/3] 서비스별 페이지 크롤링...")
            for idx, service in enumerate(services, 1):
                service_name = service['service_name']
                service_url = service['service_url']
                category = service['category']

                log(f"[{idx}/{len(services)}] {category} > {service_name}", idx, len(services))

                try:
                    page.goto(service_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_load_state("networkidle", timeout=60000)
                    page.wait_for_timeout(1500)

                    service_pages = get_section_links(page, base_url, service_url)

                    service_result = {
                        'name': service_name,
                        'category': category,
                        'service_id': service['service_id'],
                        'url': service_url,
                        'pages': service_pages,
                        'page_count': len(service_pages)
                    }

                    result['services'].append(service_result)
                    result['total_pages'] += len(service_pages)

                    log(f"  -> {len(service_pages)}개 페이지 수집 완료")

                    if save_callback and service_pages:
                        save_callback(service_result)

                except Exception as e:
                    error_msg = f"{service_name}: {str(e)}"
                    result['errors'].append(error_msg)
                    crawl_logger.error(f"오류: {str(e)}")

                page.wait_for_timeout(500)

        except Exception as e:
            crawl_logger.error(f"전체 크롤링 실패: {str(e)}")
            result['errors'].append(str(e))

        finally:
            browser.close()

    crawl_logger.log(f"완료: 총 {result['total_services']}개 서비스, {result['total_pages']}개 페이지")
    return result
