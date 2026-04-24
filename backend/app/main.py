from __future__ import annotations

from contextlib import asynccontextmanager
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import Settings, get_settings
from app.documents import load_pdf_documents
from app.monitoring import (
    ACTIVE_CHAT_STREAMS,
    CHAT_COUNT,
    INGEST_CHUNKS,
    INGEST_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    configure_logging,
    log_event,
    metrics_response,
)
from app.models import (
    ChatRequest,
    IngestResponse,
    SSEEnvelope,
    ThreadCreateResponse,
    ThreadListResponse,
    ThreadStateResponse,
)
from app.retrieval import RetrievalService
from app.thread_store import SQLiteThreadStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    app.state.settings = settings
    app.state.threads = SQLiteThreadStore(settings.sqlite_db_path)
    app.state.retrieval = RetrievalService(settings)
    log_event("app_started", sqlite_path=str(settings.sqlite_db_path))
    yield
    log_event("app_stopped")


app = FastAPI(title="AI PDF Chatbot Backend", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_metrics_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as exc:
        duration = time.perf_counter() - started_at
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        REQUEST_COUNT.labels(method=request.method, path=path, status="500").inc()
        REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
        log_event(
            "request_failed",
            request_id=request_id,
            method=request.method,
            path=path,
            status=500,
            duration_ms=round(duration * 1000, 2),
            error=str(exc),
        )
        raise

    duration = time.perf_counter() - started_at
    path = request.scope.get("route").path if request.scope.get("route") else request.url.path
    REQUEST_COUNT.labels(method=request.method, path=path, status=str(status_code)).inc()
    REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
    response.headers["X-Request-ID"] = request_id
    log_event(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=path,
        status=status_code,
        duration_ms=round(duration * 1000, 2),
    )
    return response


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return metrics_response()


@app.get("/debug/status")
async def debug_status():
    settings = get_settings()
    checks = app.state.retrieval.debug_checks()
    return {
        "status": "ok" if checks["documents_table_accessible"] and checks["match_documents_rpc_accessible"] else "degraded",
        "env": {
            "google_api_key_present": bool(settings.google_api_key),
            "supabase_url_present": bool(settings.supabase_url),
            "supabase_service_role_key_present": bool(settings.supabase_service_role_key),
        },
        "checks": checks,
    }


@app.post("/threads", response_model=ThreadCreateResponse)
async def create_thread() -> ThreadCreateResponse:
    thread_id = app.state.threads.create_thread()
    return ThreadCreateResponse(thread_id=thread_id)


@app.get("/threads", response_model=ThreadListResponse)
async def list_threads() -> ThreadListResponse:
    return ThreadListResponse(threads=app.state.threads.list_threads())


@app.get("/threads/{thread_id}", response_model=ThreadStateResponse)
async def get_thread(thread_id: str) -> ThreadStateResponse:
    try:
        messages = app.state.threads.serialized_history(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc
    return ThreadStateResponse(thread_id=thread_id, messages=messages)


@app.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: str) -> Response:
    try:
        app.state.threads.delete_thread(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc
    return Response(status_code=204)


@app.post("/ingest", response_model=IngestResponse)
async def ingest_files(
    files: list[UploadFile] = File(...),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    started_at = time.perf_counter()
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

    try:
        await app.state.retrieval.add_documents(all_docs)
    except Exception:
        INGEST_COUNT.labels(status="error").inc()
        log_event(
            "ingest_failed",
            file_count=len(files),
            chunk_count=len(all_docs),
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        raise

    thread_id = app.state.threads.create_thread()
    INGEST_COUNT.labels(status="success").inc()
    INGEST_CHUNKS.inc(len(all_docs))
    log_event(
        "ingest_completed",
        thread_id=thread_id,
        file_count=len(files),
        chunk_count=len(all_docs),
        duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
    )
    return IngestResponse(message="Documents ingested successfully", threadId=thread_id)


@app.post("/chat/stream")
async def chat_stream(payload: ChatRequest):
    app.state.threads.get_or_create_thread(payload.threadId)
    history = app.state.threads.history(payload.threadId)

    async def event_stream():
        ACTIVE_CHAT_STREAMS.inc()
        started_at = time.perf_counter()
        route = "direct"
        try:
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
            CHAT_COUNT.labels(route=route, status="success").inc()
            log_event(
                "chat_completed",
                thread_id=payload.threadId,
                route=route,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
        except Exception as exc:
            CHAT_COUNT.labels(route=route, status="error").inc()
            log_event(
                "chat_failed",
                thread_id=payload.threadId,
                route=route,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                error=str(exc),
            )
            raise
        finally:
            ACTIVE_CHAT_STREAMS.dec()

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
