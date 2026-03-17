"""
공통 유틸리티 함수

재사용 가능한 헬퍼 함수들
"""
import os
import hashlib
from typing import Optional, List
from pathlib import Path

from src.config.settings import get_settings
from src.config.constants import SUPPORTED_EXTENSIONS


def get_file_hash(file_path: str) -> str:
    """
    파일의 MD5 해시 생성

    Args:
        file_path: 파일 경로

    Returns:
        MD5 해시 문자열
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()[:8]


def is_supported_file(filename: str) -> bool:
    """
    지원되는 파일 형식인지 확인

    Args:
        filename: 파일명

    Returns:
        지원 여부
    """
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def get_file_extension(filename: str) -> str:
    """파일 확장자 추출 (소문자)"""
    return os.path.splitext(filename)[1].lower()


def ensure_directory(path: str) -> Path:
    """
    디렉토리 존재 확인 및 생성

    Args:
        path: 디렉토리 경로

    Returns:
        Path 객체
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def safe_filename(filename: str) -> str:
    """
    안전한 파일명으로 변환

    특수문자 제거 및 공백 처리
    """
    import re
    # 허용: 알파벳, 숫자, 한글, 밑줄, 하이픈, 마침표
    safe = re.sub(r'[^\w\s가-힣.-]', '', filename)
    safe = safe.replace(' ', '_')
    return safe


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    텍스트를 최대 길이로 자르기

    Args:
        text: 원본 텍스트
        max_length: 최대 길이
        suffix: 잘릴 때 추가할 접미사

    Returns:
        잘린 텍스트
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """
    텍스트 정리

    - 연속 공백 제거
    - 앞뒤 공백 제거
    """
    import re
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
