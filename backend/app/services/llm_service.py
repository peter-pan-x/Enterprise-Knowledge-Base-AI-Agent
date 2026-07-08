import asyncio
import json

import httpx

from app.core.config import settings
from app.schemas.chat import ChatRequest
from app.schemas.rag import RagSource

RAG_SYSTEM_PROMPT = """你是企业知识库 AI 客服 Agent。
你必须优先基于提供的企业知识库片段回答用户问题。

回答要求：
1. 使用简洁、专业的中文。
2. 只依据“知识库片段”回答，不要编造片段中没有的信息。
3. 如果片段不足以回答，明确说明“知识库中没有找到明确依据”。
4. 回答末尾用“来源：”列出使用到的文档名和片段编号。
"""


async def stream_chat_completion(request: ChatRequest, sources: list[RagSource] | None = None):
    sources = sources or []
    if not sources:
        async for chunk in _stream_no_context_answer():
            yield chunk
        return

    if not settings.llm_api_key:
        async for chunk in _stream_demo_rag_answer(sources):
            yield chunk
        return

    async for chunk in _stream_openai_compatible_answer(request, sources):
        yield chunk


async def _stream_no_context_answer():
    answer = (
        "知识库中没有找到与该问题匹配的明确依据。"
        "为了避免编造答案，我暂时不能直接回答。"
        "你可以补充相关企业文档，或换一种更具体的问法后再试。"
    )
    for token in answer:
        await asyncio.sleep(0.01)
        yield token


async def _stream_demo_rag_answer(sources: list[RagSource]):
    used_sources = sources[:2]
    lines = ["根据已上传知识库资料，可以先给出以下回答："]
    for index, source in enumerate(used_sources, start=1):
        lines.append(f"{index}. {source.preview}")
    lines.append("")
    lines.append(
        "以上回答来自当前召回的知识库片段。后续接入真实 DeepSeek API Key 后，"
        "系统会把这些片段注入 Prompt，由模型生成更自然的客服回复。"
    )
    lines.append("")
    lines.append(
        "来源："
        + "；".join(
            f"{source.filename}，片段 {source.chunk_index + 1}" for source in used_sources
        )
    )
    answer = "\n".join(lines)
    for token in answer:
        await asyncio.sleep(0.01)
        yield token


async def _stream_openai_compatible_answer(request: ChatRequest, sources: list[RagSource]):
    messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]
    messages.extend(message.model_dump() for message in request.history[-8:])
    messages.append(
        {
            "role": "user",
            "content": _build_rag_user_prompt(request.message, sources),
        }
    )

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


def _build_rag_user_prompt(question: str, sources: list[RagSource]) -> str:
    context_blocks = []
    for index, source in enumerate(sources, start=1):
        page_text = f"，页码 {source.page_number}" if source.page_number else ""
        context_blocks.append(
            f"[片段 {index}] 文档：{source.filename}{page_text}，chunk_index：{source.chunk_index}\n"
            f"{source.preview}"
        )

    return (
        "用户问题：\n"
        f"{question}\n\n"
        "知识库片段：\n"
        + "\n\n".join(context_blocks)
        + "\n\n请基于上述片段回答，并在末尾列出来源。"
    )
