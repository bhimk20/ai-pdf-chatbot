from typing import Any, Literal

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    filename: str | None = None
    source: str | None = None
    uuid: str | None = None
    chunk: int | None = None
    loc: dict[str, Any] | None = None
    pdf: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class PDFDocument(BaseModel):
    page_content: str = Field(alias="pageContent")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    model_config = {"populate_by_name": True}


class ThreadCreateResponse(BaseModel):
    thread_id: str


class ThreadMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ThreadStateResponse(BaseModel):
    thread_id: str
    messages: list[ThreadMessageResponse]


class IngestResponse(BaseModel):
    message: str
    threadId: str


class ChatRequest(BaseModel):
    message: str
    threadId: str


class MessagePayload(BaseModel):
    type: Literal["human", "ai"]
    content: str


class SSEEnvelope(BaseModel):
    event: str
    data: Any
