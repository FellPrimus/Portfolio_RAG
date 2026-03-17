"""
카테고리 관리 API 라우터
"""
import json
import os
from flask import Blueprint, request, jsonify
from src.category_manager import CategoryManager

# Blueprint 생성
categories_bp = Blueprint('categories', __name__, url_prefix='/api/categories')

# CategoryManager 인스턴스 (app.py에서 주입받을 예정)
category_manager = None

# 프로젝트 루트 기준 절대 경로 계산
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
file_metadata_path = os.path.join(_project_root, "data", "file_metadata.json")


def init_category_manager(manager: CategoryManager):
    """CategoryManager 인스턴스 주입"""
    global category_manager
    category_manager = manager


def _calculate_document_counts() -> dict:
    """file_metadata.json을 기반으로 카테고리별 문서 수 실시간 계산"""
    counts = {}

    if not os.path.exists(file_metadata_path):
        return counts

    try:
        with open(file_metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        for doc_id, doc_info in metadata.items():
            category_id = doc_info.get('category_id', 'general')
            counts[category_id] = counts.get(category_id, 0) + 1
    except Exception:
        pass

    return counts


@categories_bp.route('', methods=['GET'])
def get_categories():
    """모든 카테고리 조회 (document_count 실시간 계산)"""
    try:
        categories = category_manager.get_all_categories()

        # file_metadata 기반으로 실시간 document_count 계산
        actual_counts = _calculate_document_counts()

        # 각 카테고리의 document_count를 실제 값으로 덮어쓰기
        for cat in categories:
            cat['document_count'] = actual_counts.get(cat['id'], 0)

        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('', methods=['POST'])
def create_category():
    """새 카테고리 생성"""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        color = data.get('color', '#6366f1')
        icon = data.get('icon', '📁')

        if not name:
            return jsonify({
                'success': False,
                'error': '카테고리 이름이 필요합니다.'
            }), 400

        category = category_manager.create_category(name, description, color, icon)

        return jsonify({
            'success': True,
            'category': category
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/<category_id>', methods=['PUT'])
def update_category(category_id):
    """카테고리 수정"""
    try:
        data = request.get_json()
        name = data.get('name')
        description = data.get('description')
        color = data.get('color')
        icon = data.get('icon')

        category = category_manager.update_category(
            category_id, name, description, color, icon
        )

        return jsonify({
            'success': True,
            'category': category
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    """카테고리 삭제"""
    try:
        success = category_manager.delete_category(category_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'카테고리가 삭제되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '카테고리를 찾을 수 없습니다.'
            }), 404
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/stats', methods=['GET'])
def get_category_stats():
    """카테고리 통계"""
    try:
        stats = category_manager.get_category_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/<category_id>/llm-model', methods=['GET'])
def get_category_llm_model(category_id):
    """카테고리의 LLM 모델 설정 조회"""
    try:
        model_config = category_manager.get_category_llm_model(category_id)
        return jsonify({
            'success': True,
            'category_id': category_id,
            'llm_model': model_config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@categories_bp.route('/<category_id>/llm-model', methods=['PUT'])
def set_category_llm_model(category_id):
    """카테고리의 LLM 모델 설정

    Request JSON:
        {
            "provider": "openai",  # 'openai', 'clovax', 'claude' 등
            "model_name": "gpt-5.1",
            "temperature": 0.7,
            "base_url": "https://aac-api.navercorp.com/v1"  # optional
        }

    provider를 null로 보내면 기본 모델 사용
    """
    try:
        data = request.get_json()

        # null이나 빈 객체를 받으면 기본 모델 사용 (None)
        if not data or data.get('provider') is None:
            model_config = None
        else:
            model_config = {
                'provider': data.get('provider'),
                'model_name': data.get('model_name'),
                'temperature': data.get('temperature', 0.7),
            }

            # base_url이 있으면 추가
            if data.get('base_url'):
                model_config['base_url'] = data.get('base_url')

        updated_category = category_manager.set_category_llm_model(
            category_id,
            model_config
        )

        return jsonify({
            'success': True,
            'category': updated_category
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
