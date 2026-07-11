import json
import time

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import stream_chat_completion
from app.services.rag_service import search_knowledge_base
from app.services.customer_service import complete_exchange, get_conversation, record_tool_call, start_exchange
from app.services.tool_service import handle_tool_request
from app.services.auth_service import CurrentUser, get_current_user
from app.services.audit_service import record_generation_trace
from app.core.config import settings

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    started_at = time.perf_counter()
    conversation_id, _, assistant_message_id = start_exchange(user.id, request.conversation_id, request.message)
    tool_execution = handle_tool_request(request.message)
    if tool_execution:
        record_tool_call(
            user.id, conversation_id, tool_execution.tool_name, tool_execution.arguments, tool_execution.result
        )
        complete_exchange(
            user.id,
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
    sources = search_knowledge_base(request.message, knowledge_base_id=request.knowledge_base_id, category=request.category)
    chunks: list[str] = []
    async for chunk in stream_chat_completion(request, sources):
        chunks.append(chunk)
    answer = "".join(chunks)
    record_generation_trace(request.message, answer, len(sources), int((time.perf_counter() - started_at) * 1000), settings.llm_model)
    complete_exchange(user.id, conversation_id, assistant_message_id, answer, sources, request.message)
    return ChatResponse(
        answer=answer,
        sources=sources,
        conversation_id=conversation_id,
        assistant_message_id=assistant_message_id,
    )


@router.post("/regenerate", response_model=ChatResponse)
async def regenerate(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
    """Regenerate the latest user question as a new auditable turn in the same conversation."""
    if not request.conversation_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="conversation_id is required")
    conversation = get_conversation(request.conversation_id, user.id, user.role == "admin")
    last_user = next((item.content for item in reversed(conversation.messages) if item.role == "user"), None)
    if not last_user:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="会话中没有可重新生成的问题")
    return await chat(request.model_copy(update={"message": last_user, "history": []}), user)


@router.post("/stream")
async def chat_stream(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> StreamingResponse:
    async def event_stream():
        started_at = time.perf_counter()
        conversation_id, _, assistant_message_id = start_exchange(user.id, request.conversation_id, request.message)
        try:
            tool_execution = handle_tool_request(request.message)
            if tool_execution:
                record_tool_call(
                    user.id, conversation_id, tool_execution.tool_name, tool_execution.arguments, tool_execution.result
                )
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
                    user.id,
                    conversation_id,
                    assistant_message_id,
                    tool_execution.answer,
                    [],
                    request.message,
                    resolved_by_tool=True,
                )
                yield 'data: {"type":"done"}\n\n'
                return
            sources = search_knowledge_base(request.message, knowledge_base_id=request.knowledge_base_id, category=request.category)
            sources_payload = [source.model_dump(mode="json") for source in sources]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload, 'conversation_id': conversation_id, 'assistant_message_id': assistant_message_id}, ensure_ascii=False)}\n\n"
            chunks: list[str] = []
            async for chunk in stream_chat_completion(request, sources):
                chunks.append(chunk)
                payload = json.dumps({"type": "delta", "content": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            complete_exchange(user.id, conversation_id, assistant_message_id, "".join(chunks), sources, request.message)
            record_generation_trace(request.message, "".join(chunks), len(sources), int((time.perf_counter() - started_at) * 1000), settings.llm_model)
            yield 'data: {"type":"done"}\n\n'
        except Exception:
            fallback = "抱歉，本次回答生成失败，请稍后重试。"
            complete_exchange(user.id, conversation_id, assistant_message_id, fallback, [], request.message)
            yield f"data: {json.dumps({'type': 'error', 'message': fallback}, ensure_ascii=False)}\n\n"
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
