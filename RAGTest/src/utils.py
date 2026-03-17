"""
유틸리티 함수

LLM 및 임베딩 제공자를 선택하는 헬퍼 함수들
"""

import os
import hashlib
from typing import Optional, List


def get_llm(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    temperature: float = 0.7,
    model_config: Optional[dict] = None
):
    """
    환경 변수 기반으로 LLM 인스턴스를 반환합니다.

    Args:
        provider: 'clovax', 'claude' 또는 'openai'. None이면 환경 변수에서 읽음
        model_name: 모델명. None이면 환경 변수에서 읽음
        temperature: 생성 온도
        model_config: 모델 설정 딕셔너리 (카테고리별 모델 설정 시 사용)
            {
                "provider": "openai",
                "model_name": "gpt-5.1",
                "temperature": 0.7,
                "base_url": "https://..."  # optional
            }

    Returns:
        LLM 인스턴스 (ChatClovaX, ChatAnthropic 또는 ChatOpenAI)

    Example:
        >>> llm = get_llm()  # 환경 변수 기반
        >>> llm = get_llm(provider='clovax')  # NAVER ClovaX 강제 지정
        >>> llm = get_llm(model_config=category_model_config)  # 카테고리별 설정 사용
    """
    # model_config가 제공되면 해당 설정 사용
    if model_config:
        provider = model_config.get('provider')
        model_name = model_config.get('model_name')
        temperature = model_config.get('temperature', 0.7)
    else:
        provider = provider or os.getenv("LLM_PROVIDER", "clovax")
        model_name = model_name or os.getenv("MODEL_NAME")

    if provider.lower() == "clova_studio":
        # CLOVA Studio v3 API (HCX-007)
        from src.llm import ChatClovaStudio

        if not model_name:
            model_name = os.getenv("CLOVA_MODEL_NAME", "HCX-007")

        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise ValueError(
                "CLOVASTUDIO_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 CLOVASTUDIO_API_KEY=your_key 를 추가하세요.\n"
                "API 키는 NAVER Cloud Platform > CLOVA Studio에서 발급받을 수 있습니다."
            )

        base_url = os.getenv("CLOVA_BASE_URL", "https://clovastudio.stream.ntruss.com/v3/chat-completions")

        return ChatClovaStudio(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            temperature=temperature,
            max_tokens=model_config.get('max_tokens', 4096) if model_config else 4096
        )

    elif provider.lower() == "clovax":
        # 기존 ClovaX (HCX-003) - 레거시 지원
        from langchain_naver import ChatClovaX

        if not model_name:
            model_name = "HCX-003"  # HyperCLOVA X 기본 모델

        api_key = os.getenv("CLOVASTUDIO_API_KEY")
        if not api_key:
            raise ValueError(
                "CLOVASTUDIO_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 CLOVASTUDIO_API_KEY=your_key 를 추가하세요.\n"
                "API 키는 NAVER Cloud Platform > CLOVA Studio에서 발급받을 수 있습니다."
            )

        # LangChain ChatClovaX가 자동으로 올바른 API 버전을 사용하도록 기본 설정으로 사용
        return ChatClovaX(
            model=model_name,
            temperature=temperature,
            max_tokens=2048
        )

    elif provider.lower() == "claude":
        from langchain_anthropic import ChatAnthropic

        if not model_name:
            model_name = "claude-3-5-sonnet-20241022"

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 ANTHROPIC_API_KEY=your_key 를 추가하세요."
            )

        return ChatAnthropic(
            model=model_name,
            temperature=temperature,
            anthropic_api_key=api_key
        )

    elif provider.lower() == "openai":
        from langchain_openai import ChatOpenAI

        if not model_name:
            model_name = "gpt-3.5-turbo"

        # model_config에서 api_key가 제공되면 사용, 없으면 환경 변수에서 읽음
        if model_config and 'api_key' in model_config:
            api_key = model_config.get('api_key')
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                    ".env 파일에 OPENAI_API_KEY=your_key 를 추가하세요."
                )

        # Custom base_url 지원 (AI API Channel 등)
        # model_config에서 제공되거나, 환경 변수에서 읽음
        if model_config and 'base_url' in model_config:
            base_url = model_config.get('base_url')
        else:
            base_url = os.getenv("OPENAI_BASE_URL")

        if base_url:
            return ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                openai_api_key=api_key,
                openai_api_base=base_url
            )
        else:
            return ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                openai_api_key=api_key
            )

    else:
        raise ValueError(f"지원하지 않는 제공자: {provider}. 'clova_studio', 'clovax', 'claude' 또는 'openai'를 사용하세요.")


