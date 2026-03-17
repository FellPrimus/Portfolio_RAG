"""
폴더 확장 및 재귀 링크 수집 모듈

NCloud 문서 사이드바의 폴더를 확장하고
자식 요소들을 재귀적으로 수집합니다.
"""

from typing import List, Dict
from playwright.sync_api import Page

from src.loaders.crawler.utils import (
    extract_url_prefix,
    folder_logger
)


def expand_folder_and_get_children(
    page: Page,
    folder_selector: str,
    stop_at_folder: bool = False,
    service_name: str = None
) -> List[Dict]:
    """
    폴더를 확장하고 직접 자식 요소들의 정보 반환

    Args:
        page: Playwright Page 객체
        folder_selector: 폴더 요소의 CSS 셀렉터
        stop_at_folder: True면 다음 폴더(href="")를 만나면 즉시 중단
        service_name: 서비스 이름 (다른 서비스 폴더 감지용)

    Returns:
        List[Dict]: 자식 요소 정보 목록
    """
    try:
        # 먼저 폴더가 이미 확장되어 있는지 확인
        has_visible_children = page.evaluate('''
            (selector) => {
                const folder = document.querySelector(selector);
                if (!folder) return false;

                const arrowBtn = folder.querySelector('.tree-arrow');
                if (!arrowBtn) return false;

                const icon = arrowBtn.querySelector('i');
                if (icon) {
                    if (icon.classList.contains('fa-angle-down')) return true;
                    if (icon.classList.contains('fa-caret-down')) return true;
                    if (icon.classList.contains('fa-chevron-down')) return true;
                }

                if (arrowBtn.getAttribute('aria-expanded') === 'true') return true;
                return false;
            }
        ''', folder_selector)

        # 이미 확장된 경우 클릭하지 않음
        if not has_visible_children:
            expand_btn = page.locator(f"{folder_selector} .tree-arrow")
            if expand_btn.count() > 0:
                expand_btn.first.click()
                page.wait_for_timeout(800)

        # 자식 요소들 정보 수집
        children = page.evaluate('''
            (args) => {
                const selector = args.selector;
                const stopAtFolder = args.stopAtFolder;
                const serviceName = args.serviceName || '';
                const serviceNameLower = serviceName.toLowerCase().replace(/\\s/g, '');

                const folder = document.querySelector(selector);
                if (!folder) return [];

                const children = [];
                let sibling = folder.nextElementSibling;
                let foundFirstLink = false;

                while (sibling) {
                    let link = null;
                    if (sibling.tagName === 'A') {
                        link = sibling;
                    } else {
                        link = sibling.querySelector('a');
                    }

                    if (!link) {
                        sibling = sibling.nextElementSibling;
                        continue;
                    }

                    const href = link.getAttribute('href') || '';
                    const text = link.textContent.trim();
                    const textLower = text.toLowerCase().replace(/\\s/g, '');

                    let hasArrow = false;
                    if (sibling.tagName !== 'A') {
                        hasArrow = sibling.querySelector('.tree-arrow') !== null;
                    }

                    const isFolder = (href === '' || href === null) && hasArrow;

                    // 서비스 이름이 주어진 경우, 폴더 이름이 서비스와 다르면 중단
                    if (isFolder && serviceNameLower && !textLower.includes(serviceNameLower)) {
                        children.push({
                            id: sibling.id || null,
                            href: href,
                            text: text,
                            isFolder: isFolder,
                            hasArrow: hasArrow,
                            isDifferentService: true
                        });
                        break;
                    }

                    // stop_at_folder 모드: 링크를 하나라도 찾은 후 폴더를 만나면 중단
                    if (stopAtFolder && isFolder && foundFirstLink) {
                        children.push({
                            id: sibling.id || null,
                            href: href,
                            text: text,
                            isFolder: isFolder,
                            hasArrow: hasArrow
                        });
                        break;
                    }

                    children.push({
                        id: sibling.id || null,
                        href: href,
                        text: text,
                        isFolder: isFolder,
                        hasArrow: hasArrow
                    });

                    if (href.startsWith('/docs/')) {
                        foundFirstLink = true;
                    }

                    if (children.length >= 50) break;
                    sibling = sibling.nextElementSibling;
                }

                return children;
            }
        ''', {'selector': folder_selector, 'stopAtFolder': stop_at_folder, 'serviceName': service_name})

        return children

    except Exception as e:
        folder_logger.error(f"폴더 확장 중 오류: {str(e)}")
        return []


