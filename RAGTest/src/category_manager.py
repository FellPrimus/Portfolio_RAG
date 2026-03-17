"""
카테고리 관리 모듈
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime


class CategoryManager:
    """카테고리 관리 클래스"""

    def __init__(self, storage_path: str = "./data/categories.json"):
        self.storage_path = storage_path
        self.categories = self._load_categories()

        # 기본 카테고리 추가
        if not self.categories:
            self._init_default_categories()
        else:
            # 기존 카테고리에 llm_model 필드가 없으면 추가 (마이그레이션)
            self._migrate_llm_model_field()

    def _load_categories(self) -> Dict:
        """카테고리 데이터 로드"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"카테고리 로드 실패: {e}")
                return {}
        return {}

    def _save_categories(self):
        """카테고리 데이터 저장"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.categories, f, ensure_ascii=False, indent=2)

    def _migrate_llm_model_field(self):
        """기존 카테고리에 llm_model 필드 추가 (마이그레이션)"""
        updated = False
        for cat_id, cat in self.categories.items():
            if 'llm_model' not in cat:
                cat['llm_model'] = None
                updated = True

        if updated:
            self._save_categories()
            print("✅ 카테고리에 llm_model 필드 추가 완료")

    def _init_default_categories(self):
        """기본 카테고리 초기화"""
        default_categories = [
            {
                "id": "general",
                "name": "일반",
                "description": "분류되지 않은 일반 문서",
                "color": "#6366f1",
                "icon": "📄",
                "llm_model": None  # None = 기본 모델 사용
            },
            {
                "id": "api",
                "name": "API 문서",
                "description": "API 명세서 및 개발 문서",
                "color": "#10b981",
                "icon": "🔌",
                "llm_model": None
            },
            {
                "id": "guide",
                "name": "가이드",
                "description": "사용자 가이드 및 튜토리얼",
                "color": "#f59e0b",
                "icon": "📚",
                "llm_model": None
            },
            {
                "id": "spec",
                "name": "기술 스펙",
                "description": "기술 사양 및 명세",
                "color": "#8b5cf6",
                "icon": "📋",
                "llm_model": None
            }
        ]

        for cat in default_categories:
            cat['created_at'] = datetime.now().isoformat()
            cat['document_count'] = 0
            self.categories[cat['id']] = cat

        self._save_categories()

    def get_all_categories(self) -> List[Dict]:
        """모든 카테고리 조회"""
        return list(self.categories.values())

    def get_category(self, category_id: str) -> Optional[Dict]:
        """특정 카테고리 조회"""
        return self.categories.get(category_id)

    def create_category(self, name: str, description: str = "",
                       color: str = "#6366f1", icon: str = "📁") -> Dict:
        """새 카테고리 생성"""
        # ID 생성 (이름을 소문자로 변환하고 공백을 _로 치환)
        category_id = name.lower().replace(' ', '_').replace('/', '_')

        # 중복 체크
        if category_id in self.categories:
            raise ValueError(f"카테고리 '{name}'이(가) 이미 존재합니다.")

        category = {
            "id": category_id,
            "name": name,
            "description": description,
            "color": color,
            "icon": icon,
            "created_at": datetime.now().isoformat(),
            "document_count": 0
        }

        self.categories[category_id] = category
        self._save_categories()

        return category

    def update_category(self, category_id: str, name: Optional[str] = None,
                       description: Optional[str] = None,
                       color: Optional[str] = None,
                       icon: Optional[str] = None) -> Dict:
        """카테고리 정보 수정"""
        if category_id not in self.categories:
            raise ValueError(f"카테고리 ID '{category_id}'을(를) 찾을 수 없습니다.")

        category = self.categories[category_id]

        if name is not None:
            category['name'] = name
        if description is not None:
            category['description'] = description
        if color is not None:
            category['color'] = color
        if icon is not None:
            category['icon'] = icon

        category['updated_at'] = datetime.now().isoformat()

        self._save_categories()

        return category

    def delete_category(self, category_id: str) -> bool:
        """카테고리 삭제"""
        if category_id not in self.categories:
            return False

        # 기본 카테고리는 삭제 불가
        if category_id == "general":
            raise ValueError("기본 카테고리는 삭제할 수 없습니다.")

        del self.categories[category_id]
        self._save_categories()

        return True

    def increment_document_count(self, category_id: str):
        """카테고리의 문서 수 증가"""
        if category_id in self.categories:
            self.categories[category_id]['document_count'] = \
                self.categories[category_id].get('document_count', 0) + 1
            self._save_categories()

    def decrement_document_count(self, category_id: str):
        """카테고리의 문서 수 감소"""
        if category_id in self.categories:
            count = self.categories[category_id].get('document_count', 0)
            self.categories[category_id]['document_count'] = max(0, count - 1)
            self._save_categories()

    def get_category_stats(self) -> Dict:
        """카테고리 통계"""
        total_categories = len(self.categories)
        total_documents = sum(cat.get('document_count', 0)
                            for cat in self.categories.values())

        return {
            'total_categories': total_categories,
            'total_documents': total_documents,
            'categories': self.get_all_categories()
        }

    def set_category_llm_model(self, category_id: str, model_config: Optional[Dict]) -> Dict:
        """카테고리의 LLM 모델 설정

        Args:
            category_id: 카테고리 ID
            model_config: LLM 모델 설정 (None이면 기본 모델 사용)
                {
                    "provider": "openai",  # 'openai', 'clovax', 'claude' 등
                    "model_name": "gpt-5.1",
                    "temperature": 0.7,
                    "base_url": "https://aac-api.navercorp.com/v1"  # optional
                }

        Returns:
            업데이트된 카테고리 정보
        """
        if category_id not in self.categories:
            raise ValueError(f"카테고리 ID '{category_id}'을(를) 찾을 수 없습니다.")

        self.categories[category_id]['llm_model'] = model_config
        self.categories[category_id]['updated_at'] = datetime.now().isoformat()
        self._save_categories()

        return self.categories[category_id]

    def get_category_llm_model(self, category_id: str) -> Optional[Dict]:
        """카테고리의 LLM 모델 설정 조회

        Args:
            category_id: 카테고리 ID

        Returns:
            LLM 모델 설정 (None이면 기본 모델 사용)
        """
        if category_id not in self.categories:
            return None

        return self.categories[category_id].get('llm_model')


if __name__ == "__main__":
    # 테스트
    manager = CategoryManager()
    print("=== 카테고리 목록 ===")
    for cat in manager.get_all_categories():
        print(f"{cat['icon']} {cat['name']}: {cat['description']}")
