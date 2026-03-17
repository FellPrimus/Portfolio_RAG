"""
LLM Gateway Service API

FastAPI service for LLM API abstraction (CLOVA Studio)
Port: 8002
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .providers.clova_studio import ClovaStudioClient

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Request/Response Models
class Message(BaseModel):
    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class GenerateRequest(BaseModel):
    messages: List[Message] = Field(..., description="List of messages for chat completion")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Generation temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=20480, description="Maximum tokens to generate")
    stop: Optional[List[str]] = Field(default=None, description="Stop sequences")
    stream: bool = Field(default=False, description="Enable streaming response")


class GenerateResponse(BaseModel):
    content: str
    model: str
    usage: dict
    stop_reason: Optional[str]


class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str


# Global LLM client
llm_client: Optional[ClovaStudioClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global llm_client

    # Startup: Initialize LLM client
    logger.info("Starting LLM Gateway Service...")

    api_key = os.getenv("CLOVASTUDIO_API_KEY")
    if not api_key:
        logger.error("CLOVASTUDIO_API_KEY not set!")
        raise ValueError("CLOVASTUDIO_API_KEY environment variable is required")

    model = os.getenv("LLM_MODEL", "HCX-007")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.5"))
    max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    llm_client = ClovaStudioClient(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )

    logger.info(f"LLM client initialized - model: {model}")

    yield

    # Shutdown
    logger.info("Shutting down LLM Gateway Service...")


app = FastAPI(
    title="LLM Gateway Service",
    description="LLM API Gateway for RAG System (CLOVA Studio)",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        provider="clova_studio",
        model=llm_client.model if llm_client else "not_initialized"
    )


@app.get("/readyz")
async def readiness_check():
    """Kubernetes readiness probe"""
    if llm_client:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="LLM client not initialized")


@app.get("/livez")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}


@app.post("/llm/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Generate LLM response (non-streaming)
    """
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        result = await llm_client.generate(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stop=request.stop
        )

        return GenerateResponse(
            content=result["content"],
            model=result["model"],
            usage=result["usage"],
            stop_reason=result.get("stop_reason")
        )

    except Exception as e:
        logger.error(f"Error generating response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/llm/stream")
async def stream(request: GenerateRequest):
    """
    Generate LLM response (streaming)
    """
    if not llm_client:
        raise HTTPException(status_code=503, detail="LLM client not initialized")

    async def generate_stream():
        try:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]

            async for chunk in llm_client.stream(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stop=request.stop
            ):
                yield f"data: {chunk}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in streaming: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream"
    )


@app.get("/info")
async def model_info():
    """Get LLM model information"""
    if not llm_client:
        return {"error": "LLM client not initialized"}

    return {
        "provider": "clova_studio",
        "model": llm_client.model,
        "temperature": llm_client.temperature,
        "max_tokens": llm_client.max_tokens
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
