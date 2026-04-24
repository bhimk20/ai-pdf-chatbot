from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


class SQLiteThreadStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists threads (
                  id text primary key,
                  created_at text default current_timestamp
                )
                """
            )
            connection.execute(
                """
                create table if not exists messages (
                  id integer primary key autoincrement,
                  thread_id text not null,
                  role text not null check (role in ('user', 'assistant')),
                  content text not null,
                  created_at text default current_timestamp,
                  foreign key (thread_id) references threads(id) on delete cascade
                )
                """
            )
            connection.commit()

    def _ensure_thread_unlocked(self, connection: sqlite3.Connection, thread_id: str) -> None:
        row = connection.execute(
            "select id from threads where id = ?",
            (thread_id,),
        ).fetchone()
        if row is None:
            raise KeyError(thread_id)

    def create_thread(self) -> str:
        thread_id = str(uuid4())
        with self._lock, self._connect() as connection:
            connection.execute("insert into threads (id) values (?)", (thread_id,))
            connection.commit()
        return thread_id

    def get_or_create_thread(self, thread_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("insert or ignore into threads (id) values (?)", (thread_id,))
            connection.commit()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock, self._connect() as connection:
            self._ensure_thread_unlocked(connection, thread_id)
            connection.execute("delete from threads where id = ?", (thread_id,))
            connection.commit()

    def append_human(self, thread_id: str, content: str) -> HumanMessage:
        message = HumanMessage(content=content)
        self._append_message(thread_id, "user", content)
        return message

    def append_ai(self, thread_id: str, content: str) -> AIMessage:
        message = AIMessage(content=content)
        self._append_message(thread_id, "assistant", content)
        return message

    def _append_message(self, thread_id: str, role: str, content: str) -> None:
        with self._lock, self._connect() as connection:
            self._ensure_thread_unlocked(connection, thread_id)
            connection.execute(
                "insert into messages (thread_id, role, content) values (?, ?, ?)",
                (thread_id, role, content),
            )
            connection.commit()

    def history(self, thread_id: str) -> list[BaseMessage]:
        with self._lock, self._connect() as connection:
            self._ensure_thread_unlocked(connection, thread_id)
            rows = connection.execute(
                """
                select role, content
                from messages
                where thread_id = ?
                order by id asc
                """,
                (thread_id,),
            ).fetchall()

        messages: list[BaseMessage] = []
        for row in rows:
            if row["role"] == "user":
                messages.append(HumanMessage(content=row["content"]))
            else:
                messages.append(AIMessage(content=row["content"]))
        return messages

    def serialized_history(self, thread_id: str) -> list[dict[str, str]]:
        with self._lock, self._connect() as connection:
            self._ensure_thread_unlocked(connection, thread_id)
            rows = connection.execute(
                """
                select role, content
                from messages
                where thread_id = ?
                order by id asc
                """,
                (thread_id,),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def list_threads(self) -> list[dict[str, str | int]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                select
                  t.id as thread_id,
                  coalesce(
                    (
                      select substr(trim(m.content), 1, 80)
                      from messages m
                      where m.thread_id = t.id and m.role = 'user'
                      order by m.id asc
                      limit 1
                    ),
                    (
                      select substr(trim(m.content), 1, 80)
                      from messages m
                      where m.thread_id = t.id
                      order by m.id asc
                      limit 1
                    ),
                    'New chat'
                  ) as title,
                  coalesce(
                    (
                      select substr(trim(m.content), 1, 120)
                      from messages m
                      where m.thread_id = t.id
                      order by m.id desc
                      limit 1
                    ),
                    'No messages yet'
                  ) as preview,
                  coalesce(
                    (
                      select m.created_at
                      from messages m
                      where m.thread_id = t.id
                      order by m.id desc
                      limit 1
                    ),
                    t.created_at
                  ) as updated_at,
                  (
                    select count(*)
                    from messages m
                    where m.thread_id = t.id
                  ) as message_count
                from threads t
                order by updated_at desc, t.created_at desc
                """
            ).fetchall()

        return [
            {
                "thread_id": row["thread_id"],
                "title": row["title"],
                "preview": row["preview"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
            }
            for row in rows
        ]
