"""
Playwright 기반 웹 크롤러

네이버 클라우드 플랫폼 문서 등 동적 웹페이지를 크롤링하여
RAG 시스템에 통합합니다.

Note:
    이 파일은 backward compatibility를 위한 파사드입니다.
    실제 구현은 src/loaders/crawler/ 패키지에 있습니다.
"""

# =============================================================================
# 유틸리티 함수 재노출 (backward compatibility)
# =============================================================================

from src.loaders.crawler.utils import (
    clean_text,
    convert_table_to_markdown,
    convert_list_to_markdown,
    extract_section_content,
    get_base_url,
    get_service_name_from_url,
    extract_url_prefix,
    get_majority_prefix
)

# =============================================================================
# 네비게이션 함수 재노출 (backward compatibility)
# =============================================================================

from src.loaders.crawler.navigation import (
    get_menu_links,
    expand_folder_and_get_children,
    collect_service_links_recursive,
    get_section_links,
    expand_section_submenus,
    get_all_services,
    crawl_all_services
)

# =============================================================================
# 크롤러 클래스 재노출 (backward compatibility)
# =============================================================================

from src.loaders.crawler.crawlers import (
    PlaywrightCrawler,
    GenericWebCrawler
)

# =============================================================================
# __all__ 정의
# =============================================================================

__all__ = [
    # 유틸리티 함수
    'clean_text',
    'convert_table_to_markdown',
    'convert_list_to_markdown',
    'extract_section_content',
    'get_base_url',
    'get_service_name_from_url',
    'extract_url_prefix',
    'get_majority_prefix',
    # 네비게이션 함수
    'get_menu_links',
    'expand_folder_and_get_children',
    'collect_service_links_recursive',
    'get_section_links',
    'expand_section_submenus',
    'get_all_services',
    'crawl_all_services',
    # 크롤러 클래스
    'PlaywrightCrawler',
    'GenericWebCrawler'
]
