"""
텍스트 청킹 모듈

문서를 작은 청크(chunk)로 분할하는 다양한 전략을 제공합니다.
청킹은 RAG 시스템의 성능에 중요한 영향을 미칩니다.

청킹 전략:
1. RecursiveCharacterTextSplitter: 문단, 문장, 단어 순으로 재귀적 분할
2. CharacterTextSplitter: 고정 크기 문자 기반 분할
3. SemanticChunker: 의미론적 유사도 기반 분할 (고급)
"""

from typing import List, Optional
from langchain_text_splitters import (  # LangChain 1.0+
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter
)
from langchain_core.documents import Document  # LangChain 1.0+
import tiktoken


class TextChunker:
    """
    텍스트 문서를 청크로 분할하는 클래스

    주요 개념:
    - chunk_size: 각 청크의 최대 크기 (문자 수 또는 토큰 수)
    - chunk_overlap: 연속된 청크 간의 중복 영역
      * 오버랩은 문맥 유지와 검색 품질 향상에 도움
      * 일반적으로 chunk_size의 10-20% 권장

    Example:
        청크 크기 1000, 오버랩 200인 경우:
        Chunk 1: [0 -------- 1000]
        Chunk 2:         [800 -------- 1800]
        Chunk 3:                  [1600 -------- 2600]
                          ↑ 200자 오버랩
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: Optional[callable] = None,
        separators: Optional[List[str]] = None
    ):
        """
        TextChunker 초기화

        Args:
            chunk_size (int): 청크의 최대 크기. 기본값 1000
            chunk_overlap (int): 청크 간 오버랩 크기. 기본값 200
            length_function (callable, optional): 길이 측정 함수.
                기본값은 len() (문자 수). tiktoken 사용 가능
            separators (List[str], optional): 분할 기준 문자들.
                기본값: ["\n\n", "\n", " ", ""]
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 분할 기준: 문단 > 줄 > 공백 > 문자 순으로 시도
        self.separators = separators or ["\n\n", "\n", " ", ""]

        # 길이 함수 (문자 수 또는 토큰 수)
        self.length_function = length_function or len

        # RecursiveCharacterTextSplitter 생성
        # 가장 큰 구분자부터 시도하여 자연스러운 경계에서 분할
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=self.length_function,
            separators=self.separators,
            keep_separator=True  # 구분자 유지 (문맥 보존)
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        문서 리스트를 청크로 분할합니다.

        Args:
            documents (List[Document]): 분할할 문서 리스트

        Returns:
            List[Document]: 청크로 분할된 문서 리스트
                각 청크는 원본 문서의 메타데이터를 상속받고
                추가로 청크 번호가 포함됩니다.

        Example:
            >>> chunker = TextChunker(chunk_size=500, chunk_overlap=50)
            >>> chunks = chunker.chunk_documents(documents)
            >>> print(f"총 {len(chunks)}개의 청크 생성됨")
            >>> print(chunks[0].metadata)  # 메타데이터 확인
        """
        # LangChain의 split_documents 메서드 사용
        chunks = self.text_splitter.split_documents(documents)

        # 각 청크에 추가 메타데이터 부여
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_id'] = i
            chunk.metadata['chunk_size'] = len(chunk.page_content)

        # 중복 로그 제거 (app.py에서 더 상세한 로그 출력)
        # print(f"✓ 총 {len(documents)}개 문서를 {len(chunks)}개 청크로 분할")

        return chunks

    def chunk_text(self, text: str, metadata: Optional[dict] = None) -> List[Document]:
        """
        단일 텍스트를 청크로 분할합니다.

        Args:
            text (str): 분할할 텍스트
            metadata (dict, optional): 청크에 포함할 메타데이터

        Returns:
            List[Document]: 청크 Document 리스트

        Example:
            >>> chunker = TextChunker()
            >>> text = "긴 텍스트..."
            >>> chunks = chunker.chunk_text(text, metadata={"source": "test"})
        """
        # 텍스트를 Document 형태로 변환
        document = Document(
            page_content=text,
            metadata=metadata or {}
        )

        return self.chunk_documents([document])


class TokenBasedChunker:
    """
    토큰 기반 청킹

    문자 수가 아닌 토큰 수를 기준으로 분할합니다.
    LLM API는 토큰 수로 과금되므로 정확한 비용 예측에 유용합니다.

    토큰 vs 문자:
    - 영어: 1 토큰 ≈ 4 문자 (평균)
    - 한국어: 1 토큰 ≈ 1-2 문자 (한글은 토큰화가 비효율적)
    - 공백, 특수문자도 토큰에 포함
    """

    def __init__(
        self,
        chunk_size: int = 500,  # 토큰 수
        chunk_overlap: int = 50,
        model_name: str = "gpt-3.5-turbo"
    ):
        """
        TokenBasedChunker 초기화

        Args:
            chunk_size (int): 청크의 최대 토큰 수
            chunk_overlap (int): 청크 간 오버랩 토큰 수
            model_name (str): 토큰화에 사용할 모델명
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_name = model_name

        # tiktoken 인코더 로드
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # 모델을 찾을 수 없으면 기본 인코딩 사용
            self.encoding = tiktoken.get_encoding("cl100k_base")

        # 토큰 카운트 함수
        def token_counter(text: str) -> int:
            """텍스트의 토큰 수를 반환"""
            return len(self.encoding.encode(text))

        # RecursiveCharacterTextSplitter에 토큰 카운터 전달
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=token_counter,
            separators=["\n\n", "\n", " ", ""]
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """
        문서를 토큰 기반으로 청크 분할

        Args:
            documents (List[Document]): 분할할 문서 리스트

        Returns:
            List[Document]: 청크로 분할된 문서 리스트
        """
        chunks = self.text_splitter.split_documents(documents)

        # 각 청크의 실제 토큰 수 계산 및 메타데이터 추가
        for i, chunk in enumerate(chunks):
            token_count = len(self.encoding.encode(chunk.page_content))
            chunk.metadata['chunk_id'] = i
            chunk.metadata['token_count'] = token_count

        print(f"✓ 총 {len(documents)}개 문서를 {len(chunks)}개 청크로 분할 (토큰 기반)")
        total_tokens = sum(c.metadata['token_count'] for c in chunks)
        print(f"  총 토큰 수: {total_tokens:,}")

        return chunks


