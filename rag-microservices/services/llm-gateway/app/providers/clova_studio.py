"""
CLOVA Studio v3 Chat Completions API Client

Naver Cloud Platform's HCX-007 model support
https://api.ncloud-docs.com/docs/clovastudio-chatcompletionsv3-thinking
"""

import json
import uuid
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ClovaStudioClient:
    """
    Async CLOVA Studio API Client
    """

    def __init__(
        self,
        api_key: str,
        model: str = "HCX-007",
        base_url: str = "https://clovastudio.stream.ntruss.com/v3/chat-completions",
        temperature: float = 0.5,
        top_p: float = 0.8,
        max_tokens: int = 4096,
        timeout: int = 120
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _get_headers(self, stream: bool = False) -> Dict[str, str]:
        """Generate API request headers"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        if stream:
            headers["Accept"] = "text/event-stream"
        return headers

    def _build_request_body(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Build API request body"""
        return {
            "messages": messages,
            "thinking": {"effort": "none"},
            "topP": self.top_p,
            "topK": 0,
            "maxCompletionTokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "repetitionPenalty": 1.1,
            "stop": stop or [],
            "seed": 0,
            "includeAiFilters": True,
        }

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate response (non-streaming)
        """
        url = f"{self.base_url}/{self.model}"
        headers = self._get_headers(stream=False)
        body = self._build_request_body(messages, temperature, max_tokens, stop)

        logger.debug(f"CLOVA Studio API call: {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, headers=headers, json=body)
                response.raise_for_status()
                result = response.json()

                # Extract content
                content = ""
                if "message" in result:
                    content = result["message"].get("content", "")
                elif "result" in result:
                    content = result["result"].get("message", {}).get("content", "")

                usage = result.get("usage", {})

                return {
                    "content": content,
                    "model": self.model,
                    "usage": usage,
                    "stop_reason": result.get("stopReason")
                }

            except httpx.HTTPStatusError as e:
                logger.error(f"CLOVA Studio API error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"CLOVA Studio API error: {e.response.status_code}")
            except Exception as e:
                logger.error(f"CLOVA Studio API call failed: {e}")
                raise

    async def stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop: Optional[List[str]] = None
    ) -> AsyncIterator[str]:
        """
        Generate response (streaming via SSE)
        """
        url = f"{self.base_url}/{self.model}"
        headers = self._get_headers(stream=True)
        body = self._build_request_body(messages, temperature, max_tokens, stop)

        logger.debug(f"CLOVA Studio streaming API call: {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, headers=headers, json=body) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            content = ""
                            if "message" in data:
                                content = data["message"].get("content", "")
                            elif "delta" in data:
                                content = data["delta"].get("content", "")

                            if content:
                                yield content

                        except json.JSONDecodeError:
                            continue
