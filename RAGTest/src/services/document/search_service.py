"""
문서 검색 서비스

다중 컬렉션 검색 및 필터링을 담당합니다.
"""

import os
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .session_state import DocumentSessionState
    from langchain_core.documents import Document


class SearchService:
    """문서 검색 서비스"""

    def __init__(self, state: 'DocumentSessionState'):
        self.state = state

    def multi_collection_search(self, query: str, k: int = 5) -> List['Document']:
        """
        모든 활성화된 컬렉션에서 검색 후 결과 병합

        Args:
            query: 검색 쿼리
            k: 반환할 최대 문서 수

        Returns:
            List[Document]: 상위 k개 문서 리스트
        """
        try:
            if not self.state.active_vectorstores:
                print("[WARN] 활성화된 컬렉션이 없습니다.")
                return []

            print(f"\n[SEARCH] 다중 컬렉션 검색 시작: {len(self.state.active_vectorstores)}개 컬렉션")
            self._log_filter_state()

            all_results = []

            # 각 컬렉션에서 검색
            for collection_name, vectorstore in self.state.active_vectorstores.items():
                try:
                    results = self._search_collection(
                        vectorstore, collection_name, query, k
                    )
                    all_results.extend(results)
                except Exception as e:
                    print(f"[ERROR] 컬렉션 검색 실패: {collection_name} - {e}")
                    continue

            # 점수 기준 정렬 (FAISS는 L2 거리이므로 낮을수록 좋음)
            all_results.sort(key=lambda x: x[1])

            # 상위 k개만 반환
            top_docs = [doc for doc, score in all_results[:k]]

            self._log_search_results(all_results, top_docs)

            return top_docs

        except Exception as e:
            import traceback
            print(f"[ERROR] 다중 컬렉션 검색 실패: {e}")
            print(traceback.format_exc())
            return []

    def _search_collection(
        self, vectorstore, collection_name: str, query: str, k: int
    ) -> List[tuple]:
        """단일 컬렉션에서 검색"""
        # 필터링을 위해 더 많이 검색
        search_k = k * 3 if self.state.active_filenames else k
        docs_with_scores = vectorstore.similarity_search_with_score(query, k=search_k)

        results = []
        filtered_count = 0

        for doc, score in docs_with_scores:
            if self.state.active_filenames:
                if not self._matches_filename_filter(doc):
                    filtered_count += 1
                    continue

            doc.metadata['collection'] = collection_name
            results.append((doc, score))

        self._log_collection_search(collection_name, len(docs_with_scores), filtered_count)

        return results

    def _matches_filename_filter(self, doc) -> bool:
        """문서가 파일명 필터에 매칭되는지 확인"""
        if not self.state.active_filenames:
            return True

        # 문서 식별자 구성
        category_id = doc.metadata.get('category_id', doc.metadata.get('category', 'general'))
        service_name = doc.metadata.get('service_name', '')

        if service_name:
            doc_filename = f"{category_id}:{service_name}"
        else:
            source = doc.metadata.get('source', '')
            doc_filename = os.path.basename(source)

        return doc_filename in self.state.active_filenames

    def _log_filter_state(self) -> None:
        """필터 상태 로깅"""
        print(f"[SEARCH] DEBUG - active_filenames: {self.state.active_filenames}")
        if self.state.active_filenames:
            print(f"[SEARCH] 활성화된 파일 필터: {len(self.state.active_filenames)}개")

    def _log_collection_search(
        self, collection_name: str, total: int, filtered: int
    ) -> None:
        """컬렉션 검색 결과 로깅"""
        if filtered > 0:
            print(f"[SEARCH] {collection_name}: {total - filtered}개 문서 (필터됨: {filtered}개)")
        else:
            print(f"[SEARCH] {collection_name}: {total}개 문서 검색됨")

    def _log_search_results(self, all_results: List, top_docs: List) -> None:
        """검색 결과 로깅"""
        print(f"[SEARCH] 총 {len(all_results)}개 검색, 상위 {len(top_docs)}개 반환")
        sources = set([doc.metadata.get('source', 'Unknown') for doc in top_docs])
        print(f"[SEARCH] 검색된 문서 출처: {', '.join([os.path.basename(s) for s in sources])}")
