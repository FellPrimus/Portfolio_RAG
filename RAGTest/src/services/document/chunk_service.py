"""
문서 청크 조회 서비스

벡터DB에 저장된 문서의 청크를 조회하는 기능을 담당합니다.
"""

from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .session_state import DocumentSessionState


class ChunkService:
    """문서 청크 조회 서비스"""

    def __init__(self, state: 'DocumentSessionState'):
        self.state = state

    def get_document_chunks_preview(
        self, filename: str, collection: str, limit: int = 3
    ) -> Dict:
        """
        특정 문서의 청크 미리보기 조회 (처음 N개)

        Args:
            filename: 파일명
            collection: 컬렉션 이름
            limit: 반환할 최대 청크 개수

        Returns:
            {'success': bool, 'filename': str, 'total_chunks': int, 'preview_chunks': list}
        """
        try:
            if not filename or not collection:
                return {'success': False, 'error': '파일명과 컬렉션이 필요합니다.'}

            vectorstore = self._get_vectorstore(collection)
            if vectorstore is None:
                return {'success': False, 'error': '컬렉션을 찾을 수 없습니다.'}

            all_chunks = vectorstore.get_chunks_by_filename(filename, limit=None)
            if not all_chunks:
                return {'success': False, 'error': '문서를 찾을 수 없습니다.'}

            preview_chunks = all_chunks[:limit] if limit else all_chunks

            return {
                'success': True,
                'filename': filename,
                'total_chunks': len(all_chunks),
                'preview_chunks': preview_chunks
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 청크 미리보기 조회 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def get_document_chunks_all(
        self, filename: str, collection: str, page: int = 1, per_page: int = 10
    ) -> Dict:
        """
        특정 문서의 전체 청크 조회 (페이지네이션)

        Args:
            filename: 파일명
            collection: 컬렉션 이름
            page: 페이지 번호 (1부터 시작)
            per_page: 페이지당 청크 개수

        Returns:
            {'success': bool, 'filename': str, 'total_chunks': int,
             'current_page': int, 'total_pages': int, 'chunks': list}
        """
        try:
            if not filename or not collection:
                return {'success': False, 'error': '파일명과 컬렉션이 필요합니다.'}

            vectorstore = self._get_vectorstore(collection)
            if vectorstore is None:
                return {'success': False, 'error': '컬렉션을 찾을 수 없습니다.'}

            all_chunks = vectorstore.get_chunks_by_filename(filename, limit=None)
            if not all_chunks:
                return {'success': False, 'error': '문서를 찾을 수 없습니다.'}

            # 페이지네이션 계산
            total_chunks = len(all_chunks)
            total_pages = (total_chunks + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_chunks = all_chunks[start_idx:end_idx]

            return {
                'success': True,
                'filename': filename,
                'total_chunks': total_chunks,
                'current_page': page,
                'total_pages': total_pages,
                'chunks': page_chunks
            }

        except Exception as e:
            import traceback
            print(f"[ERROR] 전체 청크 조회 실패: {e}")
            print(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _get_vectorstore(self, collection: str):
        """벡터스토어 로드"""
        from src.vectorstore.faiss_store import FAISSVectorStore

        emb_model = self.state.embedding_model
        if emb_model is None:
            return None

        persist_directory = "./data/faiss_web"
        vectorstore = FAISSVectorStore(
            collection_name=collection,
            persist_directory=persist_directory,
            embedding_function=emb_model
        )

        if not vectorstore.exists():
            return None

        return vectorstore
