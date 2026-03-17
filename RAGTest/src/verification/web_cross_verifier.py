"""
웹 검색 교차 검증기

벡터DB 기반 RAG 답변을 웹 검색 결과로 교차 검증하여
답변의 정확도와 신뢰도를 향상시킵니다.

임베딩 기반 의미적 유사도 분석을 통해 정확한 검증을 수행합니다.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    """검증 상태"""
    CONFIRMED = "confirmed"      # 웹 검색 결과와 일치
    ENHANCED = "enhanced"        # 웹 검색으로 보완됨
    CONFLICTING = "conflicting"  # 웹 검색 결과와 충돌
    NO_DATA = "no_data"          # 웹 검색 결과 없음
    SKIPPED = "skipped"          # 검증 건너뜀


@dataclass
class VerificationResult:
    """검증 결과"""
    status: VerificationStatus
    confidence_delta: float  # -0.2 ~ 0.2
    enhanced_answer: Optional[str]
    web_sources: List[Dict[str, str]]
    verification_notes: str
    verification_details: Optional[Dict[str, Any]] = None  # 검증 상세 정보


class WebCrossVerifier:
    """
    웹 검색 결과를 이용한 RAG 답변 교차 검증기

    벡터DB에서 생성된 답변을 웹 검색 결과와 비교하여
    정확도를 검증하고 필요시 답변을 보완합니다.

    임베딩 기반 코사인 유사도를 사용하여 의미적 일치도를 분석합니다.
    """

    # 기본 임계값 (settings에서 오버라이드 가능)
    DEFAULT_THRESHOLD_CONFIRMED = 0.75
    DEFAULT_THRESHOLD_ENHANCED = 0.55
    DEFAULT_THRESHOLD_CONFLICTING = 0.35

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        similarity_thresholds: Optional[Dict[str, float]] = None
    ):
        """
        WebCrossVerifier 초기화

        Args:
            llm_service: LLM 서비스 (답변 보완용)
            embedding_service: 임베딩 서비스 (의미적 유사도 분석용)
            similarity_thresholds: 유사도 임계값 설정
                - confirmed: CONFIRMED 상태 임계값 (기본 0.75)
                - enhanced: ENHANCED 상태 임계값 (기본 0.55)
                - conflicting: CONFLICTING 상태 임계값 (기본 0.35)
        """
        self.llm_service = llm_service
        self.embedding_service = embedding_service

        # 임계값 설정
        thresholds = similarity_thresholds or {}
        self.threshold_confirmed = thresholds.get('confirmed', self.DEFAULT_THRESHOLD_CONFIRMED)
        self.threshold_enhanced = thresholds.get('enhanced', self.DEFAULT_THRESHOLD_ENHANCED)
        self.threshold_conflicting = thresholds.get('conflicting', self.DEFAULT_THRESHOLD_CONFLICTING)

        if self.embedding_service:
            logger.info("WebCrossVerifier 초기화 완료 (임베딩 기반 유사도 분석 활성화)")
        else:
            logger.info("WebCrossVerifier 초기화 완료 (키워드 기반 분석 - fallback)")

    def verify_and_enhance(
        self,
        question: str,
        rag_answer: str,
        web_results: List[Dict[str, Any]]
    ) -> VerificationResult:
        """
        RAG 답변을 웹 검색 결과로 교차 검증

        임베딩 서비스가 있으면 의미적 유사도 분석을 수행하고,
        없으면 키워드 기반 분석으로 대체합니다.

        Args:
            question: 사용자 질문
            rag_answer: 벡터DB 기반 RAG 답변
            web_results: 웹 검색 결과 리스트

        Returns:
            VerificationResult: 검증 결과
        """
        # 웹 검색 결과가 없는 경우
        if not web_results:
            logger.info("웹 검색 결과 없음 - 검증 건너뜀")
            return VerificationResult(
                status=VerificationStatus.NO_DATA,
                confidence_delta=0.0,
                enhanced_answer=None,
                web_sources=[],
                verification_notes="웹 검색 결과가 없어 교차 검증을 수행할 수 없습니다."
            )

        # 웹 검색 결과에서 관련 정보 추출
        web_contents = self._extract_relevant_content(web_results)
        web_sources = self._format_sources(web_results)

        # 유사도 분석 (임베딩 우선, 없으면 키워드 매칭)
        if self.embedding_service:
            similarity_analysis = self._analyze_embedding_similarity(rag_answer, web_contents)
        else:
            similarity_analysis = self._analyze_keyword_match(rag_answer, web_contents)

        # 검증 상태 결정
        status, confidence_delta, notes = self._determine_verification_status(
            similarity_analysis,
            rag_answer,
            web_contents
        )

        # 답변 보강이 필요한 경우
        enhanced_answer = None
        if status == VerificationStatus.ENHANCED and self.llm_service:
            enhanced_answer = self._enhance_answer(
                question,
                rag_answer,
                web_contents
            )

        # 검증 상세 정보 구성
        verification_details = self._build_verification_details(
            status, similarity_analysis
        )

        logger.info(
            f"교차 검증 완료: status={status.value}, "
            f"confidence_delta={confidence_delta:+.2f}, "
            f"method={similarity_analysis.get('method', 'unknown')}"
        )

        return VerificationResult(
            status=status,
            confidence_delta=confidence_delta,
            enhanced_answer=enhanced_answer,
            web_sources=web_sources,
            verification_notes=notes,
            verification_details=verification_details
        )

    def _build_verification_details(
        self,
        status: VerificationStatus,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """검증 상세 정보 구성"""
        method = analysis.get('method', 'keyword')

        if method == 'embedding':
            return {
                'status_type': status.value,
                'method': 'embedding',
                'similarity_score': analysis.get('similarity_score', 0.0),
                'avg_similarity': analysis.get('avg_similarity', 0.0),
                'max_similarity': analysis.get('max_similarity', 0.0),
                'num_chunks': analysis.get('num_chunks', 0),
                'thresholds': {
                    'confirmed': self.threshold_confirmed,
                    'enhanced': self.threshold_enhanced,
                    'conflicting': self.threshold_conflicting
                }
            }
        else:
            return {
                'status_type': status.value,
                'method': 'keyword',
                'matched_keywords': analysis.get('matched_keywords', []),
                'unmatched_keywords': analysis.get('unmatched_keywords', []),
                'match_ratio': analysis.get('match_ratio', 0),
                'total_keywords': analysis.get('total_keywords', 0)
            }

    def _extract_relevant_content(
        self,
        web_results: List[Dict[str, Any]]
    ) -> List[str]:
        """웹 검색 결과에서 관련 콘텐츠 추출"""
        contents = []

        for result in web_results:
            content = result.get('content', '')
            if content:
                contents.append(content)

            # raw_content가 있으면 추가 정보 활용
            raw_content = result.get('raw_content', '')
            if raw_content and len(raw_content) > len(content):
                contents.append(raw_content[:2000])  # 길이 제한

        return contents

    def _analyze_embedding_similarity(
        self,
        rag_answer: str,
        web_contents: List[str]
    ) -> Dict[str, Any]:
        """
        임베딩 기반 의미적 유사도 분석

        RAG 답변과 웹 콘텐츠 간의 코사인 유사도를 계산합니다.
        웹 콘텐츠는 청크로 분할하여 가장 높은 유사도를 찾습니다.

        Args:
            rag_answer: RAG 답변
            web_contents: 웹 검색 결과 콘텐츠 리스트

        Returns:
            유사도 분석 결과 딕셔너리
        """
        if not self.embedding_service:
            logger.warning("임베딩 서비스 없음 - 키워드 매칭으로 대체")
            return self._analyze_keyword_match(rag_answer, web_contents)

        try:
            # 1. RAG 답변 임베딩
            answer_embedding = self.embedding_service.embed_query(rag_answer)

            # 2. 웹 콘텐츠 청킹
            all_chunks = []
            for content in web_contents:
                chunks = self._chunk_text(content, max_size=1000)
                all_chunks.extend(chunks)

            if not all_chunks:
                logger.info("웹 콘텐츠 청크 없음")
                return {
                    'similarity_score': 0.0,
                    'avg_similarity': 0.0,
                    'max_similarity': 0.0,
                    'num_chunks': 0,
                    'method': 'embedding'
                }

            # 3. 웹 청크 임베딩 (배치 처리)
            chunk_embeddings = self.embedding_service.embed_documents(all_chunks)

            # 4. 코사인 유사도 계산
            similarities = [
                self._cosine_similarity(answer_embedding, chunk_emb)
                for chunk_emb in chunk_embeddings
            ]

            max_similarity = max(similarities)
            avg_similarity = sum(similarities) / len(similarities)

            logger.info(
                f"임베딩 유사도 분석 완료: max={max_similarity:.3f}, "
                f"avg={avg_similarity:.3f}, chunks={len(all_chunks)}"
            )

            return {
                'similarity_score': max_similarity,  # 주요 메트릭: 최대 유사도
                'avg_similarity': avg_similarity,
                'max_similarity': max_similarity,
                'num_chunks': len(all_chunks),
                'method': 'embedding'
            }

        except Exception as e:
            logger.error(f"임베딩 유사도 분석 실패: {str(e)}, 키워드 매칭으로 대체")
            return self._analyze_keyword_match(rag_answer, web_contents)

    def _chunk_text(self, text: str, max_size: int = 1000) -> List[str]:
        """
        텍스트를 청크로 분할

        Args:
            text: 분할할 텍스트
            max_size: 청크 최대 크기 (문자)

        Returns:
            청크 리스트
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        if len(text) <= max_size:
            return [text]

        chunks = []
        # 문장 단위로 분할 시도
        sentences = text.replace('\n', ' ').split('. ')

        current_chunk = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # 문장 끝에 마침표 복원
            if not sentence.endswith('.'):
                sentence += '.'

            if len(current_chunk) + len(sentence) + 1 <= max_size:
                current_chunk += (" " + sentence if current_chunk else sentence)
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        # 청크가 없으면 강제 분할
        if not chunks:
            for i in range(0, len(text), max_size):
                chunk = text[i:i + max_size].strip()
                if chunk:
                    chunks.append(chunk)

        return chunks

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        두 벡터 간 코사인 유사도 계산

        Args:
            vec1: 첫 번째 벡터
            vec2: 두 번째 벡터

        Returns:
            코사인 유사도 (-1 ~ 1, 일반적으로 0 ~ 1)
        """
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(np.dot(v1, v2) / (norm1 * norm2))

    def _format_sources(
        self,
        web_results: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """웹 소스 정보 포맷팅"""
        sources = []

        for result in web_results:
            source = {
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'snippet': result.get('content', '')[:200] if result.get('content') else ''
            }
            if source['url']:  # URL이 있는 결과만 포함
                sources.append(source)

        return sources

    def _analyze_keyword_match(
        self,
        rag_answer: str,
        web_contents: List[str]
    ) -> Dict[str, Any]:
        """키워드 기반 일치도 분석"""
        # RAG 답변에서 주요 키워드 추출
        rag_keywords = self._extract_keywords(rag_answer)

        # 웹 콘텐츠 통합
        combined_web_content = ' '.join(web_contents).lower()

        # 키워드 매칭
        matched_keywords = []
        unmatched_keywords = []

        for keyword in rag_keywords:
            if keyword.lower() in combined_web_content:
                matched_keywords.append(keyword)
            else:
                unmatched_keywords.append(keyword)

        match_ratio = len(matched_keywords) / len(rag_keywords) if rag_keywords else 0

        return {
            'match_ratio': match_ratio,
            'matched_keywords': matched_keywords,
            'unmatched_keywords': unmatched_keywords,
            'total_keywords': len(rag_keywords),
            'method': 'keyword'  # 분석 방식 표시
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """텍스트에서 주요 키워드 추출 (간단한 구현)"""
        import re

        # 불용어 (한국어 + 영어)
        stopwords = {
            '의', '가', '이', '은', '들', '는', '좀', '잘', '걍', '과',
            '도', '를', '으로', '자', '에', '와', '한', '하다', '있다',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can',
            'and', 'or', 'but', 'if', 'then', 'else', 'when', 'at',
            'by', 'for', 'with', 'about', 'against', 'between', 'into',
            'through', 'during', 'before', 'after', 'above', 'below',
            'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
            'under', 'again', 'further', 'once', 'here', 'there', 'all',
            'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
            'very', 's', 't', 'just', 'don', 'now'
        }

        # 단어 추출 (한글 + 영문 + 숫자)
        words = re.findall(r'[가-힣]+|[a-zA-Z]{2,}|\d+', text)

        # 불용어 제거 및 중복 제거
        keywords = []
        seen = set()

        for word in words:
            word_lower = word.lower()
            if word_lower not in stopwords and word_lower not in seen:
                if len(word) >= 2:  # 2글자 이상만
                    keywords.append(word)
                    seen.add(word_lower)

        return keywords[:30]  # 최대 30개 키워드

    def _determine_verification_status(
        self,
        analysis: Dict[str, Any],
        rag_answer: str,
        web_contents: List[str]
    ) -> tuple:
        """
        검증 상태 결정

        임베딩 기반 분석과 키워드 기반 분석 모두 지원합니다.
        """
        method = analysis.get('method', 'keyword')

        if method == 'embedding':
            return self._determine_status_by_embedding(analysis, web_contents)
        else:
            return self._determine_status_by_keyword(analysis, web_contents)

    def _determine_status_by_embedding(
        self,
        analysis: Dict[str, Any],
        web_contents: List[str]
    ) -> tuple:
        """임베딩 유사도 기반 상태 결정"""
        similarity = analysis.get('similarity_score', 0.0)

        # 높은 유사도 - 확인됨
        if similarity >= self.threshold_confirmed:
            return (
                VerificationStatus.CONFIRMED,
                0.1,
                f"웹 검색 결과와 높은 의미적 일치 (유사도: {similarity:.2f}) - 답변이 확인되었습니다."
            )

        # 중간 유사도 - 보완 가능
        elif similarity >= self.threshold_enhanced:
            return (
                VerificationStatus.ENHANCED,
                0.05,
                f"웹 검색 결과와 중간 수준 일치 (유사도: {similarity:.2f}) - 추가 정보로 보완 가능합니다."
            )

        # 낮은 유사도 - 충돌 가능성
        elif similarity >= self.threshold_conflicting:
            return (
                VerificationStatus.CONFLICTING,
                -0.1,
                f"웹 검색 결과와 낮은 일치 (유사도: {similarity:.2f}) - 정보 확인이 필요합니다."
            )

        # 매우 낮은 유사도
        else:
            total_web_content = ''.join(web_contents)
            if len(total_web_content) > 500:
                return (
                    VerificationStatus.CONFLICTING,
                    -0.15,
                    f"웹 검색 결과와 의미적 차이가 큽니다 (유사도: {similarity:.2f})."
                )
            else:
                return (
                    VerificationStatus.NO_DATA,
                    0.0,
                    "관련 웹 검색 결과가 부족합니다."
                )

    def _determine_status_by_keyword(
        self,
        analysis: Dict[str, Any],
        web_contents: List[str]
    ) -> tuple:
        """키워드 매칭 기반 상태 결정 (fallback)"""
        match_ratio = analysis.get('match_ratio', 0)

        # 높은 일치율 (70% 이상) - 확인됨
        if match_ratio >= 0.7:
            return (
                VerificationStatus.CONFIRMED,
                0.1,
                f"웹 검색 결과와 {match_ratio:.0%} 키워드 일치 - 답변이 확인되었습니다."
            )

        # 중간 일치율 (40-70%) - 보완 가능
        elif match_ratio >= 0.4:
            return (
                VerificationStatus.ENHANCED,
                0.05,
                f"웹 검색 결과와 {match_ratio:.0%} 키워드 일치 - 추가 정보로 보완 가능합니다."
            )

        # 낮은 일치율 (20-40%) - 충돌 가능성
        elif match_ratio >= 0.2:
            return (
                VerificationStatus.CONFLICTING,
                -0.1,
                f"웹 검색 결과와 {match_ratio:.0%}만 키워드 일치 - 정보 확인이 필요합니다."
            )

        # 매우 낮은 일치율 (20% 미만)
        else:
            total_web_content = ''.join(web_contents)
            if len(total_web_content) > 500:
                return (
                    VerificationStatus.CONFLICTING,
                    -0.15,
                    f"웹 검색 결과와 상당한 차이가 있습니다 (키워드 일치율: {match_ratio:.0%})."
                )
            else:
                return (
                    VerificationStatus.NO_DATA,
                    0.0,
                    "관련 웹 검색 결과가 부족합니다."
                )

    def _enhance_answer(
        self,
        question: str,
        rag_answer: str,
        web_contents: List[str]
    ) -> Optional[str]:
        """LLM을 이용한 답변 보강"""
        if not self.llm_service:
            return None

        try:
            # 웹 콘텐츠 결합
            web_context = "\n\n".join(web_contents[:3])  # 상위 3개만 사용

            enhance_prompt = f"""다음은 사용자 질문에 대한 기존 답변과 웹 검색 결과입니다.
