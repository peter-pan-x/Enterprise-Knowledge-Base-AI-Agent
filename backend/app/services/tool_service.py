import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.schemas.tools import OrderStatusResponse, TicketResponse, ToolCallRecord

TOOL_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "tool_logs.json"
_TOOL_LOCK = threading.RLock()

MOCK_ORDERS = {
    "10001": OrderStatusResponse(order_id="10001", status="已发货", carrier="顺丰速运", tracking_number="SF10001001", estimated_delivery="明天"),
    "10002": OrderStatusResponse(order_id="10002", status="处理中"),
    "10003": OrderStatusResponse(order_id="10003", status="已签收", carrier="京东物流", tracking_number="JD10003003"),
}


class ToolServiceError(Exception):
    pass


@dataclass(frozen=True)
class ToolExecution:
    tool_name: str
    answer: str
    arguments: dict
    result: dict


def get_order_status(order_id: str) -> OrderStatusResponse:
    order = MOCK_ORDERS.get(order_id)
    if order is None:
        raise ToolServiceError("未找到该订单")
    _try_append_tool_log("get_order_status", {"order_id": order_id}, order.model_dump(mode="json"))
    return order


def create_ticket(description: str) -> TicketResponse:
    ticket = TicketResponse(ticket_id=f"TK-{uuid4().hex[:8].upper()}", status="open", description=description)
    _try_append_tool_log("create_ticket", {"description": description}, ticket.model_dump(mode="json"))
    return ticket


def _handle_tool_request_legacy(message: str) -> ToolExecution | None:
    order_match = re.search(r"(?:订单(?:号)?\s*)?(\d{5,})", message)
    if order_match and any(keyword in message for keyword in ("订单", "物流", "发货", "到哪", "送达")):
        order_id = order_match.group(1)
        try:
            order = get_order_status(order_id)
            details = [f"订单 {order.order_id} 当前状态为“{order.status}”"]
            if order.carrier:
                details.append(f"承运方：{order.carrier}")
            if order.tracking_number:
                details.append(f"运单号：{order.tracking_number}")
            if order.estimated_delivery:
                details.append(f"预计{order.estimated_delivery}送达")
            answer = "，".join(details) + "。"
            return ToolExecution("get_order_status", answer, {"order_id": order_id}, order.model_dump(mode="json"))
        except ToolServiceError:
            result = {"order_id": order_id, "status": "not_found"}
            _try_append_tool_log("get_order_status", {"order_id": order_id}, result)
            return ToolExecution("get_order_status", f"没有查询到订单 {order_id}，请核对订单号后重试。", {"order_id": order_id}, result)

    if any(keyword in message for keyword in ("创建工单", "提交工单", "转工单")):
        ticket = create_ticket(message.strip())
        answer = f"已为你创建工单 {ticket.ticket_id}，当前状态为待处理。工作人员会根据问题描述继续跟进。"
        return ToolExecution("create_ticket", answer, {"description": message.strip()}, ticket.model_dump(mode="json"))
    return None


def handle_tool_request(message: str) -> ToolExecution | None:
    """Recognize the supported Chinese tool intents using encoding-safe literals."""
    order_match = re.search(r"(?:\u8ba2\u5355(?:\u53f7)?\s*)?(\d{5,})", message)
    order_keywords = ("\u8ba2\u5355", "\u7269\u6d41", "\u53d1\u8d27", "\u5230\u54ea", "\u9001\u8fbe")
    if order_match and any(keyword in message for keyword in order_keywords):
        order_id = order_match.group(1)
        try:
            order = get_order_status(order_id)
            details = [f"\u8ba2\u5355 {order.order_id} \u5f53\u524d\u72b6\u6001\u4e3a\u201c{order.status}\u201d"]
            if order.carrier:
                details.append(f"\u627f\u8fd0\u65b9\uff1a{order.carrier}")
            if order.tracking_number:
                details.append(f"\u8fd0\u5355\u53f7\uff1a{order.tracking_number}")
            if order.estimated_delivery:
                details.append(f"\u9884\u8ba1{order.estimated_delivery}\u9001\u8fbe")
            return ToolExecution("get_order_status", "\uff1b".join(details) + "\u3002", {"order_id": order_id}, order.model_dump(mode="json"))
        except ToolServiceError:
            result = {"order_id": order_id, "status": "not_found"}
            _try_append_tool_log("get_order_status", {"order_id": order_id}, result)
            answer = f"\u6ca1\u6709\u67e5\u8be2\u5230\u8ba2\u5355 {order_id}\uff0c\u8bf7\u6838\u5bf9\u8ba2\u5355\u53f7\u540e\u91cd\u8bd5\u3002"
            return ToolExecution("get_order_status", answer, {"order_id": order_id}, result)

    ticket_keywords = ("\u521b\u5efa\u5de5\u5355", "\u63d0\u4ea4\u5de5\u5355", "\u8f6c\u5de5\u5355")
    if any(keyword in message for keyword in ticket_keywords):
        ticket = create_ticket(message.strip())
        answer = f"\u5df2\u4e3a\u4f60\u521b\u5efa\u5de5\u5355 {ticket.ticket_id}\uff0c\u5f53\u524d\u72b6\u6001\u4e3a\u5f85\u5904\u7406\u3002"
        return ToolExecution("create_ticket", answer, {"description": message.strip()}, ticket.model_dump(mode="json"))
    return None


def list_tool_logs(limit: int = 100) -> list[ToolCallRecord]:
    with _TOOL_LOCK:
        if not TOOL_LOG_PATH.exists():
            return []
        try:
            raw = json.loads(TOOL_LOG_PATH.read_text(encoding="utf-8"))
            return [ToolCallRecord.model_validate(item) for item in raw[:limit]]
        except (OSError, json.JSONDecodeError, ValueError):
            return []


def _append_tool_log(tool_name: str, arguments: dict, result: dict) -> None:
    with _TOOL_LOCK:
        TOOL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        logs = []
        if TOOL_LOG_PATH.exists():
            try:
                logs = json.loads(TOOL_LOG_PATH.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logs = []
        entry = ToolCallRecord(id=uuid4().hex, tool_name=tool_name, arguments=arguments, result=result, created_at=datetime.now(UTC).isoformat())
        logs.insert(0, entry.model_dump(mode="json"))
        _atomic_write(logs[:500])


def _try_append_tool_log(tool_name: str, arguments: dict, result: dict) -> None:
    try:
        _append_tool_log(tool_name, arguments, result)
    except OSError:
        # A diagnostics failure must not make the business tool unavailable.
        return


def _atomic_write(payload: list[dict]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=TOOL_LOG_PATH.parent, prefix=f".{TOOL_LOG_PATH.name}.", suffix=".tmp", delete=False) as temporary_file:
            json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, TOOL_LOG_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
