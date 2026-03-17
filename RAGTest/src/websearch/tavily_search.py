"""
Tavily 웹 검색 서비스

벡터DB 답변의 교차 검증을 위한 웹 검색 기능 제공
보안을 위해 쿼리 익명화 기능 포함
"""

import re
import logging
from typing import List, Dict, Optional, Any

from tavily import TavilyClient

logger = logging.getLogger(__name__)


# 쿼리 익명화 규칙 - 내부 정보 유출 방지
ANONYMIZATION_RULES = [
    # 내부 시스템/회사 관련 표현 제거
    (r'우리\s*회사|사내|내부\s*시스템|자사', ''),
    (r'우리\s*팀|우리\s*부서', ''),

    # 이메일 마스킹
    (r'\b[\w.-]+@[\w.-]+\.\w+\b', '[EMAIL]'),

    # 전화번호 마스킹 (한국 형식)
    (r'\b\d{2,3}[-.]?\d{3,4}[-.]?\d{4}\b', '[PHONE]'),

    # 내부 IP 주소 마스킹 (10.x.x.x, 192.168.x.x, 172.16-31.x.x)
    (r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[INTERNAL_IP]'),
    (r'\b192\.168\.\d{1,3}\.\d{1,3}\b', '[INTERNAL_IP]'),
    (r'\b172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}\b', '[INTERNAL_IP]'),

    # 주민등록번호 패턴 마스킹
    (r'\b\d{6}[-]?\d{7}\b', '[PII]'),

    # 사원번호/직원 ID 패턴 (숫자로 시작하는 5-8자리)
    (r'\b[A-Za-z]?\d{5,8}\b', ''),

    # 내부 URL 패턴 마스킹
    (r'https?://[a-z0-9.-]*\.(internal|local|corp|intra)[a-z0-9./-]*', '[INTERNAL_URL]'),

    # 중복 공백 정리
    (r'\s+', ' '),
]


class TavilySearchService:
    """
    Tavily API를 이용한 웹 검색 서비스

    벡터DB 답변의 교차 검증을 위해 웹 검색을 수행합니다.
    보안을 위해 쿼리 익명화 기능을 제공합니다.
    """

    def __init__(self, api_key: str, settings: Optional[Any] = None):
        """
        TavilySearchService 초기화

        Args:
            api_key: Tavily API Key
            settings: WebSearchSettings 인스턴스 (선택)
        """
        if not api_key:
            raise ValueError("Tavily API Key가 필요합니다. WEB_SEARCH_API_KEY 환경변수를 설정하세요.")

        self.client = TavilyClient(api_key=api_key)
        self.settings = settings

        # 설정값 또는 기본값 사용
        self.max_results = getattr(settings, 'max_results', 3) if settings else 3
        self.search_depth = getattr(settings, 'search_depth', 'basic') if settings else 'basic'
        self.anonymize_enabled = getattr(settings, 'anonymize_query', True) if settings else True
        self.include_domains = getattr(settings, 'include_domains', []) if settings else []
        self.exclude_domains = getattr(settings, 'exclude_domains', []) if settings else []

        logger.info(
            f"TavilySearchService 초기화 완료 - "
            f"max_results={self.max_results}, search_depth={self.search_depth}, "
            f"anonymize={self.anonymize_enabled}"
        )

    def anonymize_query(self, query: str) -> str:
        """
        쿼리 익명화 - 내부 정보 유출 방지

        내부 시스템명, 이메일, 전화번호, IP 주소 등을 마스킹합니다.

        Args:
            query: 원본 검색 쿼리

        Returns:
            익명화된 검색 쿼리
        """
        anonymized = query

        for pattern, replacement in ANONYMIZATION_RULES:
            anonymized = re.sub(pattern, replacement, anonymized, flags=re.IGNORECASE)

        # 마스킹된 플레이스홀더 제거 (검색에 불필요)
        anonymized = re.sub(r'\[(EMAIL|PHONE|INTERNAL_IP|PII|INTERNAL_URL)\]', '', anonymized)

        # 앞뒤 공백 및 중복 공백 정리
        anonymized = ' '.join(anonymized.split()).strip()

        if anonymized != query:
            logger.debug(f"쿼리 익명화: '{query[:50]}...' → '{anonymized[:50]}...'")

        return anonymized

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        웹 검색 실행

        Args:
            query: 검색 쿼리

        Returns:
            검색 결과 리스트 - 각 항목에 title, url, content, score 포함
        """
        if not query or not query.strip():
            logger.warning("빈 쿼리로 검색 시도됨")
            return []

        # 쿼리 익명화 (설정에 따라)
        search_query = self.anonymize_query(query) if self.anonymize_enabled else query

        if not search_query.strip():
            logger.warning("익명화 후 쿼리가 비어있음")
            return []

        try:
            logger.info(f"Tavily 검색 시작: '{search_query[:100]}...'")

            # Tavily 검색 실행
            search_params = {
                "query": search_query,
                "search_depth": self.search_depth,
                "max_results": self.max_results,
            }

            # 도메인 필터 적용
            if self.include_domains:
                search_params["include_domains"] = self.include_domains
            if self.exclude_domains:
                search_params["exclude_domains"] = self.exclude_domains

            response = self.client.search(**search_params)

            # 결과 정규화
            results = self._normalize_results(response)

            logger.info(f"Tavily 검색 완료: {len(results)}개 결과")
            return results

        except Exception as e:
            logger.error(f"Tavily 검색 실패: {str(e)}")
            return []

    def _normalize_results(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tavily 응답을 정규화된 형식으로 변환

        Args:
            response: Tavily API 응답

        Returns:
            정규화된 검색 결과 리스트
        """
        results = []

        raw_results = response.get('results', [])

        for item in raw_results:
            normalized = {
                'title': item.get('title', ''),
                'url': item.get('url', ''),
                'content': item.get('content', ''),
                'score': item.get('score', 0.0),
                'raw_content': item.get('raw_content', ''),
            }
            results.append(normalized)

        return results

    def search_with_context(self, query: str, context: str = "") -> List[Dict[str, Any]]:
        """
        컨텍스트를 포함한 웹 검색

        RAG 답변과 관련된 추가 컨텍스트를 검색 쿼리에 포함시킵니다.

        Args:
            query: 원본 질문
            context: 추가 컨텍스트 (예: RAG 답변의 키워드)

        Returns:
            검색 결과 리스트
        """
        # 컨텍스트가 있으면 검색 쿼리 보강
        if context:
            enhanced_query = f"{query} {context}"
        else:
            enhanced_query = query

        return self.search(enhanced_query)

    def is_available(self) -> bool:
        """
        서비스 사용 가능 여부 확인

        Returns:
            API가 정상 작동하면 True
        """
        try:
            # 간단한 테스트 검색
            test_response = self.client.search(
                query="test",
                max_results=1,
                search_depth="basic"
            )
            return 'results' in test_response
        except Exception as e:
            logger.warning(f"Tavily API 상태 확인 실패: {str(e)}")
            return False


def create_tavily_service(settings: Optional[Any] = None) -> Optional[TavilySearchService]:
    """
    TavilySearchService 팩토리 함수

    설정에서 API 키를 가져와 서비스 인스턴스를 생성합니다.

    Args:
        settings: WebSearchSettings 인스턴스

    Returns:
        TavilySearchService 인스턴스 또는 None (API 키 없음)
    """
    import os

    # 설정에서 API 키 가져오기
    api_key = None

    if settings:
        api_key = getattr(settings, 'api_key', None)

    # 환경변수에서 API 키 가져오기 (fallback)
    if not api_key:
        api_key = os.environ.get('TAVILY_API_KEY') or os.environ.get('WEB_SEARCH_API_KEY')

    if not api_key:
        logger.warning("Tavily API Key가 설정되지 않았습니다.")
        return None

    try:
        return TavilySearchService(api_key=api_key, settings=settings)
    except Exception as e:
        logger.error(f"TavilySearchService 생성 실패: {str(e)}")
        return None
