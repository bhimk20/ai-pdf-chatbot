from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.config import Settings


def _safe_pdf_metadata(reader: PdfReader) -> dict:
    metadata = {}
    raw_metadata = reader.metadata or {}
    for key, value in raw_metadata.items():
        metadata[str(key)] = str(value)
    return metadata


async def load_pdf_documents(file: UploadFile, settings: Settings) -> list[Document]:
    raw_bytes = await file.read()
    reader = PdfReader(BytesIO(raw_bytes))
    pdf_metadata = _safe_pdf_metadata(reader)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    docs: list[Document] = []
    for page_index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue

        base_metadata = {
            "filename": file.filename,
            "source": file.filename,
            "pdf": {
                "info": pdf_metadata,
                "totalPages": len(reader.pages),
            },
            "loc": {"pageNumber": page_index},
        }
        split_docs = splitter.create_documents([page_text], metadatas=[base_metadata])
        for chunk_index, doc in enumerate(split_docs, start=1):
            doc.metadata["uuid"] = str(uuid4())
            doc.metadata["chunk"] = chunk_index
            docs.append(doc)

    return docs
