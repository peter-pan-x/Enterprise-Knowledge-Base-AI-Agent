import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from pypdf import PdfReader

from app.schemas.document import DocumentRecord

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TEXT_DIR = DATA_DIR / "texts"
METADATA_PATH = DATA_DIR / "documents.json"

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024


class DocumentServiceError(Exception):
    pass


def _ensure_storage() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    if not METADATA_PATH.exists():
        METADATA_PATH.write_text("[]", encoding="utf-8")


def _load_records() -> list[DocumentRecord]:
    _ensure_storage()
    raw = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    return [DocumentRecord.model_validate(item) for item in raw]


def _save_records(records: list[DocumentRecord]) -> None:
    _ensure_storage()
    payload = [record.model_dump(mode="json") for record in records]
    METADATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(f"[page {index}]\n{page_text}")
    return "\n\n".join(pages)


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _clean_text(_extract_pdf_text(path))
    if suffix in {".txt", ".md", ".markdown"}:
        return _clean_text(path.read_text(encoding="utf-8", errors="ignore"))
    raise DocumentServiceError("仅支持 PDF、TXT、Markdown 文档")


async def save_uploaded_document(file: UploadFile) -> DocumentRecord:
    _ensure_storage()
    original_name = Path(file.filename or "").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise DocumentServiceError("仅支持 PDF、TXT、Markdown 文档")

    document_id = uuid4().hex
    stored_name = f"{document_id}{suffix}"
    upload_path = UPLOAD_DIR / stored_name
    text_path = TEXT_DIR / f"{document_id}.txt"

    size_bytes = 0
    with upload_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size_bytes += len(chunk)
            if size_bytes > MAX_UPLOAD_SIZE_BYTES:
                upload_path.unlink(missing_ok=True)
                raise DocumentServiceError("单个文档不能超过 15MB")
            output.write(chunk)

    status = "processed"
    error_message = None
    text_length = 0

    try:
        parsed_text = _extract_text(upload_path)
        text_length = len(parsed_text)
        text_path.write_text(parsed_text, encoding="utf-8")
        if not parsed_text:
            status = "failed"
            error_message = "文档未解析出有效文本"
    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        text_path.write_text("", encoding="utf-8")

    record = DocumentRecord(
        id=document_id,
        filename=original_name,
        content_type=file.content_type or "application/octet-stream",
        status=status,
        size_bytes=size_bytes,
        text_length=text_length,
        created_at=datetime.now(UTC),
        error_message=error_message,
    )

    records = _load_records()
    records.insert(0, record)
    _save_records(records)
    return record


def list_documents() -> list[DocumentRecord]:
    return _load_records()


def get_document(document_id: str) -> DocumentRecord:
    for record in _load_records():
        if record.id == document_id:
            return record
    raise DocumentServiceError("文档不存在")


def get_document_preview(document_id: str, limit: int = 1200) -> tuple[DocumentRecord, str]:
    record = get_document(document_id)
    text_path = TEXT_DIR / f"{document_id}.txt"
    preview = text_path.read_text(encoding="utf-8", errors="ignore")[:limit] if text_path.exists() else ""
    return record, preview


def delete_document(document_id: str) -> None:
    records = _load_records()
    next_records = [record for record in records if record.id != document_id]
    if len(next_records) == len(records):
        raise DocumentServiceError("文档不存在")

    for path in UPLOAD_DIR.glob(f"{document_id}.*"):
        if path.is_file():
            path.unlink(missing_ok=True)
    text_path = TEXT_DIR / f"{document_id}.txt"
    text_path.unlink(missing_ok=True)
    _save_records(next_records)


def reset_documents_for_tests() -> None:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
