import json
import os
import sqlite3
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.schemas.customer_service import ConversationDetail, ConversationSummary, StoredMessage
from app.schemas.rag import RagSource
from app.services.auth_service import DATABASE_PATH

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "customer_service.json"
_STATE_LOCK = threading.RLock()


class CustomerServiceError(Exception):
    pass


def _empty_state() -> dict[str, list[dict]]:
    return {"conversations": [], "feedback": [], "knowledge_gaps": [], "handoffs": [], "tool_calls": []}


def initialize_customer_storage() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _customer_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        existing = connection.execute("SELECT 1 FROM customer_state WHERE id = 1").fetchone()
        if existing is None:
            legacy = _empty_state()
            if DATA_PATH.exists():
                try:
                    legacy = json.loads(DATA_PATH.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
            connection.execute(
                "INSERT INTO customer_state (id, payload, updated_at) VALUES (1, ?, ?)",
                (json.dumps(legacy, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )


def _customer_connection() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE_PATH)


def _load_state() -> dict[str, list[dict]]:
    with _STATE_LOCK:
        initialize_customer_storage()
        try:
            with _customer_connection() as connection:
                row = connection.execute("SELECT payload FROM customer_state WHERE id = 1").fetchone()
            state = json.loads(row[0]) if row else _empty_state()
        except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
            raise CustomerServiceError("客服数据读取失败") from exc
        defaults = _empty_state()
        for key, value in defaults.items():
            state.setdefault(key, value)
        return state


def _save_state(state: dict[str, list[dict]]) -> None:
    with _STATE_LOCK:
        initialize_customer_storage()
        with _customer_connection() as connection:
            connection.execute(
                "UPDATE customer_state SET payload = ?, updated_at = ? WHERE id = 1",
                (json.dumps(state, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )


def start_exchange(user_id: str, conversation_id: str | None, question: str) -> tuple[str, str, str]:
    with _STATE_LOCK:
        state = _load_state()
        now = datetime.now(UTC).isoformat()
        conversation = _find_conversation(state, conversation_id) if conversation_id else None
        if conversation is None:
            conversation_id = uuid4().hex
            conversation = {
                "id": conversation_id,
                "user_id": user_id,
                "title": question.strip()[:36] or "新会话",
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "category": _classify_question(question),
            }
            state["conversations"].insert(0, conversation)

        if conversation.get("user_id") not in (None, user_id):
            raise CustomerServiceError("无权访问该会话")
        conversation.setdefault("user_id", user_id)
        user_message_id = uuid4().hex
        assistant_message_id = uuid4().hex
        conversation["messages"].append(
            {"id": user_message_id, "role": "user", "content": question, "sources": [], "created_at": now}
        )
        conversation["updated_at"] = now
        _save_state(state)
        return conversation["id"], user_message_id, assistant_message_id


def complete_exchange(
    user_id: str,
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
        if conversation.get("user_id") not in (None, user_id):
            raise CustomerServiceError("无权访问该会话")
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


def list_conversations(user_id: str, is_admin: bool = False) -> list[ConversationSummary]:
    state = _load_state()
    conversations = state["conversations"] if is_admin else [
        item for item in state["conversations"] if item.get("user_id") == user_id
    ]
    return [_summary(item) for item in conversations]


def delete_conversation(conversation_id: str, user_id: str, is_admin: bool = False) -> None:
    with _STATE_LOCK:
        state = _load_state()
        conversation = _find_conversation(state, conversation_id)
        if conversation is None or (not is_admin and conversation.get("user_id") != user_id):
            raise CustomerServiceError("会话不存在或无权删除")
        state["conversations"] = [item for item in state["conversations"] if item["id"] != conversation_id]
        for key in ("feedback", "knowledge_gaps", "handoffs", "tool_calls"):
            state[key] = [item for item in state[key] if item.get("conversation_id") != conversation_id]
        _save_state(state)


def get_admin_snapshot() -> dict[str, list[dict]]:
    state = _load_state()
    return {
        "conversations": list(state["conversations"]),
        "feedback": list(state["feedback"]),
        "knowledge_gaps": list(state["knowledge_gaps"]),
        "handoffs": list(state["handoffs"]),
        "tool_calls": list(state["tool_calls"]),
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


def get_conversation(conversation_id: str, user_id: str, is_admin: bool = False) -> ConversationDetail:
    state = _load_state()
    conversation = _find_conversation(state, conversation_id)
    if conversation is None:
        raise CustomerServiceError("会话不存在")
    if not is_admin and conversation.get("user_id") != user_id:
        raise CustomerServiceError("无权访问该会话")
    summary = _summary(conversation)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[StoredMessage.model_validate(item) for item in conversation["messages"]],
    )


def save_feedback(user_id: str, conversation_id: str, message_id: str, rating: str) -> dict:
    with _STATE_LOCK:
        state = _load_state()
        _require_assistant_message(state, conversation_id, message_id, user_id)
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


def create_handoff(user_id: str, conversation_id: str, message_id: str | None, note: str) -> dict:
    with _STATE_LOCK:
        state = _load_state()
        conversation = _find_conversation(state, conversation_id)
        if conversation is None:
            raise CustomerServiceError("会话不存在")
        if conversation.get("user_id") not in (None, user_id):
            raise CustomerServiceError("无权访问该会话")
        if message_id:
            _require_assistant_message(state, conversation_id, message_id, user_id)
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


def record_tool_call(
    user_id: str,
    conversation_id: str,
    tool_name: str,
    arguments: dict,
    result: dict,
    status: str = "success",
) -> dict:
    """Persist the business context missing from the diagnostic-only tool log."""
    with _STATE_LOCK:
        state = _load_state()
        conversation = _find_conversation(state, conversation_id)
        if conversation is None or conversation.get("user_id") not in (None, user_id):
            raise CustomerServiceError("无权访问该会话")
        entry = {
            "id": uuid4().hex,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
            "status": status,
            "created_at": datetime.now(UTC).isoformat(),
        }
        state["tool_calls"].insert(0, entry)
        _save_state(state)
        return entry


def _find_conversation(state: dict, conversation_id: str | None) -> dict | None:
    return next((item for item in state["conversations"] if item["id"] == conversation_id), None)


def _require_assistant_message(state: dict, conversation_id: str, message_id: str, user_id: str | None = None) -> None:
    conversation = _find_conversation(state, conversation_id)
    if conversation is None:
        raise CustomerServiceError("会话不存在")
    if user_id and conversation.get("user_id") not in (None, user_id):
        raise CustomerServiceError("无权访问该会话")
    if not any(item["id"] == message_id and item["role"] == "assistant" for item in conversation["messages"]):
        raise CustomerServiceError("AI 回复不存在")


def _summary(conversation: dict) -> ConversationSummary:
    return ConversationSummary(
        id=conversation["id"],
        title=conversation["title"],
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
        message_count=len(conversation["messages"]),
        category=conversation.get("category", "other"),
    )


def _classify_question(question: str) -> str:
    rules = {
        "after_sales": ("退款", "退货", "保修", "售后"),
        "order": ("订单", "物流", "发货", "送达"),
        "product": ("产品", "规格", "使用", "成分"),
        "certificate": ("证书", "认证", "检测"),
    }
    return next((name for name, keywords in rules.items() if any(word in question for word in keywords)), "other")
