"""
폴더 관리 모듈

문서를 계층적으로 정리하기 위한 폴더 관리 기능을 제공합니다.
"""
import json
import os
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse


class FolderManager:
    """폴더 관리 클래스"""

    # URL 도메인 기반 자동 폴더 매핑
    URL_FOLDER_MAPPING = {
        'guide.ncloud-docs.com': 'ncp-guide',
        'guide-fin.ncloud-docs.com': 'ncp-fin-guide',
        'guide-gov.ncloud-docs.com': 'ncp-gov-guide',
    }

    # 시스템 기본 폴더 정의
    SYSTEM_FOLDERS = {
        'ncp-guide': {
            'id': 'ncp-guide',
            'name': 'NCP Guide',
            'parent_id': None,
            'children': [],
            'color': '#00c73c',
            'icon': 'cloud',
            'is_system': True
        },
        'ncp-fin-guide': {
            'id': 'ncp-fin-guide',
            'name': 'NCP-FIN Guide',
            'parent_id': None,
            'children': [],
            'color': '#0068b7',
            'icon': 'building',
            'is_system': True
        },
        'ncp-gov-guide': {
            'id': 'ncp-gov-guide',
            'name': 'NCP-GOV Guide',
            'parent_id': None,
            'children': [],
            'color': '#e60012',
            'icon': 'landmark',
            'is_system': True
        }
    }

    def __init__(self, storage_path: str = "./data/folders.json"):
        self.storage_path = storage_path
        self.data = self._load_data()
        self._migrate_url_to_filename()  # URL → 파일명 마이그레이션
        self.ensure_system_folders()

    def _load_data(self) -> Dict:
        """폴더 데이터 로드"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"폴더 데이터 로드 실패: {e}")
                return self._get_default_data()
        return self._get_default_data()

    def _get_default_data(self) -> Dict:
        """기본 데이터 구조 반환"""
        return {
            'folders': {},
            'document_folder_map': {},
            'root_folders': []
        }

    def _save_data(self):
        """폴더 데이터 저장"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def _migrate_url_to_filename(self):
        """URL 기반 문서 ID를 파일명 기반으로 마이그레이션

        기존에 폴더 매핑이 URL 전체로 저장된 경우,
        벡터DB 메타데이터와 일치하도록 파일명만 추출하여 변환합니다.
        """
        if 'document_folder_map' not in self.data:
            return

        migrated = False
        new_map = {}

        for doc_id, folder_id in self.data['document_folder_map'].items():
            # URL 형식인지 확인 (http:// 또는 https://로 시작)
            if doc_id.startswith('http://') or doc_id.startswith('https://'):
                # URL에서 파일명만 추출
                parsed_url = urlparse(doc_id)
                filename = parsed_url.path.split('/')[-1]
                if filename:
                    new_map[filename] = folder_id
                    migrated = True
                    print(f"[마이그레이션] '{doc_id}' → '{filename}'")
                else:
                    new_map[doc_id] = folder_id
            else:
                new_map[doc_id] = folder_id

        if migrated:
            self.data['document_folder_map'] = new_map
            self._save_data()
            print(f"[마이그레이션] 문서 ID 변환 완료")

    def ensure_system_folders(self):
        """시스템 기본 폴더 생성 (없으면 생성)"""
        updated = False

        for folder_id, folder_def in self.SYSTEM_FOLDERS.items():
            if folder_id not in self.data['folders']:
                folder = folder_def.copy()
                folder['created_at'] = datetime.now().isoformat()
                self.data['folders'][folder_id] = folder

                if folder_id not in self.data['root_folders']:
                    self.data['root_folders'].append(folder_id)

                updated = True

        if updated:
            self._save_data()

    # ==================== CRUD 메서드 ====================

    def create_folder(
        self,
        name: str,
        parent_id: Optional[str] = None,
        color: str = '#6366f1',
        icon: str = 'folder'
    ) -> Dict:
        """새 폴더 생성

        Args:
            name: 폴더 이름
            parent_id: 부모 폴더 ID (None이면 루트)
            color: 폴더 색상
            icon: 폴더 아이콘

        Returns:
            생성된 폴더 정보
        """
        folder_id = str(uuid.uuid4())[:8]

        folder = {
            'id': folder_id,
            'name': name,
            'parent_id': parent_id,
            'children': [],
            'created_at': datetime.now().isoformat(),
            'color': color,
            'icon': icon,
            'is_system': False
        }

        self.data['folders'][folder_id] = folder

        # 부모 폴더에 자식으로 추가
        if parent_id and parent_id in self.data['folders']:
            self.data['folders'][parent_id]['children'].append(folder_id)
        else:
            # 루트 폴더로 추가
            self.data['root_folders'].append(folder_id)

        self._save_data()
        return folder

    def find_child_by_name(self, parent_id: Optional[str], name: str) -> Optional[Dict]:
        """부모 폴더 아래에서 이름으로 자식 폴더 찾기

        Args:
            parent_id: 부모 폴더 ID (None이면 루트 레벨)
            name: 찾을 폴더 이름

        Returns:
            찾은 폴더 또는 None
        """
        if parent_id:
            parent = self.data['folders'].get(parent_id)
            if not parent:
                return None
            children_ids = parent.get('children', [])
        else:
            children_ids = self.data.get('root_folders', [])

        for child_id in children_ids:
            child = self.data['folders'].get(child_id)
            if child and child.get('name') == name:
                return child
        return None

    def get_or_create_folder_path(
        self,
        path: List[str],
        base_folder_id: Optional[str] = None
    ) -> str:
        """폴더 경로를 따라 폴더를 생성하거나 기존 폴더 반환

        Args:
            path: 폴더 경로 리스트 (예: ['Networking', 'VPC'])
            base_folder_id: 시작 폴더 ID (None이면 루트에서 시작)

        Returns:
            최종 폴더 ID
        """
        current_parent_id = base_folder_id

        for folder_name in path:
            existing = self.find_child_by_name(current_parent_id, folder_name)
            if existing:
                current_parent_id = existing['id']
            else:
                new_folder = self.create_folder(
                    name=folder_name,
                    parent_id=current_parent_id,
                    icon='folder'
                )
                current_parent_id = new_folder['id']

        return current_parent_id

    def get_folder(self, folder_id: str) -> Optional[Dict]:
        """특정 폴더 조회"""
        return self.data['folders'].get(folder_id)

    def get_all_folders(self) -> List[Dict]:
        """모든 폴더 조회"""
        return list(self.data['folders'].values())

    def update_folder(
        self,
        folder_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
        icon: Optional[str] = None
    ) -> Dict:
        """폴더 정보 수정

        Args:
            folder_id: 폴더 ID
            name: 새 이름 (None이면 변경 안함)
            color: 새 색상
            icon: 새 아이콘

        Returns:
            업데이트된 폴더 정보
        """
        if folder_id not in self.data['folders']:
            raise ValueError(f"폴더 ID '{folder_id}'을(를) 찾을 수 없습니다.")

        folder = self.data['folders'][folder_id]

        if name is not None:
            folder['name'] = name
        if color is not None:
            folder['color'] = color
        if icon is not None:
            folder['icon'] = icon

        folder['updated_at'] = datetime.now().isoformat()

        self._save_data()
        return folder

    def delete_folder(self, folder_id: str, recursive: bool = False) -> bool:
        """폴더 삭제

        Args:
            folder_id: 삭제할 폴더 ID
            recursive: True면 하위 폴더 및 문서 매핑도 삭제

        Returns:
            삭제 성공 여부
        """
        if folder_id not in self.data['folders']:
            return False

        folder = self.data['folders'][folder_id]

        # 시스템 폴더는 삭제 불가
        if folder.get('is_system', False):
            raise ValueError("시스템 폴더는 삭제할 수 없습니다.")

        # 하위 폴더가 있는 경우
        if folder['children'] and not recursive:
            raise ValueError("하위 폴더가 있습니다. recursive=True로 설정하세요.")

        # 재귀적 삭제
        if recursive:
            for child_id in folder['children'][:]:
                self.delete_folder(child_id, recursive=True)

        # 문서 매핑 제거
        docs_to_remove = [
            doc_id for doc_id, fid in self.data['document_folder_map'].items()
            if fid == folder_id
        ]
        for doc_id in docs_to_remove:
            del self.data['document_folder_map'][doc_id]

        # 부모 폴더에서 자식 제거
        parent_id = folder.get('parent_id')
        if parent_id and parent_id in self.data['folders']:
            parent = self.data['folders'][parent_id]
            if folder_id in parent['children']:
                parent['children'].remove(folder_id)
        elif folder_id in self.data['root_folders']:
            self.data['root_folders'].remove(folder_id)

        # 폴더 삭제
        del self.data['folders'][folder_id]

        self._save_data()
        return True

    def move_folder(self, folder_id: str, new_parent_id: Optional[str]) -> Dict:
        """폴더 이동

        Args:
            folder_id: 이동할 폴더 ID
            new_parent_id: 새 부모 폴더 ID (None이면 루트로)

        Returns:
            이동된 폴더 정보
        """
        if folder_id not in self.data['folders']:
            raise ValueError(f"폴더 ID '{folder_id}'을(를) 찾을 수 없습니다.")

        folder = self.data['folders'][folder_id]
        old_parent_id = folder.get('parent_id')

        # 순환 참조 체크
        if new_parent_id:
            if new_parent_id == folder_id:
                raise ValueError("폴더를 자기 자신으로 이동할 수 없습니다.")
            if self._is_descendant(new_parent_id, folder_id):
                raise ValueError("폴더를 자신의 하위 폴더로 이동할 수 없습니다.")

        # 기존 부모에서 제거
        if old_parent_id and old_parent_id in self.data['folders']:
            parent = self.data['folders'][old_parent_id]
            if folder_id in parent['children']:
                parent['children'].remove(folder_id)
        elif folder_id in self.data['root_folders']:
            self.data['root_folders'].remove(folder_id)

        # 새 부모에 추가
        folder['parent_id'] = new_parent_id
        if new_parent_id and new_parent_id in self.data['folders']:
            self.data['folders'][new_parent_id]['children'].append(folder_id)
        else:
            self.data['root_folders'].append(folder_id)

        folder['updated_at'] = datetime.now().isoformat()

        self._save_data()
        return folder

    def _is_descendant(self, folder_id: str, potential_ancestor_id: str) -> bool:
        """folder_id가 potential_ancestor_id의 자손인지 확인"""
        folder = self.data['folders'].get(folder_id)
        if not folder:
            return False

        if folder_id == potential_ancestor_id:
            return True

        for child_id in folder.get('children', []):
            if self._is_descendant(child_id, potential_ancestor_id):
                return True

        return False

    # ==================== 문서-폴더 매핑 ====================

    def assign_document_to_folder(self, doc_id: str, folder_id: str) -> bool:
        """문서를 폴더에 할당

        Args:
            doc_id: 문서 ID (파일명 또는 URL)
            folder_id: 폴더 ID

        Returns:
            성공 여부
        """
        if folder_id not in self.data['folders']:
            return False

        self.data['document_folder_map'][doc_id] = folder_id
        self._save_data()
        return True

    def remove_document_from_folder(self, doc_id: str) -> bool:
        """문서를 폴더에서 제거

        Args:
            doc_id: 문서 ID

        Returns:
            성공 여부
        """
        if doc_id not in self.data['document_folder_map']:
            return False

        del self.data['document_folder_map'][doc_id]
        self._save_data()
        return True

    def get_document_folder(self, doc_id: str) -> Optional[str]:
        """문서가 속한 폴더 ID 조회

        Args:
            doc_id: 문서 ID

        Returns:
            폴더 ID (없으면 None)
        """
        return self.data['document_folder_map'].get(doc_id)

    def get_documents_in_folder(
        self,
        folder_id: str,
        include_subfolders: bool = False
    ) -> List[str]:
        """폴더에 속한 문서 목록 조회

        Args:
            folder_id: 폴더 ID
            include_subfolders: 하위 폴더의 문서도 포함할지

        Returns:
            문서 ID 목록
        """
        folder_ids = {folder_id}

        if include_subfolders:
            folder_ids.update(self._get_all_descendant_ids(folder_id))

        documents = [
            doc_id for doc_id, fid in self.data['document_folder_map'].items()
            if fid in folder_ids
        ]

        return documents

    def _get_all_descendant_ids(self, folder_id: str) -> set:
        """폴더의 모든 하위 폴더 ID 조회"""
        descendants = set()
        folder = self.data['folders'].get(folder_id)

        if folder:
            for child_id in folder.get('children', []):
                descendants.add(child_id)
                descendants.update(self._get_all_descendant_ids(child_id))

        return descendants

    # ==================== 트리 조회 ====================

    def get_folder_tree(self) -> List[Dict]:
        """전체 폴더 트리 구조 조회

        Returns:
            트리 구조의 폴더 목록
        """
        def build_tree(folder_id: str) -> Dict:
            folder = self.data['folders'].get(folder_id, {}).copy()
            folder['children_data'] = [
                build_tree(child_id)
                for child_id in folder.get('children', [])
            ]
            # 폴더 내 문서 목록 및 수 계산
            folder['documents'] = self.get_documents_in_folder(folder_id, include_subfolders=False)
            folder['document_count'] = len(folder['documents'])
            return folder

        tree = []
        for root_id in self.data['root_folders']:
            if root_id in self.data['folders']:
                tree.append(build_tree(root_id))

        return tree

    def get_folder_path(self, folder_id: str) -> List[Dict]:
        """폴더의 상위 경로 조회

        Args:
            folder_id: 폴더 ID

        Returns:
            루트부터 해당 폴더까지의 경로 목록
        """
        path = []
        current_id = folder_id

        while current_id:
            folder = self.data['folders'].get(current_id)
            if not folder:
                break
            path.insert(0, {
                'id': folder['id'],
                'name': folder['name']
            })
            current_id = folder.get('parent_id')

        return path

    # ==================== URL 기반 자동 폴더 할당 ====================

    def get_folder_for_url(self, url: str) -> Optional[str]:
        """URL 도메인에 따른 폴더 ID 반환

        Args:
            url: 크롤링 URL

        Returns:
            폴더 ID (매핑이 없으면 None)
        """
        domain = urlparse(url).netloc

        folder_id = self.URL_FOLDER_MAPPING.get(domain)
        if folder_id:
            self.ensure_system_folders()
            return folder_id

        return None

    def get_unassigned_documents(self, all_doc_ids: List[str]) -> List[str]:
        """폴더에 할당되지 않은 문서 목록

        Args:
            all_doc_ids: 전체 문서 ID 목록

        Returns:
            폴더에 할당되지 않은 문서 ID 목록
        """
        assigned = set(self.data['document_folder_map'].keys())
        return [doc_id for doc_id in all_doc_ids if doc_id not in assigned]

    def get_folder_stats(self) -> Dict:
        """폴더 통계"""
        total_folders = len(self.data['folders'])
        system_folders = sum(
            1 for f in self.data['folders'].values()
            if f.get('is_system', False)
        )
        user_folders = total_folders - system_folders
        total_mappings = len(self.data['document_folder_map'])

        return {
            'total_folders': total_folders,
            'system_folders': system_folders,
            'user_folders': user_folders,
            'total_document_mappings': total_mappings
        }


if __name__ == "__main__":
    # 테스트
    manager = FolderManager()
    print("=== 폴더 트리 ===")
    for folder in manager.get_folder_tree():
        print(f"- {folder['name']} ({folder['id']})")
        for child in folder.get('children_data', []):
            print(f"  - {child['name']} ({child['id']})")
