"""
콘텐츠 추출 모듈

웹 페이지에서 메인 콘텐츠를 추출합니다.
"""

from typing import List, Dict
from bs4 import BeautifulSoup

from src.loaders.crawler.utils import (
    convert_table_to_markdown,
    convert_list_to_markdown,
    clean_text
)


class ContentExtractor:
    """웹 페이지 콘텐츠 추출기"""

    def extract_main_content(self, html: str) -> str:
        """
        HTML에서 메인 콘텐츠 추출 (범용)

        일반적인 웹페이지 구조에서 주요 콘텐츠를 추출합니다.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 불필요한 요소 제거
        for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            element.decompose()

        # 메인 콘텐츠 영역 찾기
        main_content = self._find_main_content(soup)

        if not main_content:
            return ""

        # 텍스트 추출 및 정리
        content_parts = []

        # 제목 추출
        title = soup.find('h1')
        if title:
            content_parts.append(f"# {title.get_text(strip=True)}\n")

        # 본문 추출
        content_parts.extend(self._extract_body_content(main_content))

        return "\n".join(content_parts)

    def _find_main_content(self, soup: BeautifulSoup):
        """메인 콘텐츠 영역 찾기"""
        # 1. <main> 태그
        main_content = soup.find('main')

        # 2. role="main" 속성
        if not main_content:
            main_content = soup.find(attrs={'role': 'main'})

        # 3. id나 class에 'content', 'main', 'article' 포함
        if not main_content:
            for selector in ['#content', '#main', '#article', '.content', '.main', '.article']:
                main_content = soup.select_one(selector)
                if main_content:
                    break

        # 4. <article> 태그
        if not main_content:
            articles = soup.find_all('article')
            if articles:
                main_content = articles[0]

        # 5. 찾지 못하면 body 전체 사용
        if not main_content:
            main_content = soup.find('body')

        return main_content

    def _extract_body_content(self, main_content) -> List[str]:
        """본문 콘텐츠 추출"""
        content_parts = []
        elements = main_content.find_all(
            ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'table', 'pre', 'blockquote']
        )

        for element in elements:
            part = self._process_element(element)
            if part:
                content_parts.append(part)

        return content_parts

    def _process_element(self, element) -> str:
        """개별 요소 처리"""
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            heading_marker = '#' * level
            return f"\n{heading_marker} {element.get_text(strip=True)}\n"

        elif element.name == 'p':
            text = element.get_text(strip=True)
            return text + "\n" if text else ""

        elif element.name == 'table':
            markdown_table = convert_table_to_markdown(element)
            return "\n" + markdown_table + "\n" if markdown_table else ""

        elif element.name in ['ul', 'ol']:
            markdown_list = convert_list_to_markdown(element, level=1)
            return "\n" + markdown_list + "\n" if markdown_list else ""

        elif element.name == 'pre':
            code = element.get_text(strip=True)
            return f"\n```\n{code}\n```\n" if code else ""

        elif element.name == 'blockquote':
            quote = element.get_text(strip=True)
            return f"\n> {quote}\n" if quote else ""

        return ""

    def extract_ncloud_content(self, html: str, service_name: str = "") -> Dict:
        """
        NCloud 문서 페이지 콘텐츠 추출

        Args:
            html: 페이지 HTML
            service_name: 서비스 이름

        Returns:
            {'title': str, 'content': str, 'sections': list}
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 제목 추출
        title_elem = soup.select_one('article h1')
        title = title_elem.get_text(strip=True) if title_elem else service_name

        # 섹션별 콘텐츠 추출
        from src.loaders.crawler.utils import extract_section_content
        sections = extract_section_content(html)

        # 전체 콘텐츠
        content_parts = [f"# {title}\n\n"]
        for section in sections:
            if section['heading']:
                content_parts.append(f"## {section['heading']}\n")
            content_parts.append(section['content'] + "\n\n")

        return {
            'title': title,
            'content': ''.join(content_parts),
            'sections': sections
        }
