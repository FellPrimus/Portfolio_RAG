"""
크롤러 통합 로깅 유틸리티

중복된 log 함수들을 통합하여 일관된 로깅을 제공합니다.
"""

from typing import Optional


class CrawlerLogger:
    """크롤러 로깅 클래스"""

    def __init__(self, prefix: str, verbose: bool = True):
        """
        Args:
            prefix: 로그 메시지 접두사
            verbose: 상세 로그 출력 여부
        """
        self.prefix = prefix
        self.verbose = verbose

    def log(self, msg: str) -> None:
        """일반 로그"""
        if self.verbose:
            print(f"[{self.prefix}] {msg}")

    def info(self, msg: str) -> None:
        """정보 로그"""
        if self.verbose:
            print(f"[{self.prefix}] INFO: {msg}")

    def warn(self, msg: str) -> None:
        """경고 로그"""
        print(f"[{self.prefix}] WARN: {msg}")

    def error(self, msg: str) -> None:
        """에러 로그"""
        print(f"[{self.prefix}] ERROR: {msg}")

    def debug(self, msg: str) -> None:
        """디버그 로그 (verbose일 때만)"""
        if self.verbose:
            print(f"[{self.prefix}] DEBUG: {msg}")

    def progress(self, current: int, total: int, item: str = "") -> None:
        """진행률 로그"""
        percent = (current / total * 100) if total > 0 else 0
        if item:
            print(f"[{self.prefix}] Progress: {current}/{total} ({percent:.1f}%) - {item}")
        else:
            print(f"[{self.prefix}] Progress: {current}/{total} ({percent:.1f}%)")


# 미리 정의된 로거 인스턴스
section_logger = CrawlerLogger("Section")
folder_logger = CrawlerLogger("Folder")
link_logger = CrawlerLogger("Link")
content_logger = CrawlerLogger("Content")
crawl_logger = CrawlerLogger("Crawl")


def create_logger(prefix: str, verbose: bool = True) -> CrawlerLogger:
    """로거 팩토리 함수"""
    return CrawlerLogger(prefix, verbose)
