"""크롤러 유틸리티 모듈"""

from .crawler_logger import (
    CrawlerLogger,
    create_logger,
    section_logger,
    folder_logger,
    link_logger,
    content_logger,
    crawl_logger
)

from .text_utils import (
    clean_text,
    convert_table_to_markdown,
    convert_list_to_markdown,
    extract_section_content
)

from .url_utils import (
    get_base_url,
    get_service_name_from_url,
    extract_url_prefix,
    get_majority_prefix,
    is_valid_doc_url,
    normalize_url
)

__all__ = [
    # Logger
    'CrawlerLogger',
    'create_logger',
    'section_logger',
    'folder_logger',
    'link_logger',
    'content_logger',
    'crawl_logger',
    # Text utils
    'clean_text',
    'convert_table_to_markdown',
    'convert_list_to_markdown',
    'extract_section_content',
    # URL utils
    'get_base_url',
    'get_service_name_from_url',
    'extract_url_prefix',
    'get_majority_prefix',
    'is_valid_doc_url',
    'normalize_url'
]
