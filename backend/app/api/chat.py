import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import stream_chat_completion
from app.services.rag_service import search_knowledge_base
from app.services.customer_service import complete_exchange, start_exchange
from app.services.tool_service import handle_tool_request

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    conversation_id, _, assistant_message_id = start_exchange(request.conversation_id, request.message)
    tool_execution = handle_tool_request(request.message)
    if tool_execution:
        complete_exchange(
            conversation_id,
            assistant_message_id,
            tool_execution.answer,
            [],
            request.message,
            resolved_by_tool=True,
        )
        return ChatResponse(
            answer=tool_execution.answer,
            sources=[],
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            tool_name=tool_execution.tool_name,
        )
    sources = search_knowledge_base(request.message)
    chunks: list[str] = []
    async for chunk in stream_chat_completion(request, sources):
        chunks.append(chunk)
    answer = "".join(chunks)
    complete_exchange(conversation_id, assistant_message_id, answer, sources, request.message)
    return ChatResponse(
        answer=answer,
        sources=sources,
        conversation_id=conversation_id,
        assistant_message_id=assistant_message_id,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    async def event_stream():
        conversation_id, _, assistant_message_id = start_exchange(request.conversation_id, request.message)
        tool_execution = handle_tool_request(request.message)
        if tool_execution:
            metadata = {
                "type": "sources",
                "sources": [],
                "conversation_id": conversation_id,
                "assistant_message_id": assistant_message_id,
            }
            yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'tool', 'tool_name': tool_execution.tool_name, 'result': tool_execution.result}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'delta', 'content': tool_execution.answer}, ensure_ascii=False)}\n\n"
            complete_exchange(
                conversation_id,
                assistant_message_id,
                tool_execution.answer,
                [],
                request.message,
                resolved_by_tool=True,
            )
            yield 'data: {"type":"done"}\n\n'
            return
        sources = search_knowledge_base(request.message)
        sources_payload = [source.model_dump(mode="json") for source in sources]
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'conversation_id': conversation_id, 'assistant_message_id': assistant_message_id}, ensure_ascii=False)}\n\n"
        chunks: list[str] = []
        async for chunk in stream_chat_completion(request, sources):
            chunks.append(chunk)
            payload = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
            yield f"data: {payload}\n\n"
        complete_exchange(conversation_id, assistant_message_id, "".join(chunks), sources, request.message)
        yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