def get_embeddings(
    provider: Optional[str] = None,
    model: Optional[str] = None
):
    """
    임베딩 모델 인스턴스를 반환합니다.

    지원되는 제공자:
    - e5: multilingual-e5-large (로컬, 1024차원, 100+ 언어)
    - qwen: Qwen3-Embedding-8B (NAMC AI Gateway)
    - huggingface: 로컬 오픈소스 모델 (무료, API 키 불필요)
    - clova: NAVER Clova Embedding API
    - openai: OpenAI API (유료, API 키 필요)

    Args:
        provider: 'e5', 'qwen', 'huggingface', 'clova', 또는 'openai'
        model: 임베딩 모델명

    Returns:
        Embeddings 인스턴스

    Example:
        >>> embeddings = get_embeddings()  # 환경 변수 기반
        >>> embeddings = get_embeddings(provider='e5')  # E5 Multilingual
        >>> embeddings = get_embeddings(provider='huggingface')  # HuggingFace 강제
    """
    provider = provider or os.getenv("EMBEDDING_PROVIDER", "huggingface")
    model = model or os.getenv("EMBEDDING_MODEL")

    if provider.lower() == "e5":
        from src.embeddings.e5_embeddings import E5Embeddings

        if not model:
            model = "intfloat/multilingual-e5-large"

        print(f"Embedding: e5")
        return E5Embeddings(model_name=model, device="cpu")

    elif provider.lower() == "qwen":
        from src.embeddings.qwen_embeddings import QwenEmbeddings

        if not model:
            model = "Qwen3-Embedding-8B"

        try:
            print("Qwen3-Embedding-8B API 초기화 중...")
        except (ValueError, AttributeError, OSError):
            pass

        return QwenEmbeddings(model=model)

    elif provider.lower() == "huggingface":
        from langchain_community.embeddings import HuggingFaceEmbeddings

        if not model:
            # 기본 모델: 경량 (384차원, 빠름)
            model = "sentence-transformers/all-MiniLM-L6-v2"

        try:
            print(f"로컬 임베딩 모델 로딩 중: {model}")
            print("(처음 실행 시 모델 다운로드로 시간이 걸릴 수 있습니다)")
        except (ValueError, AttributeError, OSError):
            pass

        return HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={'device': 'cpu'},  # CPU 사용
            encode_kwargs={'normalize_embeddings': True}  # 정규화
        )

    elif provider.lower() == "clova":
        from src.embeddings import ClovaEmbeddings

        try:
            print("NAVER Clova Embedding API 초기화 중...")
        except (ValueError, AttributeError, OSError):
            pass
        api_key = os.getenv("CLOVASTUDIO_EMBEDDING_API_KEY")
        if not api_key:
            raise ValueError(
                "Clova 임베딩을 사용하려면 CLOVASTUDIO_EMBEDDING_API_KEY가 필요합니다.\n"
                ".env 파일에 CLOVASTUDIO_EMBEDDING_API_KEY=your_key 를 추가하세요."
            )

        return ClovaEmbeddings(api_key=api_key)

    elif provider.lower() == "openai":
        from langchain_openai import OpenAIEmbeddings

        if not model:
            model = "text-embedding-3-small"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI 임베딩을 사용하려면 OPENAI_API_KEY가 필요합니다.\n"
                ".env 파일에 OPENAI_API_KEY=your_key 를 추가하세요."
            )

        return OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key
        )

    else:
        raise ValueError(
            f"지원하지 않는 임베딩 제공자: {provider}.\n"
            "'e5' (무료, 로컬, 1024차원), 'qwen', 'huggingface' (무료, 로컬), 'clova', 또는 'openai' (유료)를 사용하세요."
        )