웹 검색 결과를 참고하여 기존 답변을 보완해주세요.
단, 기존 답변의 핵심 내용은 유지하고, 웹에서 발견된 추가 정보만 덧붙여주세요.

[질문]
{question}

[기존 답변]
{rag_answer}

[웹 검색 결과]
{web_context[:2000]}

[보완된 답변]
"""
            # LLM 호출
            if hasattr(self.llm_service, 'generate'):
                enhanced = self.llm_service.generate(enhance_prompt)
                return enhanced
            elif hasattr(self.llm_service, 'invoke'):
                enhanced = self.llm_service.invoke(enhance_prompt)
                return str(enhanced)

        except Exception as e:
            logger.error(f"답변 보강 실패: {str(e)}")

        return None

    def quick_verify(
        self,
        rag_answer: str,
        web_results: List[Dict[str, Any]]
    ) -> bool:
        """
        빠른 검증 - 웹 결과와 RAG 답변의 일치 여부만 확인

        임베딩 서비스가 있으면 의미적 유사도로, 없으면 키워드 매칭으로 검증합니다.

        Args:
            rag_answer: RAG 답변
            web_results: 웹 검색 결과

        Returns:
            True if 답변이 웹 결과와 대체로 일치
        """
        if not web_results:
            return True  # 검증 데이터 없으면 통과

        web_contents = self._extract_relevant_content(web_results)

        if self.embedding_service:
            analysis = self._analyze_embedding_similarity(rag_answer, web_contents)
            return analysis.get('similarity_score', 0) >= self.threshold_enhanced
        else:
            analysis = self._analyze_keyword_match(rag_answer, web_contents)
            return analysis.get('match_ratio', 0) >= 0.4
