"""
중앙화된 설정 관리 모듈

모든 하드코딩된 값들을 환경변수 또는 기본값으로 관리
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Dict, Optional


class ChunkingSettings(BaseSettings):
    """청킹 관련 설정"""
    # Qwen3-Embedding-8B 최적화 (더 큰 컨텍스트 지원)
    default_chunk_size: int = Field(default=1500, description="기본 청크 크기 (문자)")
    default_chunk_overlap: int = Field(default=300, description="청크 오버랩 크기")
    min_chunk_size: int = Field(default=200, description="최소 청크 크기")
    max_chunk_size: int = Field(default=3000, description="최대 청크 크기")

    # 문서 타입별 청크 크기
    html_chunk_size: int = Field(default=2000, description="HTML 문서 청크 크기")
    pdf_chunk_size: int = Field(default=1200, description="PDF 문서 청크 크기")
    excel_chunk_size: int = Field(default=800, description="Excel 문서 청크 크기")

    class Config:
        env_prefix = "CHUNKING_"


class RAGSettings(BaseSettings):
    """RAG 파이프라인 설정"""
    retrieval_k: int = Field(default=5, description="검색할 문서 수")
    rerank_top_n: int = Field(default=3, description="재순위화 후 선택할 문서 수")
    max_retries: int = Field(default=2, description="품질 미달 시 재시도 횟수")
    min_quality_score: float = Field(default=0.6, description="최소 품질 점수 (0-1)")

    # Hybrid Search 설정
    hybrid_alpha: float = Field(default=0.5, description="Hybrid Search 가중치 (0=BM25, 1=Vector)")

    # 품질 검증 가중치
    quality_weight_length: float = Field(default=0.2, description="답변 길이 가중치")
    quality_weight_grounding: float = Field(default=0.4, description="문서 근거성 가중치")
    quality_weight_directness: float = Field(default=0.2, description="직접성 가중치")
    quality_weight_relevance: float = Field(default=0.2, description="관련성 가중치")

    # 답변 기준값
    min_answer_length: int = Field(default=200, description="최소 답변 길이 (문자)")

    class Config:
        env_prefix = "RAG_"


class LLMSettings(BaseSettings):
    """LLM 관련 설정"""
    provider: str = Field(default="clovax", description="LLM 제공자")
    temperature: float = Field(default=0.2, description="기본 temperature")
    creative_temperature: float = Field(default=0.5, description="창의적 답변용 temperature")
    max_tokens: int = Field(default=2048, description="최대 토큰 수")

    # 프롬프트 전략
    prompt_strategy: str = Field(default="balanced", description="프롬프트 전략 (strict/balanced/few_shot)")

    # 모델명 설정
    default_model_name: str = Field(default="gpt-5.2", description="기본 모델명")
    secure_model_name: str = Field(default="gpt-oss-120b", description="보안 모드 모델명")

    class Config:
        env_prefix = "LLM_"


class EmbeddingSettings(BaseSettings):
    """임베딩 관련 설정"""
    provider: str = Field(default="huggingface", description="임베딩 제공자")
    model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="HuggingFace 모델명")
    dimension: int = Field(default=384, description="임베딩 차원")
    batch_size: int = Field(default=32, description="배치 크기")

    # API 설정
    clova_rate_limit: float = Field(default=1.0, description="CLOVA API 요청 간격 (초)")
    qwen_base_url: str = Field(default="https://namc-aigw.io.naver.com", description="Qwen API Base URL")

    class Config:
        env_prefix = "EMBEDDING_"


class CrawlingSettings(BaseSettings):
    """웹 크롤링 설정"""
    timeout: int = Field(default=60000, description="페이지 로드 타임아웃 (ms)")
    wait_time: int = Field(default=2000, description="JS 실행 대기 시간 (ms)")
    viewport_width: int = Field(default=1280, description="브라우저 너비")
    viewport_height: int = Field(default=800, description="브라우저 높이")
    headless: bool = Field(default=True, description="헤드리스 모드")

    class Config:
        env_prefix = "CRAWL_"


class StreamingSettings(BaseSettings):
    """스트리밍 응답 설정"""
    chunk_size: int = Field(default=3, description="스트리밍 청크 크기 (문자)")
    delay: float = Field(default=0.01, description="청크 간 딜레이 (초)")
    preview_length: int = Field(default=200, description="문서 미리보기 길이")

    class Config:
        env_prefix = "STREAM_"


class PathSettings(BaseSettings):
    """경로 설정"""
    data_dir: str = Field(default="./data", description="데이터 디렉토리")
    faiss_dir: str = Field(default="./data/faiss_web", description="FAISS 저장 디렉토리")
    feedback_dir: str = Field(default="./data/feedback", description="피드백 저장 디렉토리")
    learning_cache_path: str = Field(default="./data/learning_cache.json", description="학습 캐시 경로")
    html_dir: str = Field(default="./html", description="HTML 파일 디렉토리")
    documents_dir: str = Field(default="./documents", description="업로드 문서 디렉토리")

    class Config:
        env_prefix = "PATH_"


class UISettings(BaseSettings):
    """UI 관련 설정"""
    default_category_color: str = Field(default="#6366f1", description="기본 카테고리 색상")
    default_category_icon: str = Field(default="📁", description="기본 카테고리 아이콘")

    class Config:
        env_prefix = "UI_"


class WebSearchSettings(BaseSettings):
    """웹 검색 교차 검증 설정"""
    enabled: bool = Field(default=False, description="웹 검색 기능 전역 활성화 여부")
    api_key: str = Field(default="", description="Tavily API Key")
    max_results: int = Field(default=3, description="최대 검색 결과 수")
    search_depth: str = Field(default="basic", description="검색 깊이 (basic/advanced)")
    anonymize_query: bool = Field(default=True, description="쿼리 익명화 여부")

    # 도메인 필터
    include_domains: List[str] = Field(
        default=[],
        description="허용 도메인 리스트 (비어있으면 모든 도메인 허용)"
    )
    exclude_domains: List[str] = Field(
        default=[],
        description="제외 도메인 리스트"
    )

    # 보안 관련
    allowed_in_secure_mode: bool = Field(
        default=False,
        description="보안 모드에서 웹 검색 허용 여부"
    )

    # 임베딩 기반 유사도 검증 임계값
    embedding_similarity_confirmed: float = Field(
        default=0.75,
        description="CONFIRMED 상태 임계값 (이상이면 웹 결과와 일치 확인)"
    )
    embedding_similarity_enhanced: float = Field(
        default=0.55,
        description="ENHANCED 상태 임계값 (이상이면 답변 보강 가능)"
    )
    embedding_similarity_conflicting: float = Field(
        default=0.35,
        description="CONFLICTING 상태 임계값 (이상이면 충돌 가능성)"
    )

    class Config:
        env_prefix = "WEB_SEARCH_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


class Settings(BaseSettings):
    """통합 설정 클래스"""
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    crawling: CrawlingSettings = Field(default_factory=CrawlingSettings)
    streaming: StreamingSettings = Field(default_factory=StreamingSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    ui: UISettings = Field(default_factory=UISettings)
    web_search: WebSearchSettings = Field(default_factory=WebSearchSettings)

    # 앱 설정
    debug: bool = Field(default=True, description="디버그 모드")
    host: str = Field(default="0.0.0.0", description="서버 호스트")
    port: int = Field(default=5000, description="서버 포트")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Allow extra fields from .env file


# 싱글톤 인스턴스
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """설정 싱글톤 인스턴스 반환"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
