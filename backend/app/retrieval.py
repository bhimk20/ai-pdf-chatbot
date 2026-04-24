from __future__ import annotations

from collections.abc import Callable

import langchain_google_genai.chat_models as google_chat_models
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel
from supabase import Client, create_client

from app.config import Settings


ROUTER_PROMPT = """You are a routing assistant.
Decide whether the user's message requires consulting the indexed PDF knowledge base.

Return:
- retrieve: if the answer depends on uploaded PDF content
- direct: if the answer can be answered without retrieval
"""

ANSWER_PROMPT = """You are an assistant for question-answering tasks.
Use the retrieved context to answer the question.
If the answer is not in the context, say you do not know.
Use at most three concise sentences.

Question:
{question}

Context:
{context}
"""


class RouteDecision(BaseModel):
    route: str


def _extract_text_content(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "thinking":
                    continue
                text_value = item.get("text") or item.get("content")
                if isinstance(text_value, str):
                    text_parts.append(text_value)
        return "\n".join(part for part in text_parts if part).strip()

    return str(content)


def _normalize_route(text: str) -> str:
    lowered = text.strip().lower()
    if "retrieve" in lowered:
        return "retrieve"
    return "direct"


def _patch_google_genai_retry_compat() -> None:
    if getattr(google_chat_models, "_codex_retry_patch_applied", False):
        return

    control_kwargs = {
        "max_retries",
        "wait_exponential_multiplier",
        "wait_exponential_min",
        "wait_exponential_max",
    }

    async def _achat_with_retry_compat(generation_method: Callable, **kwargs):
        sanitized = {k: v for k, v in kwargs.items() if k not in control_kwargs}
        return await generation_method(**sanitized)

    def _chat_with_retry_compat(generation_method: Callable, **kwargs):
        sanitized = {k: v for k, v in kwargs.items() if k not in control_kwargs}
        return generation_method(**sanitized)

    google_chat_models._achat_with_retry = _achat_with_retry_compat
    google_chat_models._chat_with_retry = _chat_with_retry_compat
    google_chat_models._codex_retry_patch_applied = True


def format_docs(docs: list[Document]) -> str:
    if not docs:
        return "<documents></documents>"

    formatted_docs = []
    for doc in docs:
        metadata = " ".join(f'{key}="{value}"' for key, value in doc.metadata.items())
        formatted_docs.append(f"<document {metadata}>\n{doc.page_content}\n</document>")
    return "<documents>\n" + "\n".join(formatted_docs) + "\n</documents>"


class RetrievalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        _patch_google_genai_retry_compat()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            output_dimensionality=settings.gemini_embedding_dimensions,
            google_api_key=settings.google_api_key,
        )
        self.chat_model = ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            temperature=0.2,
            google_api_key=settings.google_api_key,
        )
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self.vector_store = SupabaseVectorStore(
            client=self.supabase,
            embedding=self.embeddings,
            table_name="documents",
            query_name="match_documents",
        )

    async def add_documents(self, docs: list[Document]) -> None:
        if docs:
            await self.vector_store.aadd_documents(docs)

    async def route_query(self, query: str) -> str:
        messages = [
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=query),
        ]

        try:
            structured_model = self.chat_model.with_structured_output(RouteDecision)
            response = await structured_model.ainvoke(messages)
            if response is not None and getattr(response, "route", None):
                return _normalize_route(response.route)
        except Exception:
            pass

        fallback_response = await self.chat_model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You are a routing assistant. "
                        "Reply with exactly one word: retrieve or direct."
                    )
                ),
                HumanMessage(content=query),
            ]
        )
        fallback_text = (
            _extract_text_content(fallback_response.content)
        )
        return _normalize_route(fallback_text)

    async def retrieve_documents(self, query: str) -> list[Document]:
        query_embedding = await self.embeddings.aembed_query(query)
        response = (
            self.supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_count": self.settings.retrieval_k,
                    "filter": {},
                },
            ).execute()
        )

        rows = response.data or []
        documents: list[Document] = []
        for row in rows:
            documents.append(
                Document(
                    page_content=row.get("content", ""),
                    metadata=row.get("metadata") or {},
                )
            )
        return documents

    async def answer_direct(self, history: list, query: str) -> str:
        response = await self.chat_model.ainvoke([*history, HumanMessage(content=query)])
        return _extract_text_content(response.content)

    async def stream_answer_with_context(self, history: list, query: str, docs: list[Document]):
        prompt = ANSWER_PROMPT.format(question=query, context=format_docs(docs))
        accumulated = ""
        async for chunk in self.chat_model.astream(
            [*history, HumanMessage(content=prompt)]
        ):
            text = _extract_text_content(chunk.content)
            if not text:
                continue
            accumulated += text
            yield accumulated

    @staticmethod
    def serialize_documents(docs: list[Document]) -> list[dict]:
        serialized = []
        for doc in docs:
            serialized.append(
                {
                    "pageContent": doc.page_content,
                    "metadata": doc.metadata,
                }
            )
        return serialized
