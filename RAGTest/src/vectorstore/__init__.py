"""
벡터 스토어 모듈

임베딩을 저장하고 유사도 검색을 수행하는 벡터 데이터베이스를 제공합니다.
"""

from .faiss_store import FAISSVectorStore

__all__ = ['FAISSVectorStore']
