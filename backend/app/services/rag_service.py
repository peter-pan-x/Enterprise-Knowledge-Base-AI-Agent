import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.schemas.document import DocumentRecord
from app.schemas.rag import RagLogEntry, RagSource
from app.services.document_service import TEXT_DIR, list_documents
from app.services.embedding_service import embed_text

CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "chroma"
RAG_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "rag_logs.json"
COLLECTION_NAME = "enterprise_knowledge_chunks"


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def get_collection():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def index_document(record: DocumentRecord) -> int:
    if record.status != "processed":
        return 0

    text_path = TEXT_DIR / f"{record.id}.txt"
    if not text_path.exists():
        return 0

    text = text_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return 0

    collection = get_collection()
    collection.delete(where={"document_id": record.id})

    chunks = split_document_text(record, text)
    if not chunks:
        return 0

    collection.add(
        ids=[chunk.id for chunk in chunks],
        documents=[chunk.text for chunk in chunks],
        embeddings=[embed_text(chunk.text) for chunk in chunks],
        metadatas=[chunk.metadata for chunk in chunks],
    )
    return len(chunks)


def delete_document_index(document_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"document_id": document_id})


def reindex_all_documents() -> tuple[int, int]:
    indexed_documents = 0
    indexed_chunks = 0
    for record in list_documents():
        chunk_count = index_document(record)
        if chunk_count:
            indexed_documents += 1
            indexed_chunks += chunk_count
    return indexed_documents, indexed_chunks


def search_knowledge_base(query: str, top_k: int | None = None) -> list[RagSource]:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        append_rag_log(query, top_k or settings.rag_top_k, [])
        return []

    result = collection.query(
        query_embeddings=[embed_text(query)],
        n_results=min(top_k or settings.rag_top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]

    sources: list[RagSource] = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        score = max(0.0, 1.0 - float(distance))
        if score < settings.rag_min_score and not _has_keyword_overlap(query, document):
            continue
        sources.append(
            RagSource(
                document_id=str(metadata.get("document_id", "")),
                filename=str(metadata.get("filename", "")),
                chunk_id=str(chunk_id),
                chunk_index=int(metadata.get("chunk_index", 0)),
                page_number=_optional_int(metadata.get("page_number")),
                score=round(score, 4),
                preview=_preview(document),
            )
        )
    append_rag_log(query, top_k or settings.rag_top_k, sources)
    return sources


def list_rag_logs(limit: int = 50) -> list[RagLogEntry]:
    if not RAG_LOG_PATH.exists():
        return []
    raw = json.loads(RAG_LOG_PATH.read_text(encoding="utf-8"))
    return [RagLogEntry.model_validate(item) for item in raw[:limit]]


def append_rag_log(query: str, top_k: int, sources: list[RagSource]) -> None:
    RAG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logs = []
    if RAG_LOG_PATH.exists():
        logs = json.loads(RAG_LOG_PATH.read_text(encoding="utf-8"))
    entry = RagLogEntry(
        id=uuid4().hex,
        query=query,
        top_k=top_k,
        source_count=len(sources),
        sources=sources,
        created_at=datetime.now(UTC).isoformat(),
    )
    logs.insert(0, entry.model_dump(mode="json"))
    RAG_LOG_PATH.write_text(json.dumps(logs[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def split_document_text(record: DocumentRecord, text: str) -> list[Chunk]:
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []

    chunks: list[Chunk] = []
    start = 0
    chunk_index = 0
    chunk_size = settings.rag_chunk_size
    overlap = min(settings.rag_chunk_overlap, max(0, chunk_size - 1))

    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            boundary = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind("。", start, end),
                normalized.rfind(".", start, end),
            )
            if boundary > start + chunk_size * 0.45:
                end = boundary + 1

        chunk_text = normalized[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    id=f"{record.id}:{chunk_index}",
                    text=chunk_text,
                    metadata={
                        "document_id": record.id,
                        "filename": record.filename,
                        "chunk_index": chunk_index,
                        "page_number": _detect_page_number(chunk_text),
                        "created_at": record.created_at.isoformat(),
                    },
                )
            )
            chunk_index += 1

        if end >= len(normalized):
            break
        start = max(0, end - overlap)

    return chunks


def _detect_page_number(text: str) -> int:
    match = re.search(r"\[page\s+(\d+)\]", text, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _optional_int(value: object) -> int | None:
    if value in (None, "", 0):
        return None
    return int(value)


def _preview(text: str, limit: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _has_keyword_overlap(query: str, document: str) -> bool:
    query_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", query.lower()))
    document_tokens = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", document.lower()))
    if not query_tokens or not document_tokens:
        return False
    return len(query_tokens & document_tokens) >= 2
