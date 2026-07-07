import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import stream_chat_completion

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    chunks: list[str] = []
    async for chunk in stream_chat_completion(request):
        chunks.append(chunk)
    return ChatResponse(answer="".join(chunks))


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        async for chunk in stream_chat_completion(request):
            payload = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
