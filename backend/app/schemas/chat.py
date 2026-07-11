from pydantic import BaseModel, Field

from app.schemas.rag import RagSource


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)
    conversation_id: str | None = None
    knowledge_base_id: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=80)


class ChatResponse(BaseModel):
    answer: str
    sources: list[RagSource] = Field(default_factory=list)
    conversation_id: str
    assistant_message_id: str
    tool_name: str | None = None
