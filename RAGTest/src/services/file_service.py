"""
파일 관리 서비스

파일 업로드, 메타데이터 관리 등의 비즈니스 로직을 담당합니다.
"""

import os
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
from werkzeug.utils import secure_filename


def safe_filename(filename: str) -> str:
    """
    한글을 포함한 파일명을 안전하게 처리

    - 위험한 문자만 제거하고 한글, 영문, 숫자, 공백, 일부 특수문자는 유지
    - Path traversal 공격 방지 (../, ..\\ 등)
    - 파일명 길이 제한 (255자)

    Args:
        filename: 원본 파일명

    Returns:
        안전하게 처리된 파일명
    """
    if not filename:
        return "unnamed_file"

    # Path traversal 공격 방지: 경로 구분자 제거
    filename = os.path.basename(filename)

    # 위험한 문자 제거: / \ : * ? " < > |
    # 한글, 영문, 숫자, 공백, 하이픈, 언더스코어, 괄호, 점은 유지
    filename = re.sub(r'[/\\:*?"<>|]', '', filename)

    # 연속된 공백을 하나로
    filename = re.sub(r'\s+', ' ', filename)

    # 앞뒤 공백 제거
    filename = filename.strip()

    # 파일명이 비어있으면 기본값
    if not filename:
        return "unnamed_file"

    # 파일명 길이 제한 (Windows 최대 경로 길이 고려)
    if len(filename) > 255:
        # 확장자 보존하면서 자르기
        name, ext = os.path.splitext(filename)
        max_name_len = 255 - len(ext)
        filename = name[:max_name_len] + ext

    return filename


