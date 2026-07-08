import asyncio
import json

import httpx

from app.core.config import settings
from app.schemas.chat import ChatRequest

SYSTEM_PROMPT = """你是企业知识库 AI 客服 Agent 的基础聊天版本。
当前阶段还没有接入 RAG 知识库，所以你需要清楚说明能力边界。

回答要求：
1. 使用简洁、专业的中文。
2. 可以帮助用户梳理问题、解释系统能力和下一步计划。
3. 不要假装已经检索企业知识库。
4. 如果问题需要企业文档依据，请说明后续 RAG 模块接入后可以基于文档回答。
"""


async def stream_chat_completion(request: ChatRequest):
    if not settings.llm_api_key:
        async for chunk in _stream_demo_answer(request.message):
            yield chunk
        return

    async for chunk in _stream_openai_compatible_answer(request):
        yield chunk


async def _stream_demo_answer(message: str):
    answer = (
        "基础聊天链路已经打通。"
        "当前版本还没有接入企业知识库和 RAG，所以我不会假装检索了文档。"
        f"你刚才的问题是：“{message}”。"
        "下一阶段会加入文档上传、解析、切片、向量检索和引用来源展示，"
        "这样就可以基于真实企业资料回答。"
    )
    for token in answer:
        await asyncio.sleep(0.015)
        yield token


async def _stream_openai_compatible_answer(request: ChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(message.model_dump() for message in request.history[-10:])
    messages.append({"role": "user", "content": request.message})

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.llm_base_url.rstrip('/')}/v1/chat/completions"

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                delta = event["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
