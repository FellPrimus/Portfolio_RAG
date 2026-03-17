"""
문서 로더 모듈

웹, HTML 파일 등 다양한 소스에서 문서를 로드하는 로더들을 제공합니다.
지원 형식: HTML, PDF, Excel (.xlsx, .xls), Word (.docx)
"""

from .web_loader import WebDocumentLoader, HTMLFileLoader
from .pdf_loader import PDFLoader
from .excel_loader import ExcelLoader
from .word_loader import WordLoader
from .document_loader import UniversalDocumentLoader
from .playwright_crawler import PlaywrightCrawler, GenericWebCrawler

__all__ = [
    'WebDocumentLoader',
    'HTMLFileLoader',
    'PDFLoader',
    'ExcelLoader',
    'WordLoader',
    'UniversalDocumentLoader',
    'PlaywrightCrawler',
    'GenericWebCrawler'
]
