"""
URL 처리 유틸리티

URL 파싱, 변환 등을 담당합니다.
"""

from typing import List
from urllib.parse import urlparse
from collections import Counter


def get_base_url(url: str) -> str:
    """URL에서 base URL 추출 (scheme + netloc)"""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def get_service_name_from_url(url: str) -> str:
    """URL에서 서비스명 추출"""
    try:
        path = url.split('/')[-1]
        service_name = path.replace('-', ' ').replace(' ', '_')
        return service_name
    except:
        return "unknown_service"


def extract_url_prefix(url_path: str) -> str:
    """
    URL 경로에서 서비스 prefix 추출

    예시:
    - /docs/sourceband-overview → sourceband
    - /docs/securitymonitoring-start-vpc → securitymonitoring
    """
    try:
        if '/docs/' in url_path:
            doc_path = url_path.split('/docs/')[-1]
        else:
            doc_path = url_path.split('/')[-1]

        if '-' in doc_path:
            return doc_path.split('-')[0].lower()
        return doc_path.lower()
    except:
        return ""


def get_majority_prefix(urls: List[str]) -> str:
    """
    URL 목록에서 가장 많이 등장하는 prefix 반환 (다수결)

    Args:
        urls: URL 경로 목록

    Returns:
        가장 빈번한 prefix
    """
    prefixes = [extract_url_prefix(url) for url in urls if url]
    prefixes = [p for p in prefixes if p]

    if not prefixes:
        return ""

    counter = Counter(prefixes)
    most_common = counter.most_common(1)
    return most_common[0][0] if most_common else ""


def is_valid_doc_url(href: str) -> bool:
    """유효한 문서 URL인지 확인"""
    if not href:
        return False
    return href.startswith('/docs/') or href.startswith('http')


def normalize_url(href: str, base_url: str) -> str:
    """상대 URL을 절대 URL로 변환"""
    if not href:
        return ""
    if href.startswith('http'):
        return href
    return base_url + href
