"""
통합 로깅 설정

일관된 로그 포맷과 핸들러 관리
"""
import logging
import sys
from pathlib import Path
from typing import Optional
from src.config.constants import LOG_FORMAT, LOG_DATE_FORMAT


def setup_logging(
    log_level: int = logging.INFO,
    log_file: Optional[str] = "app.log",
    enable_console: bool = True
) -> logging.Logger:
    """
    애플리케이션 로깅 설정

    Args:
        log_level: 로그 레벨 (logging.INFO, logging.DEBUG 등)
        log_file: 로그 파일 경로 (None이면 파일 로깅 비활성화)
        enable_console: 콘솔 출력 활성화 여부

    Returns:
        설정된 루트 로거
    """
    # 루트 로거 가져오기
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 기존 핸들러 제거 (중복 방지)
    root_logger.handlers.clear()

    # 포맷터 생성
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 파일 핸들러
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # 콘솔 핸들러
    if enable_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거 가져오기

    Args:
        name: 로거 이름 (보통 __name__ 사용)

    Returns:
        설정된 로거 인스턴스

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("문서 로드 시작")
    """
    return logging.getLogger(name)


class LoggerMixin:
    """
    로깅 기능을 클래스에 추가하는 믹스인

    Example:
        class MyService(LoggerMixin):
            def process(self):
                self.logger.info("처리 시작")
    """

    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
