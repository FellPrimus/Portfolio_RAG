"""
LLM 선택 유틸리티

문서 카테고리 및 보안 모드에 따라 적절한 LLM을 선택합니다.
"""

import os
from typing import Tuple, Set, Any

from src.utils import get_llm
from src.config.settings import get_settings


class LLMSelector:
    """카테고리 기반 LLM 선택기"""

    def __init__(self, default_llm=None):
        """
        Args:
            default_llm: 기본 LLM 인스턴스
        """
        self.settings = get_settings()
        self.default_llm = default_llm

    def select_for_categories(
        self,
        categories: list,
        secure_mode: bool = False
    ) -> Tuple[Any, str, str]:
        """
        검색된 문서의 카테고리에 따라 적절한 LLM 모델을 선택

        규칙:
        1. 보안 모드 활성화 시 -> 무조건 secure_model
        2. 일반(general) 또는 기술 스펙(spec) 포함 -> secure_model
        3. API 또는 가이드만 있는 경우 -> default_model
        4. 그 외 -> secure_model

        Args:
            categories: 검색된 문서들의 카테고리 ID 리스트
            secure_mode: 보안 모드 활성화 여부

        Returns:
            (llm_instance, model_name, selection_reason)
        """
        unique_categories = set(categories)

        secure_model = self.settings.llm.secure_model_name
        default_model = os.getenv("MODEL_NAME", self.settings.llm.default_model_name)

        # 보안 모드 활성화 시 무조건 secure_model 사용
        if secure_mode:
            return self._create_secure_llm(secure_model, f"[SECURE] Secure mode -> {secure_model}")

        # 카테고리가 없으면 기본 모델
        if not unique_categories:
            return (
                self.default_llm,
                default_model,
                f"No documents - using default model ({default_model})"
            )

        # 일반(general) 또는 기술 스펙(spec) 포함 -> secure_model
        if 'general' in unique_categories or 'spec' in unique_categories:
            categories_str = ', '.join(sorted(unique_categories))
            return self._create_secure_llm(
                secure_model,
                f"general/spec included({categories_str}) -> {secure_model}"
            )

        # API 또는 가이드만 있는 경우 -> default_model
        if 'api' in unique_categories or 'guide' in unique_categories:
            categories_str = ', '.join(sorted(unique_categories))
            return self._create_default_llm(
                default_model,
                f"API/guide only({categories_str}) -> {default_model}"
            )

        # 그 외 모든 경우 -> secure_model
        categories_str = ', '.join(sorted(unique_categories))
        return self._create_secure_llm(
            secure_model,
            f"Other categories({categories_str}) -> {secure_model}"
        )

    def _create_secure_llm(self, model_name: str, reason: str) -> Tuple[Any, str, str]:
        """보안 모델 LLM 생성"""
        model_config = {
            "provider": "openai",
            "model_name": model_name,
            "temperature": 0.2,
            "base_url": "https://namc-aigw.io.naver.com",
            "api_key": "sk-sx1_aC1JFoGH5DHbhHMByA"
        }
        llm = get_llm(model_config=model_config)
        return (llm, model_name, reason)

    def _create_default_llm(self, model_name: str, reason: str) -> Tuple[Any, str, str]:
        """기본 모델 LLM 생성"""
        model_config = {
            "provider": "openai",
            "model_name": model_name,
            "temperature": 0.2,
            "base_url": os.getenv("OPENAI_BASE_URL", "https://aac-api.navercorp.com/v1")
        }
        llm = get_llm(model_config=model_config)
        return (llm, model_name, reason)
