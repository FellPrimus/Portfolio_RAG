"""
API 데코레이터

공통 기능을 데코레이터로 추출
"""
import functools
import logging
from flask import jsonify
from typing import Callable, Any

from src.exceptions import RAGBaseException
from src.config.constants import HTTP_STATUS_MESSAGES

logger = logging.getLogger(__name__)


def handle_exceptions(func: Callable) -> Callable:
    """
    API 예외 처리 데코레이터

    RAGBaseException과 일반 Exception을 일관되게 처리

    Example:
        @app.route('/api/query')
        @handle_exceptions
        def query():
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)

        except RAGBaseException as e:
            logger.error(f"{e.__class__.__name__}: {e.message}", extra=e.details)
            return jsonify({
                'success': False,
                'error': e.message,
                'error_type': e.__class__.__name__,
                'details': e.details
            }), 400

        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': 'InternalError'
            }), 500

    return wrapper


def validate_request(*required_fields: str) -> Callable:
    """
    요청 데이터 검증 데코레이터

    Args:
        *required_fields: 필수 필드 이름들

    Example:
        @app.route('/api/query', methods=['POST'])
        @validate_request('question')
        def query():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            from flask import request

            data = request.get_json() or {}
            missing = [f for f in required_fields if not data.get(f)]

            if missing:
                return jsonify({
                    'success': False,
                    'error': f"필수 필드가 누락되었습니다: {', '.join(missing)}"
                }), 400

            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_request(func: Callable) -> Callable:
    """
    요청 로깅 데코레이터
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        from flask import request
        logger.info(f"API 호출: {request.method} {request.path}")
        return func(*args, **kwargs)
    return wrapper
