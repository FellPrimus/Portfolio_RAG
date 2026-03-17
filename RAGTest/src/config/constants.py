"""
시스템 상수 정의

변경되지 않는 고정 값들
"""
from typing import List, Dict, Set

# 지원 파일 확장자
SUPPORTED_EXTENSIONS: List[str] = [
    ".html", ".htm", ".pdf", ".xlsx", ".xls", ".docx", ".doc"
]

# 회피 표현 목록 (할루시네이션 감지용)
EVASIVE_PHRASES: List[str] = [
    "모르겠", "찾을 수 없", "정보가 없", "알 수 없",
    "확인되지 않", "명시되어 있지 않"
]

# 금지 표현 목록 (할루시네이션 유발)
FORBIDDEN_PHRASES: List[str] = [
    "일반적으로", "추정하건대", "보통", "대부분",
    "아마도", "~일 것입니다", "~할 것으로 예상"
]

# 질문 패턴 분류
QUESTION_PATTERNS: Dict[str, List[str]] = {
    "price": ["가격", "비용", "요금", "얼마", "pricing", "cost"],
    "feature": ["기능", "특징", "제공", "지원", "feature", "support"],
    "method": ["방법", "어떻게", "설정", "구성", "how", "setup"],
    "comparison": ["차이", "비교", "vs", "versus", "다른점"],
    "performance": ["성능", "속도", "처리량", "performance", "throughput"]
}

# HTTP 상태 코드 메시지
HTTP_STATUS_MESSAGES: Dict[int, str] = {
    400: "잘못된 요청입니다.",
    404: "요청한 리소스를 찾을 수 없습니다.",
    500: "서버 내부 오류가 발생했습니다."
}

# 기본 카테고리
DEFAULT_CATEGORY: Dict[str, str] = {
    "id": "general",
    "name": "일반",
    "color": "#6366f1",
    "icon": "📄"
}

# 신뢰도 레벨
CONFIDENCE_LEVELS: Dict[str, float] = {
    "high": 0.7,
    "medium": 0.5,
    "low": 0.0
}

# 로그 포맷
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
