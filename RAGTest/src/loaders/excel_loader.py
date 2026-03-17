"""
Excel 문서 로더

이 모듈은 Excel 파일(.xlsx, .xls)을 로드하고 텍스트를 추출합니다.
LangChain의 문서 형식과 호환되도록 구현되었습니다.
"""

import os
import pandas as pd
from typing import List, Optional
from langchain_core.documents import Document  # LangChain 1.0+


class ExcelLoader:
    """
    Excel 파일에서 데이터를 추출하는 문서 로더

    주요 기능:
    - Excel 파일(.xlsx, .xls) 읽기
    - 시트별 또는 전체 데이터 로드
    - 테이블 형태를 텍스트로 변환
    - 메타데이터 추출 (파일명, 시트명, 행/열 수 등)
    - LangChain Document 형식으로 반환
    """

    def __init__(
        self,
        sheet_name: Optional[str] = None,
        extract_by_sheet: bool = True,
        include_header: bool = True
    ):
        """
        ExcelLoader 초기화

        Args:
            sheet_name (Optional[str]): 특정 시트만 로드. None이면 모든 시트 로드
            extract_by_sheet (bool): True면 시트별로 Document 생성, False면 전체를 하나로. 기본값 True
            include_header (bool): 헤더(컬럼명) 포함 여부. 기본값 True
        """
        self.sheet_name = sheet_name
        self.extract_by_sheet = extract_by_sheet
        self.include_header = include_header

    def load(self, file_path: str) -> List[Document]:
        """
        Excel 파일을 로드합니다.

        Args:
            file_path (str): Excel 파일 경로

        Returns:
            List[Document]: LangChain Document 객체 리스트

        Raises:
            Exception: Excel 로드 실패 시

        Example:
            >>> loader = ExcelLoader()
            >>> docs = loader.load("./data/sample.xlsx")
            >>> print(f"총 {len(docs)}개 시트 로드됨")
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

            documents = []

            # Excel 파일 읽기 (모든 시트 또는 특정 시트)
            if self.sheet_name:
                # 특정 시트만 로드
                df_dict = {self.sheet_name: pd.read_excel(file_path, sheet_name=self.sheet_name)}
            else:
                # 모든 시트 로드
                df_dict = pd.read_excel(file_path, sheet_name=None)

            if self.extract_by_sheet:
                # 시트별로 Document 생성
                for sheet_name, df in df_dict.items():
                    if df.empty:
                        continue

                    text = self._dataframe_to_text(df)

                    metadata = self._create_metadata(
                        file_path=file_path,
                        sheet_name=sheet_name,
                        num_rows=len(df),
                        num_cols=len(df.columns),
                        total_sheets=len(df_dict)
                    )

                    document = Document(
                        page_content=text,
                        metadata=metadata
                    )
                    documents.append(document)
            else:
                # 모든 시트를 하나의 Document로
                all_text = []
                for sheet_name, df in df_dict.items():
                    if df.empty:
                        continue

                    text = f"[시트: {sheet_name}]\n" + self._dataframe_to_text(df)
                    all_text.append(text)

                if all_text:
                    metadata = self._create_metadata(
                        file_path=file_path,
                        sheet_name=None,
                        num_rows=sum(len(df) for df in df_dict.values()),
                        num_cols=max(len(df.columns) for df in df_dict.values() if not df.empty),
                        total_sheets=len(df_dict)
                    )

                    document = Document(
                        page_content='\n\n'.join(all_text),
                        metadata=metadata
                    )
                    documents.append(document)

            if not documents:
                raise Exception("Excel에서 데이터를 추출할 수 없습니다.")

            return documents

        except Exception as e:
            raise Exception(f"Excel 로드 실패: {file_path}\n에러: {str(e)}")

    def load_multiple(self, file_paths: List[str]) -> List[Document]:
        """
        여러 Excel 파일을 로드합니다.

        Args:
            file_paths (List[str]): Excel 파일 경로 리스트

        Returns:
            List[Document]: 모든 파일에서 로드된 Document 리스트

        Example:
            >>> loader = ExcelLoader()
            >>> files = ["./data/data1.xlsx", "./data/data2.xlsx"]
            >>> docs = loader.load_multiple(files)
            >>> print(f"총 {len(docs)}개 문서 로드됨")
        """
        all_documents = []

        for file_path in file_paths:
            try:
                documents = self.load(file_path)
                all_documents.extend(documents)
                print(f"✓ 로드 완료: {file_path} ({len(documents)}개 시트)")
            except Exception as e:
                print(f"✗ 로드 실패: {file_path} - {str(e)}")
                continue

        return all_documents

    def _dataframe_to_text(self, df: pd.DataFrame) -> str:
        """
        DataFrame을 텍스트로 변환합니다.

        Args:
            df (pd.DataFrame): 변환할 DataFrame

        Returns:
            str: 텍스트 형식의 데이터
        """
        lines = []

        # 헤더 추가
        if self.include_header:
            header = " | ".join(str(col) for col in df.columns)
            lines.append(header)
            lines.append("-" * len(header))

        # 데이터 행 추가
        for idx, row in df.iterrows():
            row_text = " | ".join(str(val) if pd.notna(val) else "" for val in row.values)
            lines.append(row_text)

        return '\n'.join(lines)

    def _create_metadata(
        self,
        file_path: str,
        sheet_name: Optional[str],
        num_rows: int,
        num_cols: int,
        total_sheets: int
    ) -> dict:
        """
        Excel 메타데이터를 생성합니다.

        Args:
            file_path (str): 파일 경로
            sheet_name (Optional[str]): 시트 이름 (None이면 전체 문서)
            num_rows (int): 행 수
            num_cols (int): 열 수
            total_sheets (int): 전체 시트 수

        Returns:
            dict: 메타데이터 딕셔너리
        """
        metadata = {
            'source': file_path,
            'file_name': os.path.basename(file_path),
            'type': 'excel',
            'num_rows': num_rows,
            'num_cols': num_cols,
            'total_sheets': total_sheets
        }

        if sheet_name is not None:
            metadata['sheet_name'] = sheet_name

        return metadata


# 사용 예제
if __name__ == "__main__":
    print("=== Excel 문서 로더 예제 ===\n")

    # 시트별로 로드
    print("1. 시트별 로드:")
    loader = ExcelLoader(extract_by_sheet=True)
    try:
        docs = loader.load("./data/sample.xlsx")
        print(f"문서 로드 성공! (총 {len(docs)}개 시트)")
        for doc in docs:
            print(f"\n시트: {doc.metadata.get('sheet_name', 'N/A')}")
            print(f"  - 행 수: {doc.metadata.get('num_rows', 'N/A')}")
            print(f"  - 열 수: {doc.metadata.get('num_cols', 'N/A')}")
            print(f"  - 내용 미리보기: {doc.page_content[:150]}...")
    except Exception as e:
        print(f"에러: {e}\n")

    # 전체를 하나로 로드
    print("\n2. 전체 문서 로드:")
    loader_all = ExcelLoader(extract_by_sheet=False)
    try:
        docs = loader_all.load("./data/sample.xlsx")
        print(f"문서 로드 성공!")
        print(f"전체 시트 수: {docs[0].metadata.get('total_sheets', 'N/A')}")
        print(f"내용 미리보기: {docs[0].page_content[:200]}...")
    except Exception as e:
        print(f"에러: {e}")
