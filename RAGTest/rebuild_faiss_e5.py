#!/usr/bin/env python3
"""
FAISS 인덱스 재구축 스크립트

기존 Qwen 임베딩 (4096차원) → E5 임베딩 (1024차원)으로 마이그레이션

사용법:
    docker exec ragtest-app python rebuild_faiss_e5.py

또는 로컬에서:
    python rebuild_faiss_e5.py
"""

import os
import sys
import pickle
from typing import List, Dict
from datetime import datetime

# 환경 설정
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

# E5 임베딩 로드
from src.embeddings.e5_embeddings import E5Embeddings


def load_documents_from_pkl(pkl_path: str) -> List[Document]:
    """
    기존 FAISS pkl 파일에서 문서 추출

    pkl 파일은 docstore와 index_to_docstore_id를 포함합니다.
    """
    print(f"\n[1/4] 기존 인덱스에서 문서 추출 중...")
    print(f"      PKL 파일: {pkl_path}")

    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)

    # 데이터 구조 분석
    if isinstance(data, tuple) and len(data) == 2:
        docstore, index_to_docstore_id = data
    else:
        raise ValueError(f"예상치 못한 pkl 데이터 구조: {type(data)}")

    # docstore에서 모든 문서 추출
    documents = []
    docstore_dict = docstore._dict if hasattr(docstore, '_dict') else docstore

    for doc_id, doc in docstore_dict.items():
        if hasattr(doc, 'page_content'):
            documents.append(doc)

    print(f"      추출된 문서 수: {len(documents)}")

    # 문서 통계
    sources = set()
    for doc in documents:
        source = doc.metadata.get('source', 'Unknown')
        sources.add(os.path.basename(source))

    print(f"      고유 소스 파일: {len(sources)}개")

    return documents


def rebuild_faiss_index(
    documents: List[Document],
    embedding_function,
    output_dir: str,
    index_name: str = "documents",
    batch_size: int = 100
):
    """
    E5 임베딩으로 FAISS 인덱스 재구축
    """
    print(f"\n[2/4] E5 임베딩으로 벡터 생성 중...")
    print(f"      총 문서: {len(documents)}개")
    print(f"      배치 크기: {batch_size}")

    # 배치 처리
    total_batches = (len(documents) + batch_size - 1) // batch_size
    vectorstore = None

    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        batch_num = i // batch_size + 1

        print(f"      배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 문서)")

        if vectorstore is None:
            # 첫 배치로 인덱스 생성
            vectorstore = FAISS.from_documents(
                documents=batch,
                embedding=embedding_function
            )
        else:
            # 기존 인덱스에 추가
            vectorstore.add_documents(batch)

    # 인덱스 저장
    print(f"\n[3/4] 새 인덱스 저장 중...")
    print(f"      저장 경로: {output_dir}/{index_name}")

    os.makedirs(output_dir, exist_ok=True)
    vectorstore.save_local(
        folder_path=output_dir,
        index_name=index_name
    )

    return vectorstore


def main():
    print("=" * 60)
    print("FAISS 인덱스 재구축 (Qwen 4096D → E5 1024D)")
    print("=" * 60)

    # 경로 설정
    faiss_dir = "./data/faiss_web"
    index_name = "documents"
    pkl_path = os.path.join(faiss_dir, f"{index_name}.pkl")
    faiss_path = os.path.join(faiss_dir, f"{index_name}.faiss")

    # 백업 경로
    backup_dir = "./data/faiss_web_backup"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 기존 인덱스 확인
    if not os.path.exists(pkl_path):
        print(f"\n[ERROR] PKL 파일을 찾을 수 없습니다: {pkl_path}")
        print("        기존 FAISS 인덱스가 없습니다.")
        sys.exit(1)

    # 1. 기존 문서 추출
    documents = load_documents_from_pkl(pkl_path)

    if not documents:
        print("\n[ERROR] 추출된 문서가 없습니다.")
        sys.exit(1)

    # 2. 기존 인덱스 백업
    print(f"\n[BACKUP] 기존 인덱스 백업 중...")
    os.makedirs(backup_dir, exist_ok=True)

    import shutil
    if os.path.exists(faiss_path):
        shutil.copy2(faiss_path, os.path.join(backup_dir, f"{index_name}_{timestamp}.faiss"))
    if os.path.exists(pkl_path):
        shutil.copy2(pkl_path, os.path.join(backup_dir, f"{index_name}_{timestamp}.pkl"))

    print(f"        백업 완료: {backup_dir}")

    # 3. E5 임베딩 초기화
    print(f"\n[E5] E5 임베딩 모델 로딩...")
    e5_embeddings = E5Embeddings(
        model_name="intfloat/multilingual-e5-large",
        device="cpu",
        batch_size=32
    )

    # 4. 새 인덱스 구축
    vectorstore = rebuild_faiss_index(
        documents=documents,
        embedding_function=e5_embeddings,
        output_dir=faiss_dir,
        index_name=index_name,
        batch_size=100  # E5는 배치 처리 가능
    )

    # 5. 검증
    print(f"\n[4/4] 인덱스 검증 중...")
    stats = {
        "document_count": vectorstore.index.ntotal,
        "embedding_dim": vectorstore.index.d,
        "index_type": type(vectorstore.index).__name__
    }

    print(f"      문서 수: {stats['document_count']}")
    print(f"      임베딩 차원: {stats['embedding_dim']}")
    print(f"      인덱스 타입: {stats['index_type']}")

    # 테스트 검색
    print(f"\n[TEST] 검색 테스트...")
    test_query = "서버 생성 방법"
    results = vectorstore.similarity_search(test_query, k=3)

    if results:
        print(f"      쿼리: '{test_query}'")
        print(f"      결과: {len(results)}개 문서")
        for i, doc in enumerate(results[:2]):
            content_preview = doc.page_content[:100].replace('\n', ' ')
            print(f"        {i+1}. {content_preview}...")

    print("\n" + "=" * 60)
    print("✓ FAISS 인덱스 재구축 완료!")
    print("=" * 60)
    print(f"\n다음 단계:")
    print(f"  1. Docker 컨테이너 재시작: docker compose restart")
    print(f"  2. 웹 UI에서 문서 검색 테스트")


if __name__ == "__main__":
    main()
