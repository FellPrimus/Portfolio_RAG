"""
섹션 네비게이션 모듈

현재 페이지가 속한 섹션의 링크들을 수집합니다.
"""

from typing import List, Dict
from urllib.parse import urlparse
from playwright.sync_api import Page

from src.loaders.crawler.utils import (
    extract_url_prefix,
    section_logger
)
from .folder_expander import (
    expand_folder_and_get_children,
    collect_service_links_recursive
)


def get_section_links(
    page: Page,
    base_url: str,
    current_url: str,
    structure_collector=None
) -> List[Dict[str, str]]:
    """
    현재 페이지가 속한 섹션의 링크만 수집 (하이브리드 알고리즘)

    알고리즘:
    1. 현재 페이지에서 서비스 헤더(href="") 찾기
    2. 직접 링크들 수집하며 다수 URL prefix 파악
    3. href="" 폴더 발견 시 확장하여 자식 URL prefix 확인

    Args:
        page: Playwright Page 객체
        base_url: 기본 URL (scheme + host)
        current_url: 현재 페이지 URL
        structure_collector: NCloud 구조 수집기

    Returns:
        List[Dict]: 해당 섹션 내의 링크 목록
    """
    try:
        current_path = urlparse(current_url).path
        section_logger.log(f"시작 URL: {current_path}")

        # 1단계: 서비스 헤더 찾기 및 초기 정보 수집
        initial_info = page.evaluate('''
            (currentPath) => {
                const pathEnd = currentPath.split('/').pop();

                const sidebar = document.querySelector('[role="complementary"]') ||
                               document.querySelector('.left-panel') ||
                               document.querySelector('aside');

                let currentLink = null;
                if (sidebar) {
                    currentLink = sidebar.querySelector(`a[href="${currentPath}"]`) ||
                                 sidebar.querySelector(`a[href*="${pathEnd}"]`);
                }

                if (!currentLink) {
                    const nodeElements = document.querySelectorAll('[id^="node-"]');
                    for (const node of nodeElements) {
                        const link = node.querySelector(`a[href="${currentPath}"]`) ||
                                    node.querySelector(`a[href*="${pathEnd}"]`);
                        if (link) {
                            currentLink = link;
                            break;
                        }
                    }
                }

                if (!currentLink) {
                    currentLink = document.querySelector(`a[href="${currentPath}"]`) ||
                                  document.querySelector(`a[href*="${pathEnd}"]`);
                }

                if (!currentLink) return { error: 'current link not found' };

                let sectionHeader = null;
                let sectionHeaderId = null;
                let serviceName = '';

                let parent = currentLink.parentElement;

                while (parent && parent.tagName !== 'BODY') {
                    let prevSibling = parent.previousElementSibling;
                    while (prevSibling) {
                        const sectionLink = prevSibling.querySelector('a');
                        if (sectionLink) {
                            const href = sectionLink.getAttribute('href');
                            if (href === '' || href === null) {
                                const hasArrow = prevSibling.querySelector('.tree-arrow, [role="button"]');
                                if (hasArrow) {
                                    sectionHeader = prevSibling;
                                    sectionHeaderId = prevSibling.id || null;
                                    serviceName = sectionLink.textContent.trim();
                                    break;
                                }
                            }
                        }
                        prevSibling = prevSibling.previousElementSibling;
                    }
                    if (sectionHeader) break;
                    parent = parent.parentElement;
                }

                if (!sectionHeader) {
                    return { error: 'section header not found' };
                }

                let debugSiblings = [];
                let nextSib = sectionHeader.nextElementSibling;
                for (let i = 0; i < 5 && nextSib; i++) {
                    const sibLink = nextSib.tagName === 'A' ? nextSib : nextSib.querySelector('a');
                    debugSiblings.push({
                        tag: nextSib.tagName,
                        id: nextSib.id || 'no-id',
                        linkHref: sibLink ? sibLink.getAttribute('href') : 'no-link',
                        linkText: sibLink ? sibLink.textContent.trim().substring(0, 20) : 'no-text'
                    });
                    nextSib = nextSib.nextElementSibling;
                }

                return {
                    serviceName,
                    sectionHeaderId,
                    currentPath,
                    headerTagName: sectionHeader.tagName,
                    debugSiblings
                };
            }
        ''', current_path)

        if 'error' in initial_info:
            section_logger.error(f"오류: {initial_info['error']}")
            return []

        service_name = initial_info.get('serviceName', '')
        section_header_id = initial_info.get('sectionHeaderId', '')
        section_logger.info(f"서비스명: {service_name}")
        section_logger.debug(f"헤더 ID: {section_header_id}")

        # 2단계: 서비스 prefix 결정
        service_prefix = extract_url_prefix(current_path)
        section_logger.info(f"서비스 prefix: {service_prefix}")

        # 3단계: 서비스 헤더부터 링크 수집 (재귀적)
        collected_links = []
        collected_hrefs = set()
        visited_folders = set()

        if section_header_id:
            selector = f"#{section_header_id}"

            children = expand_folder_and_get_children(page, selector, service_name=service_name)
            section_logger.info(f"서비스 헤더 하위 요소 수: {len(children)}")

            for child in children:
                child_id = child.get('id')
                href = child.get('href')
                text = child.get('text', '')
                is_folder = child.get('isFolder', False)
                has_arrow = child.get('hasArrow', False)

                # 일반 /docs/ 링크: 수집
                if href and href.startswith('/docs/'):
                    if href not in collected_hrefs:
                        collected_hrefs.add(href)
                        collected_links.append({'href': href, 'text': text})
                        section_logger.debug(f"페이지 수집: {text}")

                # 폴더인 경우
                elif is_folder and has_arrow and child_id:
                    section_logger.debug(f"폴더 발견: {text}")

                    # 카테고리 폴더면 수집 중단
                    if structure_collector and structure_collector.is_category(text):
                        section_logger.info(f"다른 카테고리 '{text}' 감지, 수집 중단")
                        break

                    PLATFORM_FOLDERS = {'VPC', 'Classic'}
                    is_platform_folder = text in PLATFORM_FOLDERS

                    folder_selector = f"#{child_id}"

                    sub_children = expand_folder_and_get_children(
                        page, folder_selector,
                        stop_at_folder=not is_platform_folder,
                        service_name=service_name
                    )

                    child_doc_links = [c['href'] for c in sub_children
                                      if c.get('href', '').startswith('/docs/')]

                    if child_doc_links:
                        child_prefixes = [extract_url_prefix(link) for link in child_doc_links]
                        matching_count = sum(1 for p in child_prefixes if p == service_prefix)

                        if is_platform_folder:
                            has_related_content = matching_count > 0
                            if not has_related_content:
                                child_texts = [c.get('text', '').lower() for c in sub_children]
                                service_keywords = service_prefix.lower().replace('-', ' ')
                                has_related_content = any(service_keywords in t or service_prefix in t for t in child_texts)

                            if not has_related_content:
                                section_logger.debug(f"다른 서비스의 플랫폼 폴더: {text}, 건너뛰기")
                                continue
                        else:
                            folder_is_other_service = False
                            if structure_collector:
                                folder_is_other_service = structure_collector.is_other_service(text, service_prefix)

                            if folder_is_other_service:
                                section_logger.debug(f"다른 서비스 폴더 감지됨: {text}, 건너뛰기")
                                continue

                            if matching_count == 0 and len(child_prefixes) > 0:
                                section_logger.debug(f"prefix 불일치 폴더 건너뛰기: {text}")
                                continue

                        # 하위 폴더 내용 재귀적으로 수집
                        for sub_child in sub_children:
                            sub_href = sub_child.get('href')
                            sub_text = sub_child.get('text', '')
                            sub_is_folder = sub_child.get('isFolder', False)
                            sub_has_arrow = sub_child.get('hasArrow', False)
                            sub_id = sub_child.get('id')

                            if sub_href and sub_href.startswith('/docs/'):
                                if sub_href not in collected_hrefs:
                                    collected_hrefs.add(sub_href)
                                    collected_links.append({'href': sub_href, 'text': sub_text})

                            elif sub_is_folder and sub_has_arrow and sub_id:
                                collect_service_links_recursive(
                                    page, service_prefix, collected_hrefs, collected_links,
                                    f"#{sub_id}", depth=2, structure_collector=structure_collector,
                                    visited_folders=visited_folders
                                )
                    else:
                        child_folders = [c for c in sub_children
                                        if c.get('isFolder') and c.get('hasArrow') and c.get('id')]

                        if child_folders:
                            for sub_folder in child_folders:
                                sub_folder_id = sub_folder.get('id')
                                collect_service_links_recursive(
                                    page, service_prefix, collected_hrefs, collected_links,
                                    f"#{sub_folder_id}", depth=2, structure_collector=structure_collector,
                                    visited_folders=visited_folders
                                )

        section_logger.log(f"총 수집된 링크 수: {len(collected_links)}")

        # 전체 URL로 변환
        full_links = []
        for link in collected_links:
            href = link['href']
            full_url = base_url + href if not href.startswith('http') else href
            full_links.append({
                'url': full_url,
                'text': link['text'],
                'serviceName': service_name
            })

        return full_links

    except Exception as e:
        section_logger.error(f"섹션 링크 수집 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def expand_section_submenus(page: Page, current_path: str):
    """
    현재 섹션 내의 접힌 하위 메뉴만 펼치기

    Args:
        page: Playwright Page 객체
        current_path: 현재 페이지 경로
    """
    try:
        button_selectors = page.evaluate('''
            (currentPath) => {
                const selectors = [];
                const pathEnd = currentPath.split('/').pop();

                let currentLink = document.querySelector(`a[href="${currentPath}"]`) ||
                                  document.querySelector(`a[href*="${pathEnd}"]`);

                if (!currentLink) return selectors;

                let sectionHeader = null;
                let parent = currentLink.parentElement;

                while (parent && parent.tagName !== 'BODY') {
                    let prevSibling = parent.previousElementSibling;
                    while (prevSibling) {
                        const sectionLink = prevSibling.querySelector('a');
                        if (sectionLink) {
                            const href = sectionLink.getAttribute('href');
                            if (href === '' || href === null) {
                                const hasArrow = prevSibling.querySelector('.tree-arrow, [role="button"]');
                                if (hasArrow) {
                                    sectionHeader = prevSibling;
                                    break;
                                }
                            }
                        }
                        prevSibling = prevSibling.previousElementSibling;
                    }
                    if (sectionHeader) break;
                    parent = parent.parentElement;
                }

                if (!sectionHeader) return selectors;

                let sibling = sectionHeader.nextElementSibling;
                while (sibling) {
                    const siblingLink = sibling.querySelector('a');
                    const linkHref = siblingLink ? siblingLink.getAttribute('href') : '';

                    const expandBtn = sibling.querySelector('.tree-arrow[role="button"], .tree-arrow');
                    if (expandBtn && sibling.id) {
                        selectors.push(`#${sibling.id} .tree-arrow[role="button"], #${sibling.id} .tree-arrow`);
                    }

                    sibling = sibling.nextElementSibling;
                }
                return selectors;
            }
        ''', current_path)

        section_logger.debug(f"펼칠 하위 메뉴 버튼: {len(button_selectors)}개")

        for selector in button_selectors:
            try:
                button = page.locator(selector)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(300)
            except Exception as e:
                section_logger.warn(f"버튼 클릭 실패: {selector} - {str(e)}")

        page.wait_for_timeout(500)

    except Exception as e:
        section_logger.error(f"하위 메뉴 펼치기 중 오류: {str(e)}")
