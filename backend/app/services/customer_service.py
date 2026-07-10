import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.schemas.customer_service import ConversationDetail, ConversationSummary, StoredMessage
from app.schemas.rag import RagSource

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "customer_service.json"
_STATE_LOCK = threading.RLock()


class CustomerServiceError(Exception):
    pass


def _empty_state() -> dict[str, list[dict]]:
    return {"conversations": [], "feedback": [], "knowledge_gaps": [], "handoffs": []}


def _load_state() -> dict[str, list[dict]]:
    with _STATE_LOCK:
        if not DATA_PATH.exists():
            return _empty_state()
        try:
            state = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CustomerServiceError("客服数据读取失败") from exc
        defaults = _empty_state()
        for key, value in defaults.items():
            state.setdefault(key, value)
        return state


def _save_state(state: dict[str, list[dict]]) -> None:
    with _STATE_LOCK:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=DATA_PATH.parent,
                prefix=f".{DATA_PATH.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                json.dump(state, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                temporary_path = Path(temporary_file.name)
            os.replace(temporary_path, DATA_PATH)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def start_exchange(conversation_id: str | None, question: str) -> tuple[str, str, str]:
    with _STATE_LOCK:
        state = _load_state()
        now = datetime.now(UTC).isoformat()
        conversation = _find_conversation(state, conversation_id) if conversation_id else None
        if conversation is None:
            conversation_id = uuid4().hex
            conversation = {
                "id": conversation_id,
                "title": question.strip()[:36] or "新会话",
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            state["conversations"].insert(0, conversation)

        user_message_id = uuid4().hex
        assistant_message_id = uuid4().hex
        conversation["messages"].append(
            {"id": user_message_id, "role": "user", "content": question, "sources": [], "created_at": now}
        )
        conversation["updated_at"] = now
        _save_state(state)
        return conversation["id"], user_message_id, assistant_message_id


def complete_exchange(
    conversation_id: str,
    assistant_message_id: str,
    answer: str,
    sources: list[RagSource],
    question: str,
    resolved_by_tool: bool = False,
) -> None:
    with _STATE_LOCK:
        state = _load_state()
        conversation = _find_conversation(state, conversation_id)
        if conversation is None:
            raise CustomerServiceError("会话不存在")
        now = datetime.now(UTC).isoformat()
        conversation["messages"].append(
            {
                "id": assistant_message_id,
                "role": "assistant",
                "content": answer,
                "sources": [source.model_dump(mode="json") for source in sources],
                "created_at": now,
            }
        )
        conversation["updated_at"] = now
        if not sources and not resolved_by_tool:
            state["knowledge_gaps"].insert(
                0,
                {
                    "id": uuid4().hex,
                    "conversation_id": conversation_id,
                    "message_id": assistant_message_id,
                    "question": question,
                    "status": "open",
                    "created_at": now,
                },
            )
        _save_state(state)


def list_conversations() -> list[ConversationSummary]:
    state = _load_state()
    return [_summary(item) for item in state["conversations"]]


def get_admin_snapshot() -> dict[str, list[dict]]:
    state = _load_state()
    return {
        "conversations": list(state["conversations"]),
        "feedback": list(state["feedback"]),
        "knowledge_gaps": list(state["knowledge_gaps"]),
        "handoffs": list(state["handoffs"]),
    }


def update_knowledge_gap_status(gap_id: str, status: str) -> dict:
    with _STATE_LOCK:
        state = _load_state()
        gap = next((item for item in state["knowledge_gaps"] if item["id"] == gap_id), None)
        if gap is None:
            raise CustomerServiceError("知识缺口不存在")
        gap["status"] = status
        gap["updated_at"] = datetime.now(UTC).isoformat()
        _save_state(state)
        return gap


def get_conversation(conversation_id: str) -> ConversationDetail:
    state = _load_state()
    conversation = _find_conversation(state, conversation_id)
    if conversation is None:
        raise CustomerServiceError("会话不存在")
    summary = _summary(conversation)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[StoredMessage.model_validate(item) for item in conversation["messages"]],
    )


def save_feedback(conversation_id: str, message_id: str, rating: str) -> dict:
    with _STATE_LOCK:
        state = _load_state()
        _require_assistant_message(state, conversation_id, message_id)
        existing = next(
            (item for item in state["feedback"] if item["conversation_id"] == conversation_id and item["message_id"] == message_id),
            None,
        )
        if existing:
            existing["rating"] = rating
            existing["updated_at"] = datetime.now(UTC).isoformat()
            result = existing
        else:
            result = {
                "id": uuid4().hex,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "rating": rating,
                "created_at": datetime.now(UTC).isoformat(),
            }
            state["feedback"].insert(0, result)
        _save_state(state)
        return result


def create_handoff(conversation_id: str, message_id: str | None, note: str) -> dict:
    with _STATE_LOCK:
        state = _load_state()
        conversation = _find_conversation(state, conversation_id)
        if conversation is None:
            raise CustomerServiceError("会话不存在")
        if message_id:
            _require_assistant_message(state, conversation_id, message_id)
        handoff = {
            "id": uuid4().hex,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "note": note,
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
        }
        state["handoffs"].insert(0, handoff)
        _save_state(state)
        return handoff


def _find_conversation(state: dict, conversation_id: str | None) -> dict | None:
    return next((item for item in state["conversations"] if item["id"] == conversation_id), None)


def _require_assistant_message(state: dict, conversation_id: str, message_id: str) -> None:
    conversation = _find_conversation(state, conversation_id)
    if conversation is None:
        raise CustomerServiceError("会话不存在")
    if not any(item["id"] == message_id and item["role"] == "assistant" for item in conversation["messages"]):
        raise CustomerServiceError("AI 回复不存在")


def _summary(conversation: dict) -> ConversationSummary:
    return ConversationSummary(
        id=conversation["id"],
        title=conversation["title"],
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
        message_count=len(conversation["messages"]),
    )
