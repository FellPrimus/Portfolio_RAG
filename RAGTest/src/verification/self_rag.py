"""
Self-RAG 검증 모듈

LLM 기반 답변 품질 자동 검증
"""

import json
from typing import List, Dict
from langchain_core.documents import Document


class SelfRAGVerifier:
    """Self-RAG 기반 답변 검증기"""

    def __init__(self, llm):
        """
        SelfRAGVerifier 초기화

        Args:
            llm: LLM 인스턴스
        """
        self.llm = llm

    def verify_answer(
        self,
        question: str,
        answer: str,
        documents: List[Document]
    ) -> Dict:
        """
        답변 품질 검증

        Returns:
            dict: 검증 결과
        """
        context = "\n\n".join([
            f"[문서 {i+1}]\n{doc.page_content}"
            for i, doc in enumerate(documents)
        ]) if documents else "참조 문서 없음"

        prompt = f"""당신은 RAG 시스템의 품질 검증 전문가입니다.
아래 정보를 바탕으로 답변의 품질을 엄격하게 평가하세요.

## 질문
{question}

## 생성된 답변
{answer}

## 참조 문서
{context}

## 평가 기준
1. **문서 근거성**: 답변이 제공된 문서에 근거하는가?
2. **완전성**: 질문에 대해 충분히 답변했는가?
3. **할루시네이션**: 문서에 없는 정보를 만들어냈는가?
4. **정확성**: 문서 내용을 정확히 전달했는가?

## JSON 형식으로 출력
{{
    "grounding_score": 0-5,
    "completeness_score": 0-5,
    "has_hallucination": true/false,
    "hallucination_details": "할루시네이션이 있다면 구체적 내용",
    "accuracy_score": 0-5,
    "overall_quality": 0-5,
    "feedback": "개선이 필요한 부분",
    "should_retry": true/false
}}"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # JSON 파싱
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            quality_score = result.get("overall_quality", 3) / 5.0

            return {
                "is_grounded": result.get("grounding_score", 0) >= 3,
                "is_complete": result.get("completeness_score", 0) >= 3,
                "has_hallucination": result.get("has_hallucination", False),
                "hallucination_details": result.get("hallucination_details", ""),
                "quality_score": quality_score,
                "feedback": result.get("feedback", ""),
                "needs_retry": result.get("should_retry", quality_score < 0.6),
                "raw_scores": {
                    "grounding": result.get("grounding_score", 0),
                    "completeness": result.get("completeness_score", 0),
                    "accuracy": result.get("accuracy_score", 0)
                }
            }

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[WARN] 검증 파싱 실패: {e}")
            return {
                "is_grounded": True,
                "is_complete": True,
                "has_hallucination": False,
                "quality_score": 0.7,
                "feedback": f"검증 파싱 실패: {str(e)}",
                "needs_retry": False
            }

    def verify_retrieval(
        self,
        question: str,
        documents: List[Document]
    ) -> Dict:
        """
        검색 결과 품질 검증 (CRAG 패턴)

        Returns:
            dict: 검증 결과
        """
        if not documents:
            return {
                "relevance": "INCORRECT",
                "should_search_more": True,
                "relevant_doc_indices": []
            }

        doc_summaries = "\n".join([
            f"[{i+1}] {doc.page_content[:200]}..."
            for i, doc in enumerate(documents)
        ])

        prompt = f"""검색된 문서들이 질문에 답변하기에 충분한지 평가하세요.

질문: {question}

검색된 문서 요약:
{doc_summaries}

평가:
- CORRECT: 문서들이 질문에 직접 답변 가능
- AMBIGUOUS: 일부 관련 있으나 불충분
- INCORRECT: 관련 없는 문서들

JSON 형식으로 출력:
{{"relevance": "CORRECT/AMBIGUOUS/INCORRECT", "relevant_indices": [관련 문서 번호들], "reason": "판단 이유"}}"""

        try:
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            if "```" in content:
                content = content.split("```")[1].split("```")[0]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content.strip())
            relevance = result.get("relevance", "AMBIGUOUS")

            return {
                "relevance": relevance,
                "should_search_more": relevance != "CORRECT",
                "relevant_doc_indices": result.get("relevant_indices", list(range(len(documents))))
            }
        except:
            return {
                "relevance": "AMBIGUOUS",
                "should_search_more": True,
                "relevant_doc_indices": list(range(len(documents)))
            }
