# RAGTest 호환 API 라우터
"""
RAGTest와 동일한 API 형식을 제공하는 호환 레이어입니다.
기존 RAGTest 프론트엔드가 수정 없이 동작할 수 있도록 합니다.
"""

from . import documents
from . import query
from . import categories
from . import folders
from . import files

__all__ = ["documents", "query", "categories", "folders", "files"]
