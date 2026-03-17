"""
커스텀 예외 클래스 정의

구체적이고 명확한 예외 처리를 위한 계층 구조
"""
from typing import Optional, Dict, Any


class RAGBaseException(Exception):
    """RAG 시스템 기본 예외"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.original_error = original_error

    def to_dict(self) -> Dict[str, Any]:
        """예외 정보를 딕셔너리로 변환"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details
        }


# ============ 문서 관련 예외 ============

class DocumentException(RAGBaseException):
    """문서 처리 관련 기본 예외"""
    pass


class DocumentNotFoundException(DocumentException):
    """문서를 찾을 수 없을 때"""

    def __init__(self, filename: str, collection: Optional[str] = None):
        message = f"문서를 찾을 수 없습니다: {filename}"
        if collection:
            message += f" (컬렉션: {collection})"
        super().__init__(message, {"filename": filename, "collection": collection})


class DocumentLoadException(DocumentException):
    """문서 로드 실패"""

    def __init__(self, filename: str, reason: str):
        message = f"문서 로드 실패: {filename} - {reason}"
        super().__init__(message, {"filename": filename, "reason": reason})


class UnsupportedFileTypeException(DocumentException):
    """지원하지 않는 파일 형식"""

    def __init__(self, extension: str, supported: list):
        message = f"지원하지 않는 파일 형식입니다: {extension}"
        super().__init__(
            message,
            {"extension": extension, "supported_extensions": supported}
        )


# ============ 검색 관련 예외 ============

class RetrievalException(RAGBaseException):
    """검색 관련 기본 예외"""
    pass


class VectorStoreNotInitializedException(RetrievalException):
    """벡터 스토어가 초기화되지 않았을 때"""

    def __init__(self):
        super().__init__("벡터 스토어가 초기화되지 않았습니다. 먼저 문서를 로드해주세요.")


class CollectionNotFoundException(RetrievalException):
    """컬렉션을 찾을 수 없을 때"""

    def __init__(self, collection_name: str):
        message = f"컬렉션을 찾을 수 없습니다: {collection_name}"
        super().__init__(message, {"collection_name": collection_name})


class EmptyQueryException(RetrievalException):
    """빈 쿼리가 전달되었을 때"""

    def __init__(self):
        super().__init__("질문을 입력해주세요.")


class QueryTooShortException(RetrievalException):
    """쿼리가 너무 짧을 때"""

    def __init__(self, query: str, min_length: int = 3):
        message = f"질문이 너무 짧습니다. 최소 {min_length}자 이상 입력해주세요."
        super().__init__(message, {"query": query, "min_length": min_length})


# ============ LLM 관련 예외 ============

class LLMException(RAGBaseException):
    """LLM 관련 기본 예외"""
    pass


class LLMProviderNotFoundException(LLMException):
    """지원하지 않는 LLM 제공자"""

    def __init__(self, provider: str, supported: list):
        message = f"지원하지 않는 LLM 제공자입니다: {provider}"
        super().__init__(
            message,
            {"provider": provider, "supported_providers": supported}
        )


class LLMResponseException(LLMException):
    """LLM 응답 오류"""

    def __init__(self, reason: str, provider: Optional[str] = None):
        message = f"LLM 응답 오류: {reason}"
        super().__init__(message, {"reason": reason, "provider": provider})


# ============ API 관련 예외 ============

class APIException(RAGBaseException):
    """외부 API 관련 기본 예외"""
    pass


class EmbeddingAPIException(APIException):
    """임베딩 API 오류"""

    def __init__(self, reason: str, api_name: str = "Unknown"):
        message = f"임베딩 API 오류 ({api_name}): {reason}"
        super().__init__(message, {"reason": reason, "api_name": api_name})


class RerankAPIException(APIException):
    """Rerank API 오류"""

    def __init__(self, reason: str):
        message = f"Rerank API 오류: {reason}"
        super().__init__(message, {"reason": reason})


# ============ 설정 관련 예외 ============

class ConfigurationException(RAGBaseException):
    """설정 관련 예외"""
    pass


class MissingAPIKeyException(ConfigurationException):
    """API 키 누락"""

    def __init__(self, key_name: str):
        message = f"환경변수가 설정되지 않았습니다: {key_name}"
        super().__init__(message, {"key_name": key_name})


class InvalidConfigurationException(ConfigurationException):
    """잘못된 설정값"""

    def __init__(self, config_name: str, value: Any, reason: str):
        message = f"잘못된 설정값: {config_name}={value} - {reason}"
        super().__init__(
            message,
            {"config_name": config_name, "value": value, "reason": reason}
        )
