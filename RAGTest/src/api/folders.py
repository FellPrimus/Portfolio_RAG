"""
폴더 관리 API 라우터
"""
from flask import Blueprint, request, jsonify
from src.folder_manager import FolderManager

# Blueprint 생성
folders_bp = Blueprint('folders', __name__, url_prefix='/api/folders')

# FolderManager 인스턴스 (app.py에서 주입받을 예정)
folder_manager = None


def init_folder_manager(manager: FolderManager):
    """FolderManager 인스턴스 주입"""
    global folder_manager
    folder_manager = manager


@folders_bp.route('', methods=['GET'])
def get_folders():
    """전체 폴더 트리 조회"""
    try:
        tree = folder_manager.get_folder_tree()
        return jsonify({
            'success': True,
            'folders': tree
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/list', methods=['GET'])
def get_all_folders():
    """모든 폴더 평면 목록 조회"""
    try:
        folders = folder_manager.get_all_folders()
        return jsonify({
            'success': True,
            'folders': folders
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('', methods=['POST'])
def create_folder():
    """새 폴더 생성"""
    try:
        data = request.get_json()
        name = data.get('name')
        parent_id = data.get('parent_id')
        color = data.get('color', '#6366f1')
        icon = data.get('icon', 'folder')

        if not name:
            return jsonify({
                'success': False,
                'error': '폴더 이름이 필요합니다.'
            }), 400

        folder = folder_manager.create_folder(name, parent_id, color, icon)

        return jsonify({
            'success': True,
            'folder': folder
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


@folders_bp.route('/<folder_id>', methods=['GET'])
def get_folder(folder_id):
    """특정 폴더 조회"""
    try:
        folder = folder_manager.get_folder(folder_id)

        if folder:
            return jsonify({
                'success': True,
                'folder': folder
            })
        else:
            return jsonify({
                'success': False,
                'error': '폴더를 찾을 수 없습니다.'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/<folder_id>', methods=['PUT'])
def update_folder(folder_id):
    """폴더 수정"""
    try:
        data = request.get_json()
        name = data.get('name')
        color = data.get('color')
        icon = data.get('icon')

        folder = folder_manager.update_folder(folder_id, name, color, icon)

        return jsonify({
            'success': True,
            'folder': folder
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


@folders_bp.route('/<folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """폴더 삭제"""
    try:
        recursive = request.args.get('recursive', 'false').lower() == 'true'
        success = folder_manager.delete_folder(folder_id, recursive=recursive)

        if success:
            return jsonify({
                'success': True,
                'message': '폴더가 삭제되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '폴더를 찾을 수 없습니다.'
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


@folders_bp.route('/<folder_id>/move', methods=['POST'])
def move_folder(folder_id):
    """폴더 이동"""
    try:
        data = request.get_json()
        new_parent_id = data.get('new_parent_id')  # None이면 루트로

        folder = folder_manager.move_folder(folder_id, new_parent_id)

        return jsonify({
            'success': True,
            'folder': folder
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


@folders_bp.route('/<folder_id>/documents', methods=['GET'])
def get_folder_documents(folder_id):
    """폴더 내 문서 목록 조회"""
    try:
        include_subfolders = request.args.get('include_subfolders', 'false').lower() == 'true'
        documents = folder_manager.get_documents_in_folder(folder_id, include_subfolders)

        return jsonify({
            'success': True,
            'folder_id': folder_id,
            'documents': documents,
            'count': len(documents)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/<folder_id>/documents', methods=['POST'])
def assign_document_to_folder(folder_id):
    """문서를 폴더에 할당"""
    try:
        data = request.get_json()
        doc_id = data.get('doc_id')

        if not doc_id:
            return jsonify({
                'success': False,
                'error': '문서 ID가 필요합니다.'
            }), 400

        success = folder_manager.assign_document_to_folder(doc_id, folder_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'문서가 폴더에 추가되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '폴더를 찾을 수 없습니다.'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/<folder_id>/documents/<path:doc_id>', methods=['DELETE'])
def remove_document_from_folder(folder_id, doc_id):
    """문서를 폴더에서 제거"""
    try:
        success = folder_manager.remove_document_from_folder(doc_id)

        if success:
            return jsonify({
                'success': True,
                'message': '문서가 폴더에서 제거되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '문서를 찾을 수 없습니다.'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/<folder_id>/path', methods=['GET'])
def get_folder_path(folder_id):
    """폴더 경로 조회 (브레드크럼용)"""
    try:
        path = folder_manager.get_folder_path(folder_id)

        return jsonify({
            'success': True,
            'path': path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/stats', methods=['GET'])
def get_folder_stats():
    """폴더 통계"""
    try:
        stats = folder_manager.get_folder_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@folders_bp.route('/document/<path:doc_id>', methods=['GET'])
def get_document_folder(doc_id):
    """문서가 속한 폴더 조회"""
    try:
        folder_id = folder_manager.get_document_folder(doc_id)

        if folder_id:
            folder = folder_manager.get_folder(folder_id)
            return jsonify({
                'success': True,
                'folder_id': folder_id,
                'folder': folder
            })
        else:
            return jsonify({
                'success': True,
                'folder_id': None,
                'folder': None
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