def check_api_keys():
    """
    필요한 API 키가 설정되어 있는지 확인합니다.

    Returns:
        dict: 각 키의 설정 여부
    """
    from dotenv import load_dotenv
    load_dotenv()

    llm_provider = os.getenv("LLM_PROVIDER", "clovax")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "huggingface")

    status = {
        "llm_provider": llm_provider,
        "embedding_provider": embedding_provider,
        "clovastudio_key": bool(os.getenv("CLOVASTUDIO_API_KEY")),
        "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai_key": bool(os.getenv("OPENAI_API_KEY")),
    }

    # LLM 제공자에 따른 필수 키 체크
    if llm_provider == "clova_studio" or llm_provider == "clovax":
        status["llm_key_ok"] = status["clovastudio_key"]
        status["llm_key_name"] = "CLOVASTUDIO_API_KEY"
    elif llm_provider == "claude":
        status["llm_key_ok"] = status["anthropic_key"]
        status["llm_key_name"] = "ANTHROPIC_API_KEY"
    else:
        status["llm_key_ok"] = status["openai_key"]
        status["llm_key_name"] = "OPENAI_API_KEY"

    # 임베딩 제공자에 따른 키 체크
    if embedding_provider == "huggingface":
        status["embedding_key_ok"] = True  # 로컬 모델, 키 불필요
        status["embedding_key_name"] = "없음 (로컬 모델)"
    else:
        status["embedding_key_ok"] = status["openai_key"]
        status["embedding_key_name"] = "OPENAI_API_KEY"

    return status


def print_api_key_status():
    """API 키 설정 상태를 출력합니다."""
    status = check_api_keys()

    print("=" * 60)
    print("API 키 설정 상태")
    print("=" * 60)

    print(f"\n현재 설정:")
    print(f"  LLM 제공자: {status['llm_provider']}")
    print(f"  임베딩 제공자: {status['embedding_provider']}")

    print(f"\n필수 API 키:")
    print(f"  LLM ({status['llm_key_name']}): {'✅ 설정됨' if status['llm_key_ok'] else '❌ 미설정'}")
    print(f"  임베딩 ({status['embedding_key_name']}): {'✅ 설정됨' if status['embedding_key_ok'] else '❌ 미설정'}")

    if status['clovastudio_key']:
        print(f"\n사용 가능한 키:")
        print(f"  CLOVASTUDIO_API_KEY: ✅")
    if status['anthropic_key']:
        if not status['clovastudio_key']:
            print(f"\n사용 가능한 키:")
        print(f"  ANTHROPIC_API_KEY: ✅")
    if status['openai_key']:
        if not status['clovastudio_key'] and not status['anthropic_key']:
            print(f"\n사용 가능한 키:")
        print(f"  OPENAI_API_KEY: ✅")

    print("\n" + "=" * 60)

    # 경고 메시지
    if not status['llm_key_ok']:
        print(f"\n⚠️  {status['llm_key_name']}를 설정해야 합니다!")
        print(f"   .env 파일에 추가하세요.")

    if not status['embedding_key_ok'] and status['embedding_provider'] != 'huggingface':
        print(f"\n⚠️  임베딩을 위해 {status['embedding_key_name']}가 필요합니다!")
        print(f"   또는 .env에서 EMBEDDING_PROVIDER=huggingface로 변경하세요 (무료)")

    return status


def compute_file_hash(file_paths: List[str], chunk_config: dict) -> str:
    """
    파일 경로 리스트와 청킹 설정을 기반으로 고유한 해시를 생성합니다.

    이 해시는 벡터DB 컬렉션명으로 사용되며, 파일이 변경되지 않는 한
    동일한 해시가 생성되어 벡터DB를 재사용할 수 있습니다.

    Args:
        file_paths: 파일 경로 리스트
        chunk_config: 청킹 설정 (chunk_size, chunk_overlap)

    Returns:
        str: 16자 해시 문자열

    Example:
        >>> hash_key = compute_file_hash(
        ...     ["./html/file1.html"],
        ...     {"chunk_size": 1000, "chunk_overlap": 200}
        ... )
        >>> print(hash_key)  # "a1b2c3d4e5f6g7h8"
    """
    hasher = hashlib.sha256()

    # 파일 경로를 정렬하여 순서 무관하게
    for file_path in sorted(file_paths):
        # 파일명 추가
        hasher.update(os.path.basename(file_path).encode('utf-8'))

        # 파일 내용 추가 (수정 시간으로 대체 - 더 빠름)
        if os.path.exists(file_path):
            mtime = str(os.path.getmtime(file_path))
            hasher.update(mtime.encode('utf-8'))

    # 청킹 설정도 해시에 포함
    import json
    config_str = json.dumps(chunk_config, sort_keys=True)
    hasher.update(config_str.encode('utf-8'))

    # 16자로 축약
    return hasher.hexdigest()[:16]
