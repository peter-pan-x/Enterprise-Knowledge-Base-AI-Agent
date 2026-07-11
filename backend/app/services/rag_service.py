import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.schemas.document import DocumentRecord
from app.schemas.rag import RagLogEntry, RagSource
from app.services.document_service import TEXT_DIR, list_documents, list_knowledge_bases, update_document_index_status
from app.services.embedding_service import embed_text

CHROMA_DIR = Path(__file__).resolve().parents[2] / "data" / "chroma"
RAG_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "rag_logs.json"
COLLECTION_NAME = "enterprise_knowledge_chunks"
_RAG_LOG_LOCK = threading.RLock()


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
        if record.status != "processed":
            continue
        try:
            chunk_count = index_document(record)
            if not chunk_count:
                raise ValueError("文档未生成可索引片段")
        except Exception as exc:
            update_document_index_status(
                record.id,
                index_status="failed",
                indexed_chunks=0,
                index_error_message=f"重建索引失败：{exc}",
            )
            continue

        update_document_index_status(
            record.id,
            index_status="indexed",
            indexed_chunks=chunk_count,
            index_error_message=None,
        )
        indexed_documents += 1
        indexed_chunks += chunk_count
    return indexed_documents, indexed_chunks


def search_knowledge_base(query: str, top_k: int | None = None, knowledge_base_id: str | None = None, category: str | None = None) -> list[RagSource]:
    started_at = time.perf_counter()
    collection = get_collection()
    count = collection.count()
    effective_top_k = max(1, min(top_k if top_k is not None else settings.rag_top_k, 20))
    if count == 0:
        _try_append_rag_log(query, effective_top_k, [], started_at, knowledge_base_id, category)
        return []

    candidate_count = min(max(effective_top_k * 10, 50), count)
    result = collection.query(
        query_embeddings=[embed_text(query)],
        n_results=candidate_count,
        include=["documents", "metadatas", "distances"],
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]

    sources_by_id: dict[str, RagSource] = {}
    # The configured threshold is authoritative; a hard-coded floor made tuning ineffective.
    vector_floor = settings.rag_min_score
    enabled_knowledge_base_ids = {item.id for item in list_knowledge_bases() if item.is_enabled}
    enabled_document_ids = {
        record.id for record in list_documents()
        if record.is_enabled and record.status == "processed" and record.knowledge_base_id in enabled_knowledge_base_ids
        and (knowledge_base_id is None or record.knowledge_base_id == knowledge_base_id)
        and (category is None or record.category == category)
    }
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        if str(metadata.get("document_id", "")) not in enabled_document_ids:
            continue
        vector_score = max(0.0, 1.0 - float(distance))
        lexical_score = _lexical_score(query, document)
        score = max(vector_score, lexical_score * 0.9 if lexical_score >= 0.5 else 0.0)
        if lexical_score < 0.5 and vector_score < vector_floor:
            continue
        if score < settings.rag_min_score:
            continue
        source = _build_source(chunk_id, document, metadata, score)
        sources_by_id[source.chunk_id] = source

    for term in _lexical_query_terms(query):
        lexical_matches = collection.get(
            where_document={"$contains": term},
            include=["documents", "metadatas"],
            limit=200,
        )
        for chunk_id, document, metadata in zip(
            lexical_matches.get("ids", []),
            lexical_matches.get("documents", []),
            lexical_matches.get("metadatas", []),
        ):
            if str(metadata.get("document_id", "")) not in enabled_document_ids:
                continue
            if str(chunk_id) in sources_by_id:
                continue
            lexical_score = _lexical_score(query, document)
            score = lexical_score * 0.9
            if lexical_score < 0.5 or score < settings.rag_min_score:
                continue
            source = _build_source(chunk_id, document, metadata, score)
            sources_by_id[source.chunk_id] = source

    sources = list(sources_by_id.values())
    sources.sort(key=lambda source: source.score, reverse=True)
    sources = sources[:effective_top_k]
    _try_append_rag_log(query, effective_top_k, sources, started_at, knowledge_base_id, category)
    return sources


def _build_source(chunk_id: object, document: str, metadata: dict, score: float) -> RagSource:
    return RagSource(
        document_id=str(metadata.get("document_id", "")),
        filename=str(metadata.get("filename", "")),
        chunk_id=str(chunk_id),
        chunk_index=int(metadata.get("chunk_index", 0)),
        page_number=_optional_int(metadata.get("page_number")),
        score=round(score, 4),
        preview=_preview(document),
        content=document,
    )


def list_rag_logs(limit: int = 50) -> list[RagLogEntry]:
    with _RAG_LOG_LOCK:
        if not RAG_LOG_PATH.exists():
            return []
        try:
            raw = json.loads(RAG_LOG_PATH.read_text(encoding="utf-8"))
            return [RagLogEntry.model_validate(item) for item in raw[:limit]]
        except (OSError, json.JSONDecodeError, ValueError):
            return []


def append_rag_log(query: str, top_k: int, sources: list[RagSource], retrieval_latency_ms: int = 0, knowledge_base_id: str | None = None, category: str | None = None) -> None:
    with _RAG_LOG_LOCK:
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
            retrieval_latency_ms=retrieval_latency_ms,
            knowledge_base_id=knowledge_base_id,
            category=category,
        )
        logs.insert(0, entry.model_dump(mode="json"))
        _atomic_write_rag_logs(logs[:200])


def _try_append_rag_log(query: str, top_k: int, sources: list[RagSource], started_at: float, knowledge_base_id: str | None, category: str | None) -> None:
    try:
        append_rag_log(query, top_k, sources, int((time.perf_counter() - started_at) * 1000), knowledge_base_id, category)
    except (OSError, json.JSONDecodeError, ValueError):
        # Retrieval and chat must remain available if optional logging fails.
        return


def _atomic_write_rag_logs(logs: list[dict]) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=RAG_LOG_PATH.parent,
            prefix=f".{RAG_LOG_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            json.dump(logs, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, RAG_LOG_PATH)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
                        "knowledge_base_id": record.knowledge_base_id,
                        "category": record.category,
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


def _lexical_score(query: str, document: str) -> float:
    query_tokens = _meaningful_tokens(query)
    if not query_tokens:
        return 0.0
    document_tokens = _meaningful_tokens(document)
    return len(query_tokens & document_tokens) / len(query_tokens)


def _meaningful_tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z0-9_]{2,}", lowered))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", lowered):
        tokens.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens


def _lexical_query_terms(query: str) -> list[str]:
    return sorted(_meaningful_tokens(query), key=lambda token: (-len(token), token))[:3]
