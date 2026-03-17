"""
텍스트 처리 유틸리티

HTML 변환, 텍스트 정제 등을 담당합니다.
"""

import re
from typing import List
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """텍스트에서 제어 문자 제거"""
    if isinstance(text, str):
        return re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)
    return text


def convert_table_to_markdown(table_element) -> str:
    """HTML 테이블을 마크다운 형식으로 변환"""
    rows = table_element.find_all("tr")
    if not rows:
        return ""

    markdown_lines = []
    first_row_th = rows[0].find_all("th")

    if first_row_th:
        headers = [cell.get_text(strip=True) for cell in first_row_th]
        markdown_lines.append("| " + " | ".join(headers) + " |")
        markdown_lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            cell_text = [cell.get_text(strip=True) for cell in cells]
            markdown_lines.append("| " + " | ".join(cell_text) + " |")
    else:
        first_row_cells = rows[0].find_all(["td", "th"])
        headers = [cell.get_text(strip=True) for cell in first_row_cells]
        markdown_lines.append("| " + " | ".join(headers) + " |")
        markdown_lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            cell_text = [cell.get_text(strip=True) for cell in cells]
            markdown_lines.append("| " + " | ".join(cell_text) + " |")

    return "\n".join(markdown_lines)


def convert_list_to_markdown(list_element, level: int = 1) -> str:
    """HTML 리스트를 마크다운 형식으로 변환"""
    lines = []
    for li in list_element.find_all("li", recursive=False):
        li_text = li.get_text(separator=" ", strip=True)
        bullet = "*" * (level + 1)
        lines.append(bullet + " " + li_text)
        nested_list = li.find(["ul", "ol"], recursive=False)
        if nested_list:
            lines.append(convert_list_to_markdown(nested_list, level + 1))
    return "\n\n".join(lines)


def extract_section_content(full_html: str) -> List[dict]:
    """
    HTML에서 섹션별 콘텐츠 추출

    Returns:
        List[Dict]: [{'heading': 'h2 제목', 'content': '내용'}, ...]
    """
    soup = BeautifulSoup(full_html, 'html.parser')
    sections = []
    current_section = None

    # 문서 제목 가져오기
    article_head = soup.select_one('article h1')
    article_title = article_head.get_text(strip=True) if article_head else ''

    # article 내의 모든 요소 순회
    content_elements = soup.select('article > *')

    # 최상단 소개 섹션 시작
    current_section = {
        'heading': article_title,
        'content': ''
    }

    for element in content_elements:
        # 새로운 상위 카테고리(h2)를 만나면 이전 섹션 저장
        if element.name == 'h2':
            if current_section and current_section['content'].strip():
                sections.append(current_section)
            current_section = {'heading': element.get_text(strip=True), 'content': ''}
        else:
            if element.name == 'table':
                markdown_table = convert_table_to_markdown(element)
                current_section['content'] += "\n" + markdown_table
            elif element.name in ['ul', 'ol']:
                markdown_list = convert_list_to_markdown(element, level=1)
                current_section['content'] += "\n" + markdown_list
            else:
                text_content = element.get_text(strip=True)
                if text_content:
                    if element.name == 'h3':
                        current_section['content'] += f"\n\n**{text_content}**"
                    else:
                        current_section['content'] += "\n" + text_content

    # 마지막 섹션 추가
    if current_section and current_section['content'].strip():
        sections.append(current_section)

    return sections
