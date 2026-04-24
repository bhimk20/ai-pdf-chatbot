from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings, get_settings
from app.documents import load_pdf_documents
from app.models import ChatRequest, IngestResponse, SSEEnvelope, ThreadCreateResponse
from app.retrieval import RetrievalService
from app.thread_store import InMemoryThreadStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.threads = InMemoryThreadStore()
    app.state.retrieval = RetrievalService(settings)
    yield


app = FastAPI(title="AI PDF Chatbot Backend", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/threads", response_model=ThreadCreateResponse)
async def create_thread() -> ThreadCreateResponse:
    thread_id = app.state.threads.create_thread()
    return ThreadCreateResponse(thread_id=thread_id)


@app.post("/ingest", response_model=IngestResponse)
async def ingest_files(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > settings.max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {settings.max_files} files allowed.",
        )

    all_docs = []
    for file in files:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        raw = await file.read()
        if len(raw) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File size must be less than {settings.max_file_size_mb}MB "
                    f"for {file.filename}"
                ),
            )
        await file.seek(0)
        docs = await load_pdf_documents(file, settings)
        all_docs.extend(docs)

    if not all_docs:
        raise HTTPException(status_code=400, detail="No valid text extracted from uploaded PDFs")

    await app.state.retrieval.add_documents(all_docs)
    thread_id = app.state.threads.create_thread()
    return IngestResponse(message="Documents ingested successfully", threadId=thread_id)


@app.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    app.state.threads.get_or_create_thread(payload.threadId)
    history = app.state.threads.history(payload.threadId)

    async def event_stream():
        route = await app.state.retrieval.route_query(payload.message)
        if route == "retrieve":
            docs = await app.state.retrieval.retrieve_documents(payload.message)
            updates = SSEEnvelope(
                event="updates",
                data={"retrieveDocuments": {"documents": app.state.retrieval.serialize_documents(docs)}},
            )
            yield f"data: {updates.model_dump_json()}\n\n"

            final_text = ""
            async for partial in app.state.retrieval.stream_answer_with_context(
                history,
                payload.message,
                docs,
            ):
                final_text = partial
                event = SSEEnvelope(
                    event="messages/partial",
                    data=[{"type": "ai", "content": partial}],
                )
                yield f"data: {event.model_dump_json()}\n\n"
        else:
            final_text = await app.state.retrieval.answer_direct(history, payload.message)
            event = SSEEnvelope(
                event="messages/partial",
                data=[{"type": "ai", "content": final_text}],
            )
            yield f"data: {event.model_dump_json()}\n\n"

        app.state.threads.append_human(payload.threadId, payload.message)
        app.state.threads.append_ai(payload.threadId, final_text)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})


settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
