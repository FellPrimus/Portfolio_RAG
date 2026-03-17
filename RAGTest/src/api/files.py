"""
파일 관리 API 라우터

파일 업로드, 조회, 삭제, 카테고리 변경 등을 처리합니다.
"""
from flask import Blueprint, request, jsonify
from src.services import FileService
import os
import glob

# Blueprint 생성
files_bp = Blueprint('files', __name__, url_prefix='/api/files')

# FileService 인스턴스 (app.py에서 주입받을 예정)
file_service = None
category_manager = None


def init_file_service(service: FileService, cat_manager):
    """FileService 및 CategoryManager 인스턴스 주입"""
    global file_service, category_manager
    file_service = service
    category_manager = cat_manager


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    """
    파일 업로드 처리

    Form Data:
        file: 업로드할 파일
        category: 카테고리 ID (optional, default: 'general')

    Returns:
        {
            'success': bool,
            'message': str,
            'file_path': str,
            'file_name': str,
            'category_id': str
        }
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '파일이 없습니다.'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '파일이 선택되지 않았습니다.'
            }), 400

        # 파일 확장자 확인
        ext = os.path.splitext(file.filename)[1].lower()
        supported_extensions = ['.html', '.htm', '.pdf', '.xlsx', '.xls', '.docx', '.doc']
        if ext not in supported_extensions:
            return jsonify({
                'success': False,
                'error': f'지원하지 않는 파일 형식입니다: {ext}'
            }), 400

        # 카테고리 정보 (폼 데이터에서 가져오기)
        category_id = request.form.get('category', 'general')

        # 파일 서비스를 통해 업로드
        result = file_service.upload_file(file, category_id)

        if result['success']:
            return jsonify({
                'success': True,
                'message': '파일 업로드 성공',
                'file_path': result['path'],
                'file_name': result['filename'],
                'category_id': category_id
            })
        else:
            return jsonify(result), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@files_bp.route('', methods=['GET'])
def get_files():
    """
    documents 폴더의 파일 목록 반환 (HTML, PDF, Excel, Word 지원)

    Returns:
        {
            'success': bool,
            'files': [
                {
                    'name': str,
                    'path': str,
                    'size': int,
                    'type': str,
                    'category': {...}
                }
            ],
            'count': int
        }
    """
    try:
        # 파일 서비스에서 업로드된 파일 가져오기
        files_info = file_service.get_files()

        # 추가 폴더에서 파일 검색 (html, docs, data 폴더)
        additional_folders = ["./html", "./docs", "./data"]
        supported_extensions = ['*.html', '*.htm', '*.pdf', '*.xlsx', '*.xls', '*.docx', '*.doc']

        for folder in additional_folders:
            if not os.path.exists(folder):
                continue

            for ext in supported_extensions:
                file_paths = glob.glob(f"{folder}/{ext}")

                for file_path in file_paths:
                    file_name = os.path.basename(file_path)
                    file_size = os.path.getsize(file_path)
                    file_ext = os.path.splitext(file_name)[1].lower()

                    # 파일 타입 결정
                    if file_ext in ['.html', '.htm']:
                        file_type = 'HTML'
                    elif file_ext == '.pdf':
                        file_type = 'PDF'
                    elif file_ext in ['.xlsx', '.xls']:
                        file_type = 'Excel'
                    elif file_ext in ['.docx', '.doc']:
                        file_type = 'Word'
                    else:
                        file_type = 'Unknown'

                    # 기본 카테고리 정보
                    default_category = category_manager.get_category('general')
                    category_info = {
                        'id': 'general',
                        'name': default_category['name'],
                        'color': default_category['color'],
                        'icon': default_category['icon']
                    }

                    files_info.append({
                        'name': file_name,
                        'path': file_path,
                        'size': file_size,
                        'type': file_type,
                        'category': category_info
                    })

        return jsonify({
            'success': True,
            'files': files_info,
            'count': len(files_info)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@files_bp.route('/category', methods=['PUT'])
def update_file_category():
    """
    파일의 카테고리 변경

    Request JSON:
        {
            'filename': str,
            'category_id': str
        }

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    try:
        data = request.get_json()
        filename = data.get('filename')
        category_id = data.get('category_id')

        if not filename or not category_id:
            return jsonify({
                'success': False,
                'error': '파일명과 카테고리 ID가 필요합니다.'
            }), 400

        # 파일 서비스를 통해 카테고리 업데이트
        result = file_service.update_category(filename, category_id)

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'파일 {filename}의 카테고리가 {category_id}(으)로 변경되었습니다.'
            })
        else:
            return jsonify(result), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@files_bp.route('/<filename>', methods=['DELETE'])
def delete_file(filename: str):
    """
    업로드된 파일 삭제

    Args:
        filename: 삭제할 파일명

    Returns:
        {
            'success': bool,
            'message': str
        }
    """
    try:
        # 파일 서비스를 통해 삭제
        result = file_service.delete_file(filename)

        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
