"""
통합 문서 로더

다양한 문서 형식을 자동으로 감지하여 적절한 로더를 사용합니다.
지원 형식: HTML, PDF, Excel (.xlsx, .xls)
"""

import os
from typing import List, Optional
from langchain_core.documents import Document  # LangChain 1.0+

from .web_loader import HTMLFileLoader
from .pdf_loader import PDFLoader
from .excel_loader import ExcelLoader
from .word_loader import WordLoader


class UniversalDocumentLoader:
    """
    다양한 문서 형식을 자동으로 로드하는 통합 로더

    지원 형식:
    - HTML: .html, .htm
    - PDF: .pdf
    - Excel: .xlsx, .xls

    주요 기능:
    - 파일 확장자 자동 감지
    - 적절한 로더 자동 선택
    - 여러 형식의 파일 동시 로드
    """

    # 지원하는 파일 확장자
    SUPPORTED_EXTENSIONS = {
        'html': ['.html', '.htm'],
        'pdf': ['.pdf'],
        'excel': ['.xlsx', '.xls'],
        'word': ['.docx', '.doc']
    }

    def __init__(
        self,
        # HTML 옵션
        html_to_markdown: bool = False,
        # PDF 옵션
        pdf_by_page: bool = False,
        # Excel 옵션
        excel_by_sheet: bool = True,
        excel_include_header: bool = True,
        # Word 옵션
        word_extract_tables: bool = True
    ):
        """
        UniversalDocumentLoader 초기화

        Args:
            html_to_markdown (bool): HTML을 마크다운으로 변환 여부
            pdf_by_page (bool): PDF를 페이지별로 분리 여부
            excel_by_sheet (bool): Excel을 시트별로 분리 여부
            excel_include_header (bool): Excel 헤더 포함 여부
            word_extract_tables (bool): Word 표 추출 여부
        """
        self.html_to_markdown = html_to_markdown
        self.pdf_by_page = pdf_by_page
        self.excel_by_sheet = excel_by_sheet
        self.excel_include_header = excel_include_header
        self.word_extract_tables = word_extract_tables

        # 각 로더 초기화
        self.html_loader = HTMLFileLoader(convert_to_markdown=html_to_markdown)
        self.pdf_loader = PDFLoader(extract_by_page=pdf_by_page)
        self.excel_loader = ExcelLoader(
            extract_by_sheet=excel_by_sheet,
            include_header=excel_include_header
        )
        self.word_loader = WordLoader(extract_tables=word_extract_tables)

    def load(self, file_path: str) -> List[Document]:
        """
        파일 확장자를 자동 감지하여 문서를 로드합니다.

        Args:
            file_path (str): 로드할 파일 경로

        Returns:
            List[Document]: LangChain Document 객체 리스트

        Raises:
            Exception: 파일 로드 실패 또는 지원하지 않는 형식

        Example:
            >>> loader = UniversalDocumentLoader()
            >>> docs = loader.load("./data/sample.pdf")
            >>> print(f"{len(docs)}개 문서 로드됨")
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        # 파일 확장자 추출
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # 파일 형식 감지 및 적절한 로더 선택
        file_type = self._detect_file_type(ext)

        if file_type == 'html':
            return self.html_loader.load(file_path)
        elif file_type == 'pdf':
            return self.pdf_loader.load(file_path)
        elif file_type == 'excel':
            return self.excel_loader.load(file_path)
        elif file_type == 'word':
            return self.word_loader.load(file_path)
        else:
            raise Exception(
                f"지원하지 않는 파일 형식입니다: {ext}\n"
                f"지원 형식: {self.get_supported_extensions()}"
            )

    def load_multiple(self, file_paths: List[str]) -> List[Document]:
        """
        여러 파일을 로드합니다. 각 파일의 형식은 자동으로 감지됩니다.

        Args:
            file_paths (List[str]): 파일 경로 리스트

        Returns:
            List[Document]: 모든 파일에서 로드된 Document 리스트

        Example:
            >>> loader = UniversalDocumentLoader()
            >>> files = ["doc.html", "report.pdf", "data.xlsx"]
            >>> docs = loader.load_multiple(files)
            >>> print(f"총 {len(docs)}개 문서 로드됨")
        """
        all_documents = []
        load_stats = {
            'success': 0,
            'failed': 0,
            'by_type': {}
        }

        for file_path in file_paths:
            try:
                documents = self.load(file_path)
                all_documents.extend(documents)

                # 통계 업데이트
                load_stats['success'] += 1
                _, ext = os.path.splitext(file_path)
                file_type = self._detect_file_type(ext.lower())
                load_stats['by_type'][file_type] = load_stats['by_type'].get(file_type, 0) + 1

                print(f"✓ 로드 완료: {os.path.basename(file_path)} ({len(documents)}개 문서)")

            except Exception as e:
                load_stats['failed'] += 1
                print(f"✗ 로드 실패: {os.path.basename(file_path)} - {str(e)}")
                continue

        # 최종 통계 출력
        print(f"\n=== 로드 완료 ===")
        print(f"성공: {load_stats['success']}개, 실패: {load_stats['failed']}개")
        print(f"형식별: {load_stats['by_type']}")
        print(f"총 문서 수: {len(all_documents)}개")

        return all_documents

    def _detect_file_type(self, ext: str) -> Optional[str]:
        """
        파일 확장자로 파일 형식을 감지합니다.

        Args:
            ext (str): 파일 확장자 (예: '.pdf', '.html')

        Returns:
            Optional[str]: 파일 형식 ('html', 'pdf', 'excel') 또는 None
        """
        for file_type, extensions in self.SUPPORTED_EXTENSIONS.items():
            if ext in extensions:
                return file_type
        return None

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """
        지원하는 모든 파일 확장자 목록을 반환합니다.

        Returns:
            List[str]: 지원하는 확장자 리스트
        """
        all_extensions = []
        for extensions in cls.SUPPORTED_EXTENSIONS.values():
            all_extensions.extend(extensions)
        return all_extensions

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        파일이 지원되는 형식인지 확인합니다.

        Args:
            file_path (str): 확인할 파일 경로

        Returns:
            bool: 지원 여부
        """
        _, ext = os.path.splitext(file_path)
        return ext.lower() in cls.get_supported_extensions()


# 사용 예제
if __name__ == "__main__":
    print("=== 통합 문서 로더 예제 ===\n")

    loader = UniversalDocumentLoader()

    # 지원 형식 확인
    print("지원하는 파일 형식:")
    print(loader.get_supported_extensions())
    print()

    # 단일 파일 로드
    print("1. 단일 파일 로드:")
    try:
        docs = loader.load("./data/sample.pdf")
        print(f"성공! {len(docs)}개 문서 로드됨\n")
    except Exception as e:
        print(f"에러: {e}\n")

    # 여러 파일 로드
    print("2. 여러 파일 로드:")
    files = [
        "./html/Server 개요.html",
        "./data/sample.pdf",
        "./data/sample.xlsx"
    ]

    try:
        docs = loader.load_multiple(files)
        print(f"\n전체 {len(docs)}개 문서 로드 완료!")

        # 각 문서 정보 출력
        for i, doc in enumerate(docs[:3], 1):  # 처음 3개만
            print(f"\n문서 {i}:")
            print(f"  - 출처: {doc.metadata.get('source', 'N/A')}")
            print(f"  - 타입: {doc.metadata.get('type', 'N/A')}")
            print(f"  - 내용 미리보기: {doc.page_content[:100]}...")

    except Exception as e:
        print(f"에러: {e}")
