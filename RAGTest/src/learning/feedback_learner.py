"""
피드백 기반 학습 시스템

사용자 피드백을 분석하여:
1. 자주 묻는 질문(FAQ) 식별
2. 좋은 답변 패턴 학습
3. 검색 쿼리 개선
4. 프롬프트 최적화
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Tuple
from collections import Counter, defaultdict


class FeedbackLearner:
    """
    피드백 기반 적응형 학습 시스템

    기능:
    1. 질문 패턴 분석 (FAQ 생성)
    2. 좋은 답변 사례 수집
    3. 검색 쿼리 확장 (Query Expansion)
    4. 동적 프롬프트 조정
    """

    def __init__(self, feedback_dir: str = "./data/feedback"):
        self.feedback_dir = feedback_dir
        self.learning_cache_path = "./data/learning_cache.json"

        # 학습 데이터 로드
        self.learning_data = self._load_learning_cache()

    def _load_learning_cache(self) -> dict:
        """학습 캐시 로드"""
        if os.path.exists(self.learning_cache_path):
            try:
                with open(self.learning_cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        return {
            "faq": [],  # 자주 묻는 질문
            "good_answers": [],  # 좋은 답변 사례
            "query_expansions": {},  # 쿼리 확장 매핑
            "common_patterns": [],  # 질문 패턴
            "last_updated": None
        }

    def _save_learning_cache(self):
        """학습 캐시 저장"""
        self.learning_data["last_updated"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(self.learning_cache_path), exist_ok=True)
        with open(self.learning_cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.learning_data, f, ensure_ascii=False, indent=2)

    def analyze_all_feedback(self) -> Dict:
        """
        모든 피드백 분석

        Returns:
            분석 결과 딕셔너리
        """
        if not os.path.exists(self.feedback_dir):
            return {}

        feedback_files = [
            f for f in os.listdir(self.feedback_dir)
            if f.endswith('.json')
        ]

        all_feedback = []
        for file in feedback_files:
            try:
                file_path = os.path.join(self.feedback_dir, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    feedback = json.load(f)
                    all_feedback.append(feedback)
            except:
                continue

        if not all_feedback:
            return {}

        # 1. 자주 묻는 질문 분석
        questions = [fb.get('question', '') for fb in all_feedback if 'question' in fb]
        question_counter = Counter(questions)

        # 2. 좋은 답변 수집 (평점 4-5점)
        good_cases = [
            fb for fb in all_feedback
            if fb.get('rating', 0) >= 4
        ]

        # 3. 나쁜 답변 분석 (평점 1-2점)
        bad_cases = [
            fb for fb in all_feedback
            if fb.get('rating', 0) <= 2
        ]

        # 4. 질문 패턴 추출
        patterns = self._extract_question_patterns(questions)

        return {
            "total_feedback": len(all_feedback),
            "faq": question_counter.most_common(10),
            "good_cases": len(good_cases),
            "bad_cases": len(bad_cases),
            "patterns": patterns,
            "avg_rating": sum(fb.get('rating', 0) for fb in all_feedback) / len(all_feedback)
        }

    def _extract_question_patterns(self, questions: List[str]) -> List[Dict]:
        """
        질문에서 패턴 추출

        예: "비용은?", "가격은?", "얼마인가요?" → "가격 질문" 패턴
        """
        patterns = defaultdict(list)

        # 키워드 그룹
        keyword_groups = {
            "가격/비용": ["비용", "가격", "얼마", "요금", "금액"],
            "기능": ["기능", "할 수 있", "지원", "제공"],
            "방법": ["어떻게", "방법", "설치", "사용법"],
            "차이": ["차이", "비교", "다른점", "vs"],
            "성능": ["성능", "속도", "빠른", "느린"]
        }

        for question in questions:
            for pattern_name, keywords in keyword_groups.items():
                if any(kw in question for kw in keywords):
                    patterns[pattern_name].append(question)

        # 패턴별 빈도 계산
        result = []
        for pattern_name, questions in patterns.items():
            result.append({
                "pattern": pattern_name,
                "count": len(questions),
                "examples": questions[:3]  # 상위 3개 예시
            })

        return sorted(result, key=lambda x: x['count'], reverse=True)

    def learn_from_feedback(self, session_id: str, rating: int, question: str = None):
        """
        개별 피드백에서 학습

        Args:
            session_id: 세션 ID
            rating: 평점 (1-5)
            question: 질문 (선택)
        """
        # 세션 데이터 로드
        session_file = os.path.join(self.feedback_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            return

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                feedback = json.load(f)
        except:
            return

        # 좋은 답변 사례 수집 (평점 4-5)
        if rating >= 4:
            good_case = {
                "question": question or feedback.get('question', ''),
                "answer": feedback.get('answer', ''),
                "rating": rating,
                "timestamp": feedback.get('timestamp', '')
            }

            # 중복 방지
            if good_case not in self.learning_data["good_answers"]:
                self.learning_data["good_answers"].append(good_case)

                # 최대 100개까지만 유지
                if len(self.learning_data["good_answers"]) > 100:
                    self.learning_data["good_answers"] = \
                        self.learning_data["good_answers"][-100:]

        self._save_learning_cache()

    def get_query_expansion(self, question: str) -> List[str]:
        """
        질문을 확장하여 검색 성능 향상

        Args:
            question: 원본 질문

        Returns:
            확장된 쿼리 리스트
        """
        expansions = [question]  # 원본 포함

        # 학습된 FAQ에서 유사 질문 찾기
        for faq_item in self.learning_data.get("faq", []):
            faq_question = faq_item.get("question", "")

            # 간단한 유사도 체크 (키워드 기반)
            question_words = set(question.split())
            faq_words = set(faq_question.split())

            overlap = len(question_words & faq_words)
            if overlap >= 2:  # 2개 이상 키워드 일치
                expansions.append(faq_question)

        return list(set(expansions))  # 중복 제거

    def get_similar_good_answers(self, question: str, top_k: int = 3) -> List[Dict]:
        """
        유사한 좋은 답변 사례 가져오기

        Args:
            question: 질문
            top_k: 반환할 사례 수

        Returns:
            유사한 좋은 답변 사례 리스트
        """
        good_cases = self.learning_data.get("good_answers", [])
        if not good_cases:
            return []

        # 간단한 유사도 계산 (키워드 기반)
        question_words = set(question.split())

        scored_cases = []
        for case in good_cases:
            case_question = case.get("question", "")
            case_words = set(case_question.split())

            # 자카드 유사도
            overlap = len(question_words & case_words)
            union = len(question_words | case_words)
            similarity = overlap / union if union > 0 else 0

            scored_cases.append((similarity, case))

        # 상위 k개 반환
        scored_cases.sort(reverse=True, key=lambda x: x[0])
        return [case for score, case in scored_cases[:top_k] if score > 0.2]

    def update_faq(self, analysis: Dict):
        """
        FAQ 업데이트

        Args:
            analysis: analyze_all_feedback() 결과
        """
        faq_items = analysis.get("faq", [])

        # FAQ 형식으로 변환
        self.learning_data["faq"] = [
            {
                "question": question,
                "count": count,
                "last_asked": datetime.now().isoformat()
            }
            for question, count in faq_items
        ]

        self._save_learning_cache()

    def get_learning_stats(self) -> Dict:
        """
        학습 통계 반환

        Returns:
            학습 통계 딕셔너리
        """
        return {
            "total_faq": len(self.learning_data.get("faq", [])),
            "total_good_answers": len(self.learning_data.get("good_answers", [])),
            "total_query_expansions": len(self.learning_data.get("query_expansions", {})),
            "last_updated": self.learning_data.get("last_updated"),
            "top_faq": self.learning_data.get("faq", [])[:5]
        }

    def suggest_prompt_improvements(self, analysis: Dict) -> List[str]:
        """
        피드백 분석 기반 프롬프트 개선 제안

        Args:
            analysis: 피드백 분석 결과

        Returns:
            개선 제안 리스트
        """
        suggestions = []

        avg_rating = analysis.get("avg_rating", 3.0)
        bad_cases = analysis.get("bad_cases", 0)

        # 평균 평점이 낮으면
        if avg_rating < 3.5:
            suggestions.append(
                "평균 평점이 낮습니다. 프롬프트 전략을 'few_shot'으로 변경하여 "
                "더 구체적인 예시를 제공하는 것을 고려하세요."
            )

        # 나쁜 사례가 많으면
        if bad_cases > 5:
            suggestions.append(
                f"낮은 평점 사례가 {bad_cases}개 발견되었습니다. "
                "문서 검색 개수(retrieval_k)를 늘리거나 품질 점수 기준을 높이세요."
            )

        # 특정 패턴이 자주 나타나면
        patterns = analysis.get("patterns", [])
        if patterns:
            top_pattern = patterns[0]
            suggestions.append(
                f"'{top_pattern['pattern']}' 유형의 질문이 {top_pattern['count']}회 "
                "발생했습니다. 이 유형에 특화된 프롬프트를 추가하는 것을 고려하세요."
            )

        return suggestions


class AdaptivePromptManager:
    """
    적응형 프롬프트 관리자

    피드백 기반으로 프롬프트를 동적으로 조정
    """

    def __init__(self, learner: FeedbackLearner):
        self.learner = learner

    def enhance_prompt_with_examples(self, base_prompt: str, question: str) -> str:
        """
        좋은 답변 사례를 프롬프트에 추가

        Args:
            base_prompt: 기본 프롬프트
            question: 현재 질문

        Returns:
            강화된 프롬프트
        """
        # 유사한 좋은 답변 사례 가져오기
        similar_cases = self.learner.get_similar_good_answers(question, top_k=2)

        if not similar_cases:
            return base_prompt

        # 예시 추가
        examples_section = "\n\n# 참고할 좋은 답변 사례\n\n"

        for i, case in enumerate(similar_cases, 1):
            examples_section += f"""예시 {i}:
질문: {case['question']}
답변: {case['answer']}
(평점: {case['rating']}/5)

"""

        # 프롬프트 앞부분에 예시 추가
        enhanced_prompt = base_prompt.replace(
            "컨텍스트 문서:",
            f"{examples_section}컨텍스트 문서:"
        )

        return enhanced_prompt