def collect_service_links_recursive(
    page: Page,
    service_prefix: str,
    collected_hrefs: set,
    collected_links: list,
    folder_selector: str = None,
    depth: int = 0,
    structure_collector=None,
    visited_folders: set = None
) -> bool:
    """
    재귀적으로 서비스 내 모든 링크 수집

    Args:
        page: Playwright Page 객체
        service_prefix: 현재 서비스의 URL prefix
        collected_hrefs: 수집된 href 집합
        collected_links: 수집된 링크 목록
        folder_selector: 현재 폴더 셀렉터 (None이면 루트)
        depth: 재귀 깊이
        structure_collector: NCloud 구조 수집기
        visited_folders: 이미 방문한 폴더 ID 집합

    Returns:
        bool: 계속 수집할지 여부
    """
    indent = "  " * (depth + 1)

    if visited_folders is None:
        visited_folders = set()

    if folder_selector:
        children = expand_folder_and_get_children(page, folder_selector)
    else:
        return True

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
                print(f"{indent}페이지 수집: {text}")

        # 폴더인 경우: 하위 폴더 vs 다른 서비스 판별
        elif is_folder and has_arrow and child_id:
            if child_id in visited_folders:
                print(f"{indent}하위 폴더 발견: {text} (이미 방문, 건너뛰기)")
                continue
            visited_folders.add(child_id)

            print(f"{indent}하위 폴더 발견: {text}")

            PLATFORM_FOLDERS = {'VPC', 'Classic'}
            is_platform_folder = text in PLATFORM_FOLDERS

            # 구조 수집기로 카테고리/서비스 판단
            if structure_collector and not is_platform_folder:
                if structure_collector.is_category(text):
                    print(f"{indent}  -> 다른 카테고리 폴더 '{text}' 건너뛰기")
                    continue

                if structure_collector.is_other_service(text, service_prefix):
                    print(f"{indent}  -> 다른 서비스 폴더 '{text}' 건너뛰기 (현재: {service_prefix})")
                    continue

            selector = f"#{child_id}"
            sub_children = expand_folder_and_get_children(page, selector, stop_at_folder=True)

            child_doc_links = [c['href'] for c in sub_children if c.get('href', '').startswith('/docs/')]

            if child_doc_links:
                child_prefixes = [extract_url_prefix(link) for link in child_doc_links]
                matching_count = sum(1 for p in child_prefixes if p == service_prefix)

                is_platform_folder_name = text in PLATFORM_FOLDERS

                if is_platform_folder_name:
                    has_related_content = matching_count > 0
                    if not has_related_content:
                        child_texts = [c.get('text', '').lower() for c in sub_children]
                        service_keywords = service_prefix.lower().replace('-', ' ')
                        has_related_content = any(service_keywords in t or service_prefix in t for t in child_texts)

                    if has_related_content:
                        print(f"{indent}  -> 플랫폼 폴더 감지: {text}, 수집 진행")
                    else:
                        print(f"{indent}  -> 다른 서비스의 플랫폼 폴더: {text}, 건너뛰기")
                        continue
                else:
                    folder_is_other_service = False
                    if structure_collector:
                        folder_is_other_service = structure_collector.is_other_service(text, service_prefix)

                    if folder_is_other_service:
                        print(f"{indent}  -> 다른 서비스 폴더 감지됨: {text}, 건너뛰기")
                        continue

                    if matching_count == 0 and len(child_prefixes) > 0:
                        print(f"{indent}  -> prefix 불일치 폴더 건너뛰기: {text} (0/{len(child_prefixes)})")
                        continue

                print(f"{indent}  -> 하위 폴더 수집 (prefix 매칭: {matching_count}/{len(child_prefixes)})")

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
                            print(f"{indent}  페이지 수집: {sub_text}")

                    elif sub_is_folder and sub_has_arrow and sub_id:
                        if not collect_service_links_recursive(
                            page, service_prefix, collected_hrefs, collected_links,
                            f"#{sub_id}", depth + 1, structure_collector, visited_folders
                        ):
                            continue
            else:
                child_folders = [c for c in sub_children
                                if c.get('isFolder') and c.get('hasArrow') and c.get('id')]

                if child_folders:
                    print(f"{indent}  -> 자식 링크 없음, 하위 폴더 {len(child_folders)}개 재귀 수집")
                    for sub_folder in child_folders:
                        sub_folder_id = sub_folder.get('id')
                        sub_folder_text = sub_folder.get('text', '')

                        if structure_collector:
                            if structure_collector.is_category(sub_folder_text):
                                print(f"{indent}    -> 다른 카테고리 '{sub_folder_text}' 건너뛰기")
                                continue

                            if structure_collector.is_other_service(sub_folder_text, service_prefix):
                                print(f"{indent}    -> 다른 서비스 '{sub_folder_text}' 건너뛰기")
                                continue

                        collect_service_links_recursive(
                            page, service_prefix, collected_hrefs, collected_links,
                            f"#{sub_folder_id}", depth + 1, structure_collector, visited_folders
                        )
                else:
                    print(f"{indent}  -> 자식 링크/폴더 없음, 건너뛰기")
                    continue

    return True
