"""
메뉴 링크 수집 모듈

좌측 사이드바 메뉴에서 링크를 수집합니다.
"""

from typing import List, Dict
from playwright.sync_api import Page

from src.loaders.crawler.utils import link_logger


def get_menu_links(page: Page, base_url: str) -> List[Dict[str, str]]:
    """
    좌측 메뉴의 모든 링크를 수집

    Args:
        page: Playwright Page 객체
        base_url: 기본 URL (scheme + host)

    Returns:
        List[Dict]: [{'url': 'full_url', 'text': '메뉴명', 'serviceName': '서비스명'}, ...]
    """
    try:
        links = page.evaluate('''
            () => {
                const links = [];
                let serviceName = '';

                const sidebar = document.querySelector('[role="complementary"]') ||
                               document.querySelector('.left-panel') ||
                               document.querySelector('aside') ||
                               document.querySelector('nav');

                if (!sidebar) return { links: [], serviceName: '' };

                const menuItems = sidebar.querySelectorAll('a[href]');
                menuItems.forEach(item => {
                    const href = item.getAttribute('href');
                    const text = item.textContent.trim();
                    if (href && href.startsWith('/docs/') && text && text !== 'HOME') {
                        links.push({
                            href,
                            text,
                            serviceName
                        });
                    }
                });
                return { links, serviceName };
            }
        ''')

        full_links = []
        for link in links['links']:
            if not link['href'].startswith('http'):
                full_url = base_url + link['href']
            else:
                full_url = link['href']
            full_links.append({
                'url': full_url,
                'text': link['text'],
                'serviceName': links['serviceName']
            })

        return full_links

    except Exception as e:
        link_logger.error(f"메뉴 링크 수집 중 오류: {str(e)}")
        return []