class FileService:
    """파일 업로드 및 관리 서비스"""

    def __init__(self, upload_folder: str = "./uploads",
                 metadata_path: str = "./data/file_metadata.json",
                 category_manager=None):
        """
        Args:
            upload_folder: 파일 업로드 디렉토리
            metadata_path: 메타데이터 JSON 파일 경로
            category_manager: CategoryManager 인스턴스
        """
        self.upload_folder = upload_folder
        self.metadata_path = metadata_path
        self.category_manager = category_manager
        self.file_metadata = self._load_metadata()

        # 업로드 폴더 생성
        os.makedirs(upload_folder, exist_ok=True)

    def _load_metadata(self) -> Dict:
        """파일 메타데이터 로드"""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"메타데이터 로드 실패: {e}")
                return {}
        return {}

    def _save_metadata(self):
        """파일 메타데이터 저장"""
        os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self.file_metadata, f, ensure_ascii=False, indent=2)

    def upload_file(self, file, category_id: str = 'general') -> Dict:
        """
        파일 업로드

        Args:
            file: Werkzeug FileStorage 객체
            category_id: 카테고리 ID

        Returns:
            {'success': bool, 'filename': str} 또는 {'success': False, 'error': str}
        """
        try:
            if not file or not file.filename:
                return {'success': False, 'error': '파일이 제공되지 않았습니다.'}

            # 파일명 보안 처리 (한글 지원)
            filename = safe_filename(file.filename)
            filepath = os.path.join(self.upload_folder, filename)

            # 파일 저장
            file.save(filepath)

            # 카테고리 정보 조회
            category_info = None
            if self.category_manager:
                category = self.category_manager.get_category(category_id)
                if category:
                    category_info = {
                        'id': category_id,
                        'name': category['name'],
                        'color': category['color'],
                        'icon': category['icon']
                    }

            # 메타데이터 생성
            self.file_metadata[filename] = {
                'filename': filename,
                'path': filepath,
                'size': os.path.getsize(filepath),
                'category_id': category_id,
                'category': category_info,
                'uploaded_at': datetime.now().isoformat()
            }

            self._save_metadata()

            return {
                'success': True,
                'filename': filename,
                'path': filepath
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_files(self) -> List[Dict]:
        """
        파일 목록 조회

        Returns:
            파일 메타데이터 리스트
        """
        files = []
        for filename, metadata in self.file_metadata.items():
            # 파일 경로를 여러 키에서 찾기 (하위 호환성)
            file_path = metadata.get('path') or metadata.get('file_path') or metadata.get('filepath')

            # 파일 경로가 없으면 건너뛰기
            if not file_path:
                continue

            # URL인 경우 (크롤링된 문서) 건너뛰기
            if isinstance(file_path, str) and (file_path.startswith('http://') or file_path.startswith('https://')):
                continue

            # 파일이 실제로 존재하는지 확인
            if os.path.exists(file_path):
                # 파일 타입 추론
                ext = os.path.splitext(filename)[1].lower()
                file_type = self._get_file_type(ext)

                # 카테고리 정보 업데이트
                category_id = metadata.get('category_id', 'general')
                category_info = None
                if self.category_manager:
                    category = self.category_manager.get_category(category_id)
                    if category:
                        category_info = {
                            'id': category_id,
                            'name': category['name'],
                            'color': category['color'],
                            'icon': category['icon']
                        }

                files.append({
                    'name': filename,
                    'path': file_path,
                    'size': metadata.get('size', 0),
                    'type': file_type,
                    'category': category_info,
                    'uploaded_at': metadata.get('uploaded_at', 'Unknown')
                })

        return files

    def delete_file(self, filename: str) -> Dict:
        """
        파일 삭제

        Args:
            filename: 삭제할 파일명

        Returns:
            {'success': bool, 'message': str}
        """
        try:
            if filename not in self.file_metadata:
                return {
                    'success': False,
                    'error': '파일을 찾을 수 없습니다.'
                }

            # 실제 파일 삭제
            filepath = self.file_metadata[filename]['path']
            if os.path.exists(filepath):
                os.remove(filepath)

            # 메타데이터 삭제
            del self.file_metadata[filename]
            self._save_metadata()

            return {
                'success': True,
                'message': f'파일 "{filename}"이(가) 삭제되었습니다.'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def update_category(self, filename: str, category_id: str) -> Dict:
        """
        파일의 카테고리 변경

        Args:
            filename: 파일명
            category_id: 새 카테고리 ID

        Returns:
            {'success': bool}
        """
        try:
            if filename not in self.file_metadata:
                return {
                    'success': False,
                    'error': '파일을 찾을 수 없습니다.'
                }

            # 카테고리 정보 조회
            category_info = None
            if self.category_manager:
                category = self.category_manager.get_category(category_id)
                if category:
                    category_info = {
                        'id': category_id,
                        'name': category['name'],
                        'color': category['color'],
                        'icon': category['icon']
                    }

            # 메타데이터 업데이트
            self.file_metadata[filename]['category_id'] = category_id
            self.file_metadata[filename]['category'] = category_info
            self.file_metadata[filename]['updated_at'] = datetime.now().isoformat()

            self._save_metadata()

            return {'success': True}

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_file_paths(self, filenames: Optional[List[str]] = None) -> List[str]:
        """
        파일 경로 목록 반환

        Args:
            filenames: 특정 파일들의 경로만 가져올 경우 (None이면 전체)

        Returns:
            파일 경로 리스트
        """
        if filenames is None:
            return [meta['path'] for meta in self.file_metadata.values()]
        else:
            paths = []
            for filename in filenames:
                if filename in self.file_metadata:
                    paths.append(self.file_metadata[filename]['path'])
            return paths

    @staticmethod
    def _get_file_type(ext: str) -> str:
        """파일 확장자로 타입 추론"""
        type_map = {
            '.pdf': 'PDF',
            '.txt': 'Text',
            '.md': 'Markdown',
            '.html': 'HTML',
            '.htm': 'HTML',
            '.doc': 'Word',
            '.docx': 'Word',
            '.xls': 'Excel',
            '.xlsx': 'Excel',
            '.csv': 'CSV',
            '.json': 'JSON'
        }
        return type_map.get(ext, 'Unknown')
