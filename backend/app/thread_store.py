from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


@dataclass
class ThreadState:
    messages: list[BaseMessage] = field(default_factory=list)


class InMemoryThreadStore:
    def __init__(self) -> None:
        self._threads: dict[str, ThreadState] = {}
        self._lock = Lock()

    def _ensure_thread_unlocked(self, thread_id: str) -> ThreadState:
        if thread_id not in self._threads:
            raise KeyError(thread_id)
        return self._threads[thread_id]

    def create_thread(self) -> str:
        thread_id = str(uuid4())
        with self._lock:
            self._threads[thread_id] = ThreadState()
        return thread_id

    def get_or_create_thread(self, thread_id: str) -> ThreadState:
        with self._lock:
            if thread_id not in self._threads:
                self._threads[thread_id] = ThreadState()
            return self._threads[thread_id]

    def ensure_thread(self, thread_id: str) -> ThreadState:
        with self._lock:
            return self._ensure_thread_unlocked(thread_id)

    def append_human(self, thread_id: str, content: str) -> HumanMessage:
        message = HumanMessage(content=content)
        with self._lock:
            thread = self._ensure_thread_unlocked(thread_id)
            thread.messages.append(message)
        return message

    def append_ai(self, thread_id: str, content: str) -> AIMessage:
        message = AIMessage(content=content)
        with self._lock:
            thread = self._ensure_thread_unlocked(thread_id)
            thread.messages.append(message)
        return message

    def history(self, thread_id: str) -> list[BaseMessage]:
        with self._lock:
            thread = self._ensure_thread_unlocked(thread_id)
            return list(thread.messages)