class FixedSizeChunker:
    """
    고정 크기 청킹

    단순하게 고정된 크기로 텍스트를 분할합니다.
    구분자를 고려하지 않으므로 문장이 중간에 잘릴 수 있습니다.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        FixedSizeChunker 초기화

        Args:
            chunk_size (int): 청크의 고정 크기
            chunk_overlap (int): 청크 간 오버랩
        """
        self.text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """문서를 고정 크기로 청크 분할"""
        chunks = self.text_splitter.split_documents(documents)

        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_id'] = i

        print(f"✓ 고정 크기 청킹: {len(chunks)}개 청크 생성")

        return chunks


# 청킹 전략 비교 유틸리티
def compare_chunking_strategies(text: str, chunk_size: int = 500):
    """
    여러 청킹 전략을 비교합니다 (교육용)

    Args:
        text (str): 테스트할 텍스트
        chunk_size (int): 비교할 청크 크기
    """
    print("=" * 60)
    print("청킹 전략 비교")
    print("=" * 60)

    # 1. 재귀적 청킹 (권장)
    recursive_chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=50)
    recursive_chunks = recursive_chunker.chunk_text(text)
    print(f"\n1. 재귀적 청킹: {len(recursive_chunks)}개 청크")
    print(f"   첫 청크 크기: {len(recursive_chunks[0].page_content)}")

    # 2. 고정 크기 청킹
    fixed_chunker = FixedSizeChunker(chunk_size=chunk_size, chunk_overlap=50)
    fixed_chunks = fixed_chunker.chunk_documents(
        [Document(page_content=text, metadata={})]
    )
    print(f"\n2. 고정 크기 청킹: {len(fixed_chunks)}개 청크")
    print(f"   첫 청크 크기: {len(fixed_chunks[0].page_content)}")

    # 3. 토큰 기반 청킹
    token_chunker = TokenBasedChunker(chunk_size=chunk_size // 4, chunk_overlap=10)
    token_chunks = token_chunker.chunk_documents(
        [Document(page_content=text, metadata={})]
    )
    print(f"\n3. 토큰 기반 청킹: {len(token_chunks)}개 청크")
    if token_chunks:
        print(f"   첫 청크 토큰 수: {token_chunks[0].metadata.get('token_count', 'N/A')}")

    print("\n" + "=" * 60)


# 사용 예제
if __name__ == "__main__":
    print("=== 텍스트 청킹 예제 ===\n")

    # 샘플 텍스트
    sample_text = """
    RAG (Retrieval-Augmented Generation)는 대규모 언어 모델의 응답에 외부 지식을 결합하는 기술입니다.

    RAG의 주요 구성 요소는 다음과 같습니다:
    1. 문서 로딩: 외부 데이터 소스에서 문서를 가져옵니다.
    2. 청킹: 문서를 작은 단위로 분할합니다.
    3. 임베딩: 텍스트를 벡터로 변환합니다.
    4. 벡터 저장: 임베딩을 데이터베이스에 저장합니다.
    5. 검색: 쿼리와 유사한 문서를 찾습니다.
    6. 생성: LLM이 검색된 문서를 참고하여 답변을 생성합니다.

    청킹은 RAG 성능에 중요한 영향을 미칩니다. 청크가 너무 크면 불필요한 정보가 포함되고,
    너무 작으면 문맥이 손실될 수 있습니다.
    """ * 3  # 텍스트를 더 길게 만들기

    # 기본 청킹
    chunker = TextChunker(chunk_size=200, chunk_overlap=50)
    chunks = chunker.chunk_text(sample_text, metadata={"source": "example"})

    print(f"생성된 청크 수: {len(chunks)}\n")

    for i, chunk in enumerate(chunks[:2]):  # 처음 2개만 출력
        print(f"청크 {i + 1}:")
        print(f"  크기: {chunk.metadata['chunk_size']} 문자")
        print(f"  내용 미리보기: {chunk.page_content[:100]}...")
        print()
