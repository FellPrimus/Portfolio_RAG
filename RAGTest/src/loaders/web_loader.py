"""
웹/HTML 문서 로더

이 모듈은 웹 페이지를 로드하고 HTML을 파싱하여 텍스트를 추출합니다.
LangChain의 문서 형식과 호환되도록 구현되었습니다.
"""

import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from langchain_core.documents import Document  # LangChain 1.0+ import 경로 변경
import html2text


class WebDocumentLoader:
    """
    웹 페이지에서 텍스트를 추출하는 문서 로더

    주요 기능:
    - URL에서 HTML 콘텐츠 가져오기
    - HTML을 텍스트로 변환
    - 메타데이터 추출 (제목, URL 등)
    - LangChain Document 형식으로 반환
    """

    def __init__(
        self,
        headers: Optional[dict] = None,
        timeout: int = 10,
        convert_to_markdown: bool = False
    ):
        """
        WebDocumentLoader 초기화

        Args:
            headers (dict, optional): HTTP 요청 헤더. 기본값은 User-Agent 포함
            timeout (int): 요청 타임아웃 (초). 기본값 10초
            convert_to_markdown (bool): HTML을 마크다운으로 변환 여부. 기본값 False
        """
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.timeout = timeout
        self.convert_to_markdown = convert_to_markdown
        self.html_converter = html2text.HTML2Text() if convert_to_markdown else None

        if self.html_converter:
            # 마크다운 변환 설정
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = False
            self.html_converter.body_width = 0  # 줄바꿈 제한 없음

    def load(self, url: str) -> List[Document]:
        """
        단일 URL에서 문서를 로드합니다.

        Args:
            url (str): 로드할 웹 페이지 URL

        Returns:
            List[Document]: LangChain Document 객체 리스트 (단일 문서)

        Raises:
            requests.RequestException: HTTP 요청 실패 시

        Example:
            >>> loader = WebDocumentLoader()
            >>> docs = loader.load("https://example.com")
            >>> print(docs[0].page_content[:100])
        """
        try:
            # HTTP GET 요청
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()  # 4xx, 5xx 에러 체크
            response.encoding = response.apparent_encoding  # 인코딩 자동 감지

            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')

            # 메타데이터 추출
            metadata = self._extract_metadata(soup, url)

            # 텍스트 추출
            text_content = self._extract_text(soup, response.text)

            # LangChain Document 생성
            document = Document(
                page_content=text_content,
                metadata=metadata
            )

            return [document]

        except requests.RequestException as e:
            raise Exception(f"URL 로드 실패: {url}\n에러: {str(e)}")

    def load_multiple(self, urls: List[str]) -> List[Document]:
        """
        여러 URL에서 문서를 로드합니다.

        Args:
            urls (List[str]): 로드할 URL 리스트

        Returns:
            List[Document]: 모든 URL에서 로드된 Document 리스트

        Example:
            >>> loader = WebDocumentLoader()
            >>> urls = ["https://example1.com", "https://example2.com"]
            >>> docs = loader.load_multiple(urls)
            >>> print(f"총 {len(docs)}개 문서 로드됨")
        """
        all_documents = []

        for url in urls:
            try:
                documents = self.load(url)
                all_documents.extend(documents)
                print(f"✓ 로드 완료: {url}")
            except Exception as e:
                print(f"✗ 로드 실패: {url} - {str(e)}")
                continue

        return all_documents

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """
        HTML에서 메타데이터를 추출합니다.

        Args:
            soup (BeautifulSoup): 파싱된 HTML
            url (str): 원본 URL

        Returns:
            dict: 메타데이터 딕셔너리
        """
        metadata = {
            'source': url,
            'type': 'web_page'
        }

        # 페이지 제목 추출
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)

        # 메타 태그에서 정보 추출
        meta_description = soup.find('meta', attrs={'name': 'description'})
        if meta_description and meta_description.get('content'):
            metadata['description'] = meta_description['content']

        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            metadata['keywords'] = meta_keywords['content']

        # Open Graph 메타 태그
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            metadata['og_title'] = og_title['content']

        return metadata

    def _extract_text(self, soup: BeautifulSoup, html: str) -> str:
        """
        HTML에서 텍스트를 추출합니다.

        Args:
            soup (BeautifulSoup): 파싱된 HTML
            html (str): 원본 HTML 문자열

        Returns:
            str: 추출된 텍스트
        """
        # 스크립트와 스타일 태그 제거
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
            tag.decompose()

        if self.convert_to_markdown:
            # HTML을 마크다운으로 변환
            return self.html_converter.handle(html)
        else:
            # 순수 텍스트만 추출
            text = soup.get_text(separator='\n', strip=True)

            # 연속된 빈 줄 제거
            lines = [line for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)


class HTMLFileLoader:
    """
    로컬 HTML 파일을 로드하는 문서 로더

    주요 기능:
    - 로컬 HTML 파일 읽기
    - HTML 파싱 및 텍스트 추출
    - 파일 경로를 메타데이터로 저장
    """

    def __init__(self, convert_to_markdown: bool = False):
        """
        HTMLFileLoader 초기화

        Args:
            convert_to_markdown (bool): HTML을 마크다운으로 변환 여부
        """
        self.convert_to_markdown = convert_to_markdown
        self.html_converter = html2text.HTML2Text() if convert_to_markdown else None

        if self.html_converter:
            self.html_converter.ignore_links = False
            self.html_converter.ignore_images = False
            self.html_converter.body_width = 0

    def load(self, file_path: str, encoding: str = 'utf-8') -> List[Document]:
        """
        로컬 HTML 파일을 로드합니다.

        Args:
            file_path (str): HTML 파일 경로
            encoding (str): 파일 인코딩. 기본값 'utf-8'

        Returns:
            List[Document]: LangChain Document 객체 리스트

        Example:
            >>> loader = HTMLFileLoader()
            >>> docs = loader.load("./data/sample.html")
            >>> print(docs[0].metadata['source'])
        """
        try:
            # 파일 읽기
            with open(file_path, 'r', encoding=encoding) as f:
                html_content = f.read()

            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')

            # 메타데이터 추출
            metadata = self._extract_metadata(soup, file_path)

            # 텍스트 추출
            text_content = self._extract_text(soup, html_content)

            # Document 생성
            document = Document(
                page_content=text_content,
                metadata=metadata
            )

            return [document]

        except Exception as e:
            raise Exception(f"파일 로드 실패: {file_path}\n에러: {str(e)}")

    def _extract_metadata(self, soup: BeautifulSoup, file_path: str) -> dict:
        """HTML에서 메타데이터 추출"""
        metadata = {
            'source': file_path,
            'type': 'html_file'
        }

        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text(strip=True)

        return metadata

    def _extract_text(self, soup: BeautifulSoup, html: str) -> str:
        """HTML에서 텍스트 추출"""
        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
            tag.decompose()

        if self.convert_to_markdown:
            return self.html_converter.handle(html)
        else:
            text = soup.get_text(separator='\n', strip=True)
            lines = [line for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)


# 사용 예제
if __name__ == "__main__":
    # 웹 페이지 로드 예제
    print("=== 웹 문서 로더 예제 ===\n")

    web_loader = WebDocumentLoader()

    # 단일 URL 로드
    try:
        docs = web_loader.load("https://example.com")
        print(f"문서 로드 성공!")
        print(f"제목: {docs[0].metadata.get('title', 'N/A')}")
        print(f"내용 미리보기: {docs[0].page_content[:200]}...")
    except Exception as e:
        print(f"에러: {e}")
