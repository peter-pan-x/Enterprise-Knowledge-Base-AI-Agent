from pydantic import BaseModel, Field


class ServicePolicy(BaseModel):
    welcome_message: str = Field(default="你好，我是企业知识库 AI 客服，请问有什么可以帮您？", max_length=1000)
    no_answer_message: str = Field(default="抱歉，我暂时没有找到可靠答案，已为您转交人工客服继续处理。", max_length=1000)
    handoff_message: str = Field(default="已收到您的人工服务请求，客服会尽快跟进。", max_length=1000)
    handoff_keywords: str = Field(default="人工客服,转人工,投诉,退款纠纷", max_length=1000)
    sensitive_keywords: str = Field(default="", max_length=1000)
    auto_handoff_on_no_answer: bool = True
    assistant_instructions: str = Field(default="回答必须基于提供的知识库内容；信息不足时明确说明，不要编造。", max_length=4000)


class PublicServicePolicy(BaseModel):
    """The only service-policy value that a normal chat user may read."""

    welcome_message: str
