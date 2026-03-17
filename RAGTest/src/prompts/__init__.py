"""
할루시네이션 방지 시스템 프롬프트 모듈
"""

from .system_prompts import (
    get_system_prompt,
    STRICT_PROMPT,
    BALANCED_PROMPT,
    FEW_SHOT_PROMPT
)

__all__ = [
    'get_system_prompt',
    'STRICT_PROMPT',
    'BALANCED_PROMPT',
    'FEW_SHOT_PROMPT'
]
