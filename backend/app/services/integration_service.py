"""Stable extension points for customer-specific channel and business integrations.

Deployments replace these adapters; RAG and customer-service flows do not change.
"""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class InboundMessage:
    channel: str
    external_user_id: str
    text: str
    conversation_ref: str | None = None


class ChannelAdapter(Protocol):
    name: str

    def parse_inbound(self, payload: dict) -> InboundMessage: ...
    def send_text(self, external_user_id: str, text: str) -> None: ...


class BusinessAdapter(Protocol):
    name: str

    def order_status(self, order_id: str) -> dict: ...
    def create_ticket(self, description: str) -> dict: ...


_channel_adapters: dict[str, ChannelAdapter] = {}
_business_adapter: BusinessAdapter | None = None


def register_channel_adapter(adapter: ChannelAdapter) -> None:
    _channel_adapters[adapter.name] = adapter


def list_channel_adapters() -> list[str]:
    return sorted(_channel_adapters)


def set_business_adapter(adapter: BusinessAdapter) -> None:
    global _business_adapter
    _business_adapter = adapter


def get_business_adapter() -> BusinessAdapter | None:
    return _business_adapter
