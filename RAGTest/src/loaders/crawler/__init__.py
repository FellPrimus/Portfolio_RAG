"""
크롤러 패키지

Playwright 기반 웹 크롤러 모듈을 제공합니다.
"""

from .crawlers import PlaywrightCrawler, GenericWebCrawler

# 편의를 위해 주요 함수들도 노출
from .navigation import (
    get_section_links,
    get_menu_links,
    get_all_services,
    crawl_all_services
)

from .utils import (
    clean_text,
    convert_table_to_markdown,
    convert_list_to_markdown,
    extract_section_content,
    get_base_url,
    get_service_name_from_url,
    extract_url_prefix,
    normalize_url
)

__all__ = [
    # 크롤러 클래스
    'PlaywrightCrawler',
    'GenericWebCrawler',
    # 네비게이션 함수
    'get_section_links',
    'get_menu_links',
    'get_all_services',
    'crawl_all_services',
    # 유틸리티 함수
    'clean_text',
    'convert_table_to_markdown',
    'convert_list_to_markdown',
    'extract_section_content',
    'get_base_url',
    'get_service_name_from_url',
    'extract_url_prefix',
    'normalize_url'
]
