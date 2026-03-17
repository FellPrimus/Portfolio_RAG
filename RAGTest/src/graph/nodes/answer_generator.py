"""
답변 생성 노드

LLM 기반 답변 생성을 담당합니다.
"""
from __future__ import annotations

from typing import Optional

from src.graph.state import QualityRAGState


class AnswerGeneratorNode:
    """답변 생성 노드"""

    def __init__(
        self,
        llm,
        creative_llm,
        llm_selector,
        system_prompt_template: str,
        prompt_strategy: str = "balanced"
    ):
        """
        Args:
            llm: 기본 LLM 인스턴스
            creative_llm: 창의적 LLM (재시도용)
            llm_selector: LLMSelector 인스턴스
            system_prompt_template: 시스템 프롬프트 템플릿
            prompt_strategy: 프롬프트 전략
        """
        self.llm = llm
        self.creative_llm = creative_llm
        self.llm_selector = llm_selector
        self.system_prompt_template = system_prompt_template
        self.prompt_strategy = prompt_strategy

    def __call__(self, state: 'QualityRAGState') -> 'QualityRAGState':
        """
        답변 생성 실행

        - 검색된 문서를 컨텍스트로 활용
        - 할루시네이션 방지 프롬프트 사용
        """
        print("[4/7] Generating answer...")

        if state.get('error'):
            return state

        try:
            # 컨텍스트 구성
            context = self._build_context(state.get('retrieved_docs', []))

            # 카테고리 추출 및 LLM 선택
            categories = self._extract_categories(state.get('retrieved_docs', []))
            secure_mode = state.get('secure_mode', False)

            selected_llm, model_name, selection_reason = self.llm_selector.select_for_categories(
                categories, secure_mode
            )

            state['used_model'] = model_name
            state['model_selection_reason'] = selection_reason
            print(f"   Model: {selection_reason}")

            # 재시도 시 creative_llm 사용
            if state.get('retry_count', 0) > 0:
                llm = self.creative_llm
            else:
                llm = selected_llm

            # 답변 생성
            prompt = self.system_prompt_template.format(
                context=context,
                question=state['question']
            )

            response = llm.invoke(prompt)
            answer = response.content if hasattr(response, 'content') else str(response)

            state['raw_answer'] = answer
            state['answer'] = answer
            state['steps'].append(f"Answer generated (strategy: {self.prompt_strategy})")

        except Exception as e:
            state['error'] = f"Answer generation failed: {str(e)}"
            state['steps'].append("Error: Answer generation failed")

        return state

    def _build_context(self, docs: list) -> str:
        """문서로부터 컨텍스트 구성"""
        if not docs:
            return "No relevant documents found."

        context_parts = []
        for i, doc in enumerate(docs):
            source_url = doc.metadata.get('source', '')
            doc_context = f"[Document {i+1}]\n{doc.page_content}"
            if source_url and source_url.startswith('http'):
                doc_context += f"\n[Reference URL: {source_url}]"
            context_parts.append(doc_context)

        return "\n\n---\n\n".join(context_parts)

    def _extract_categories(self, docs: list) -> list:
        """문서에서 카테고리 추출"""
        categories = []
        for doc in docs:
            category_id = doc.metadata.get('category_id', 'general')
            categories.append(category_id)
        return categories
