import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import stream_chat_completion
from app.services.rag_service import search_knowledge_base

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    sources = search_knowledge_base(request.message)
    chunks: list[str] = []
    async for chunk in stream_chat_completion(request, sources):
        chunks.append(chunk)
    return ChatResponse(answer="".join(chunks), sources=sources)


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        sources = search_knowledge_base(request.message)
        sources_payload = [source.model_dump(mode="json") for source in sources]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload}, ensure_ascii=False)}\n\n"
        async for chunk in stream_chat_completion(request, sources):
            payload = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
