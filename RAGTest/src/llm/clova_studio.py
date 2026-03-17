"""
CLOVA Studio v3 Chat Completions API

네이버 클라우드 플랫폼의 CLOVA Studio HCX-007 모델 지원
https://api.ncloud-docs.com/docs/clovastudio-chatcompletionsv3-thinking
"""

import json
import uuid
import logging
from typing import Any, Dict, Iterator, List, Optional, Union

import requests
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

logger = logging.getLogger(__name__)


class ChatClovaStudio(BaseChatModel):
    """
    CLOVA Studio v3 Chat Completions API 클라이언트

    네이버 클라우드 플랫폼의 HCX-007 모델을 사용합니다.

    Example:
        >>> from src.llm import ChatClovaStudio
        >>> llm = ChatClovaStudio(
        ...     api_key="nv-xxxxx",
        ...     model="HCX-007",
        ...     temperature=0.5
        ... )
        >>> response = llm.invoke("안녕하세요?")
        >>> print(response.content)
    """

    # API 설정
    api_key: str = Field(..., description="CLOVA Studio API 키")
    model: str = Field(default="HCX-007", description="모델명 (HCX-007)")
    base_url: str = Field(
        default="https://clovastudio.stream.ntruss.com/v3/chat-completions",
        description="API 베이스 URL"
    )

    # 생성 파라미터
    temperature: float = Field(default=0.5, ge=0.0, le=1.0, description="생성 온도")
    top_p: float = Field(default=0.8, ge=0.0, le=1.0, description="Top-P 샘플링")
    top_k: int = Field(default=0, ge=0, description="Top-K 샘플링")
    max_tokens: int = Field(default=4096, ge=1, le=20480, description="최대 토큰 수")
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0, description="반복 페널티")
    stop_sequences: List[str] = Field(default_factory=list, description="중단 시퀀스")
    seed: int = Field(default=0, description="랜덤 시드 (0=무작위)")
    include_ai_filters: bool = Field(default=True, description="AI 필터 포함")
    thinking_effort: str = Field(default="none", description="Thinking 모드 (none, low, medium, high)")

    # 요청 설정
    timeout: int = Field(default=120, description="요청 타임아웃 (초)")

    class Config:
        """Pydantic 설정"""
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        """LLM 타입 식별자"""
        return "clova-studio"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """모델 식별 파라미터"""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

    def _get_request_headers(self, stream: bool = False) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """LangChain 메시지를 CLOVA Studio 형식으로 변환"""
        converted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                converted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                converted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                converted.append({"role": "assistant", "content": msg.content})
            else:
                # 기타 메시지는 user로 처리
                converted.append({"role": "user", "content": str(msg.content)})
        return converted

    def _build_request_body(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """API 요청 바디 생성"""
        return {
            "messages": messages,
            "thinking": {"effort": self.thinking_effort},
            "topP": self.top_p,
            "topK": self.top_k,
            "maxCompletionTokens": self.max_tokens,
            "temperature": self.temperature,
            "repetitionPenalty": self.repetition_penalty,
            "stop": self.stop_sequences,
            "seed": self.seed,
            "includeAiFilters": self.include_ai_filters,
        }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """동기 생성"""
        # 메시지 변환
        converted_messages = self._convert_messages(messages)

        # 요청 바디 구성
        body = self._build_request_body(converted_messages)
        if stop:
            body["stop"] = stop

        # API 호출
        url = f"{self.base_url}/{self.model}"
        headers = self._get_request_headers(stream=False)

        logger.debug(f"CLOVA Studio API 호출: {url}")
        logger.debug(f"요청 바디: {json.dumps(body, ensure_ascii=False)[:500]}...")

        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            logger.debug(f"응답: {json.dumps(result, ensure_ascii=False)[:500]}...")

            # 응답 파싱
            content = self._parse_response(result)

            # 토큰 사용량
            usage = result.get("usage", {})

            message = AIMessage(
                content=content,
                additional_kwargs={
                    "model": self.model,
                    "usage": usage,
                    "stop_reason": result.get("stopReason"),
                }
            )

            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        except requests.exceptions.RequestException as e:
            logger.error(f"CLOVA Studio API 호출 실패: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"응답 내용: {e.response.text}")
            raise RuntimeError(f"CLOVA Studio API 호출 실패: {e}")

    def _parse_response(self, result: Dict[str, Any]) -> str:
        """API 응답에서 content 추출"""
        # 일반 응답
        if "message" in result:
            return result["message"].get("content", "")

        # 스트리밍 완료 응답
        if "result" in result:
            return result["result"].get("message", {}).get("content", "")

        # 기타 형식
        if "content" in result:
            return result["content"]

        logger.warning(f"예상치 못한 응답 형식: {result}")
        return str(result)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """스트리밍 생성 (Server-Sent Events)"""
        # 메시지 변환
        converted_messages = self._convert_messages(messages)

        # 요청 바디 구성
        body = self._build_request_body(converted_messages)
        if stop:
            body["stop"] = stop

        # API 호출 (스트리밍)
        url = f"{self.base_url}/{self.model}"
        headers = self._get_request_headers(stream=True)

        logger.debug(f"CLOVA Studio 스트리밍 API 호출: {url}")

        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()

            # SSE 파싱
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                # SSE 형식: "data: {...}"
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)

                        # 델타 컨텐츠 추출
                        content = ""
                        if "message" in data:
                            content = data["message"].get("content", "")
                        elif "delta" in data:
                            content = data["delta"].get("content", "")

                        if content:
                            chunk = ChatGenerationChunk(
                                message=AIMessageChunk(content=content)
                            )

                            if run_manager:
                                run_manager.on_llm_new_token(content)

                            yield chunk

                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 실패: {data_str[:100]}, 에러: {e}")
                        continue

                # event: 라인 처리 (선택적)
                elif line.startswith("event:"):
                    event_type = line[6:].strip()
                    logger.debug(f"SSE 이벤트: {event_type}")

        except requests.exceptions.RequestException as e:
            logger.error(f"CLOVA Studio 스트리밍 API 호출 실패: {e}")
            raise RuntimeError(f"CLOVA Studio 스트리밍 API 호출 실패: {e}")

    def invoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Dict] = None,
        **kwargs: Any
    ) -> AIMessage:
        """
        간편 호출 메서드

        Args:
            input: 문자열 또는 메시지 리스트

        Returns:
            AIMessage: 응답 메시지
        """
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        else:
            messages = input

        result = self._generate(messages, **kwargs)
        return result.generations[0].message

    def stream(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Dict] = None,
        **kwargs: Any
    ) -> Iterator[AIMessageChunk]:
        """
        스트리밍 호출 메서드

        Args:
            input: 문자열 또는 메시지 리스트

        Yields:
            AIMessageChunk: 응답 청크
        """
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        else:
            messages = input

        for chunk in self._stream(messages, **kwargs):
            yield chunk.message
