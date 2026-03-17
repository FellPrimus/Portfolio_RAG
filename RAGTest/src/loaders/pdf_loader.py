"""
PDF 문서 로더

이 모듈은 PDF 파일을 로드하고 텍스트를 추출합니다.
LangChain의 문서 형식과 호환되도록 구현되었습니다.
"""

import os
import logging
import pdfplumber
from typing import List, Optional
from langchain_core.documents import Document  # LangChain 1.0+

logger = logging.getLogger(__name__)


class PDFLoader:
    """
    PDF 파일에서 텍스트를 추출하는 문서 로더

    주요 기능:
    - PDF 파일에서 텍스트 추출
    - 페이지별 또는 전체 문서 로드
    - 메타데이터 추출 (파일명, 페이지 수, 페이지 번호 등)
    - LangChain Document 형식으로 반환
    """

    def __init__(
        self,
        extract_by_page: bool = False,
        extract_images: bool = False
    ):
        """
        PDFLoader 초기화

        Args:
            extract_by_page (bool): True면 페이지별로 Document 생성, False면 전체를 하나로. 기본값 False
            extract_images (bool): 이미지 추출 여부 (향후 구현). 기본값 False
        """
        self.extract_by_page = extract_by_page
        self.extract_images = extract_images

    def load(self, file_path: str) -> List[Document]:
        """
        PDF 파일을 로드합니다.

        Args:
            file_path (str): PDF 파일 경로

        Returns:
            List[Document]: LangChain Document 객체 리스트

        Raises:
            Exception: PDF 로드 실패 시

        Example:
            >>> loader = PDFLoader()
            >>> docs = loader.load("./data/sample.pdf")
            >>> print(f"총 {len(docs)}개 문서 로드됨")
        """
        try:
            logger.info(f"[PDF] 파일 로드 시작: {os.path.basename(file_path)}")

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

            documents = []

            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"[PDF] 총 페이지 수: {total_pages}")

                if self.extract_by_page:
                    # 페이지별로 Document 생성
                    logger.info(f"[PDF] 페이지별 추출 모드")
                    extracted_pages = 0
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()

                        if text and text.strip():
                            logger.debug(f"[PDF] 페이지 {page_num}: {len(text)} 문자 추출")
                            metadata = self._create_metadata(
                                file_path=file_path,
                                page_num=page_num,
                                total_pages=total_pages
                            )

                            document = Document(
                                page_content=text.strip(),
                                metadata=metadata
                            )
                            documents.append(document)
                            extracted_pages += 1
                        else:
                            logger.warning(f"[PDF] 페이지 {page_num}: 텍스트 없음 (이미지 전용 페이지?)")

                    logger.info(f"[PDF] 추출 완료: {extracted_pages}/{total_pages} 페이지")
                else:
                    # 전체 페이지를 하나의 Document로
                    logger.info(f"[PDF] 전체 페이지 통합 추출 모드")
                    all_text = []
                    empty_pages = 0

                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text and text.strip():
                            all_text.append(text.strip())
                            logger.debug(f"[PDF] 페이지 {page_num}: {len(text)} 문자")
                        else:
                            empty_pages += 1
                            logger.warning(f"[PDF] 페이지 {page_num}: 텍스트 없음")

                    if empty_pages > 0:
                        logger.warning(f"[PDF] ⚠️  {empty_pages}개 페이지에서 텍스트 추출 실패 (이미지 기반 PDF?)")

                    if all_text:
                        total_chars = sum(len(t) for t in all_text)
                        logger.info(f"[PDF] 총 {total_chars:,} 문자 추출 ({len(all_text)}/{total_pages} 페이지)")

                        metadata = self._create_metadata(
                            file_path=file_path,
                            page_num=None,
                            total_pages=total_pages
                        )

                        document = Document(
                            page_content='\n\n'.join(all_text),
                            metadata=metadata
                        )
                        documents.append(document)

            if not documents:
                logger.error(f"[PDF] ❌ 텍스트 추출 실패: 모든 페이지가 비어있음")
                logger.error(f"[PDF] 💡 이 파일은 스캔된 이미지 기반 PDF일 수 있습니다. OCR이 필요합니다.")
                raise Exception("PDF에서 텍스트를 추출할 수 없습니다. (이미지 기반 PDF는 OCR 필요)")

            logger.info(f"[PDF] ✅ 로드 성공: {len(documents)}개 Document 생성")
            return documents

        except Exception as e:
            logger.error(f"[PDF] ❌ 로드 실패: {file_path}")
            logger.error(f"[PDF] 에러: {str(e)}")
            raise Exception(f"PDF 로드 실패: {file_path}\n에러: {str(e)}")

    def load_multiple(self, file_paths: List[str]) -> List[Document]:
        """
        여러 PDF 파일을 로드합니다.

        Args:
            file_paths (List[str]): PDF 파일 경로 리스트

        Returns:
            List[Document]: 모든 파일에서 로드된 Document 리스트

        Example:
            >>> loader = PDFLoader()
            >>> files = ["./data/doc1.pdf", "./data/doc2.pdf"]
            >>> docs = loader.load_multiple(files)
            >>> print(f"총 {len(docs)}개 문서 로드됨")
        """
        all_documents = []

        for file_path in file_paths:
            try:
                documents = self.load(file_path)
                all_documents.extend(documents)
                print(f"✓ 로드 완료: {file_path} ({len(documents)}개 문서)")
            except Exception as e:
                print(f"✗ 로드 실패: {file_path} - {str(e)}")
                continue

        return all_documents

    def _create_metadata(
        self,
        file_path: str,
        page_num: Optional[int],
        total_pages: int
    ) -> dict:
        """
        PDF 메타데이터를 생성합니다.

        Args:
            file_path (str): 파일 경로
            page_num (Optional[int]): 페이지 번호 (None이면 전체 문서)
            total_pages (int): 전체 페이지 수

        Returns:
            dict: 메타데이터 딕셔너리
        """
        metadata = {
            'source': file_path,
            'file_name': os.path.basename(file_path),
            'type': 'pdf',
            'total_pages': total_pages
        }

        if page_num is not None:
            metadata['page'] = page_num

        return metadata


# 사용 예제
if __name__ == "__main__":
    print("=== PDF 문서 로더 예제 ===\n")

    # 전체 문서를 하나로 로드
    print("1. 전체 문서 로드:")
    loader = PDFLoader(extract_by_page=False)
    try:
        docs = loader.load("./data/sample.pdf")
        print(f"문서 로드 성공!")
        print(f"파일명: {docs[0].metadata.get('file_name', 'N/A')}")
        print(f"전체 페이지: {docs[0].metadata.get('total_pages', 'N/A')}")
        print(f"내용 미리보기: {docs[0].page_content[:200]}...\n")
    except Exception as e:
        print(f"에러: {e}\n")

    # 페이지별로 로드
    print("2. 페이지별 로드:")
    loader_by_page = PDFLoader(extract_by_page=True)
    try:
        docs = loader_by_page.load("./data/sample.pdf")
        print(f"문서 로드 성공! (총 {len(docs)}개 페이지)")
        for doc in docs[:3]:  # 처음 3페이지만 출력
            print(f"  - 페이지 {doc.metadata['page']}: {doc.page_content[:100]}...")
    except Exception as e:
        print(f"에러: {e}")
