#!/usr/bin/env python3
"""Ingest raw JSONL documents into the RAG stores.

Expected input format (one JSON object per line):
- Required: text
- Optional: doc_id, title

This script is intentionally separate from the pre-chunked pipeline:
- pipeline_cli.py expects already chunked rows with chunk_id/chunk_index metadata
- this script accepts raw documents, chunks them locally, and ingests each chunk
  using the shared ChunkIngestService write contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

# Allow running from project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import settings
from src.core.dependencies import get_document_repository, get_vector_db_manager
from src.services.chunk_ingest_service import ChunkIngestService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest raw JSONL documents using ChunkIngestService.")
    parser.add_argument("--input", required=True, help="Path to raw documents JSONL")
    parser.add_argument("--limit", type=int, default=0, help="Optional max document count (0=all)")
    parser.add_argument(
        "--reset-chroma-collection",
        action="store_true",
        help="Delete and recreate target Chroma collection before ingest.",
    )
    parser.add_argument(
        "--reset-document-store",
        action="store_true",
        help="Delete all rows from SQLite document store before ingest.",
    )
    parser.add_argument(
        "--reset-all",
        action="store_true",
        help="Reset both Chroma and SQLite stores before ingest.",
    )
    parser.add_argument(
        "--fail-on-skip",
        action="store_true",
        help="Return non-zero when any row is skipped (invalid JSON, bad type, empty text).",
    )
    return parser.parse_args()


def build_chunk_id(source_name: str, chunk_index: int, chunk_text: str) -> str:
    digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
    return f"{source_name}_chunk_{chunk_index}_{digest}"


def build_chunk_metadata(row: dict[str, Any], chunk_index: int, chunk_text: str) -> dict:
    return {
        "doc_id": row.get("doc_id", row.get("source_name", "unknown")),
        "chunk_index": chunk_index,
        "title": row.get("title"),
        "url": row.get("url"),
        "source": row.get("source"),
        "authority": row.get("authority"),
        "jurisdiction": row.get("jurisdiction"),
        "language": row.get("language"),
        "topic": row.get("topic"),
        "source_family": row.get("source_family"),
        "source_type": row.get("source_type"),
        "legal_weight": row.get("legal_weight"),
        "chunk_word_count": len(chunk_text.split()),
        "chunk_char_count": len(chunk_text),
        "content_hash": row.get("content_hash"),
    }


def _iter_rows(path: Path) -> Iterator[tuple[int, dict[str, Any] | None, str | None]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                yield lineno, None, f"invalid JSON ({exc})"
                continue
            if not isinstance(row, dict):
                yield lineno, None, f"JSON root must be object/dict, got {type(row).__name__}"
                continue
            yield lineno, row, None


def _source_name_for_row(row: dict[str, Any], lineno: int) -> str:
    source_name = (
        str(row.get("doc_id") or "").strip()
        or str(row.get("title") or "").strip()
        or f"line_{lineno}"
    )
    return " ".join(source_name.split())[:200] or f"line_{lineno}"


def _reset_chroma(vector_db) -> None:
    collection_name = vector_db.collection_name
    print(f"resetting_chroma_collection: {collection_name}")
    try:
        vector_db.client.delete_collection(name=collection_name)
    except Exception:
        pass
    vector_db.collection = vector_db._init_collection()


def _reset_document_store(document_repo) -> None:
    document_repo.delete_all_chunks()
    print("reset_document_store_deleted_rows: all")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return 1
    if not input_path.is_file():
        print(f"ERROR: input path is not a file: {input_path}")
        return 1

    try:
        vector_db = get_vector_db_manager()
        document_repo = get_document_repository()
        ingest_service = ChunkIngestService(
            document_repo=document_repo,
            vector_db=vector_db,
        )
    except Exception as exc:
        print(f"ERROR: dependency initialization failed: {exc}")
        return 1

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,
    )

    if args.reset_all or args.reset_chroma_collection:
        _reset_chroma(vector_db)
    if args.reset_all or args.reset_document_store:
        _reset_document_store(document_repo)

    processed_docs = 0
    skipped_docs = 0
    failed_docs = 0
    total_chunks = 0
    seen_docs = 0

    try:
        for lineno, row, parse_error in _iter_rows(input_path):
            if parse_error:
                skipped_docs += 1
                print(f"SKIP line={lineno}: {parse_error}")
                continue
            assert row is not None

            text = (row.get("text") or "").strip()
            if not text:
                skipped_docs += 1
                print(f"SKIP line={lineno}: missing/empty 'text'")
                continue

            seen_docs += 1
            if args.limit and seen_docs > args.limit:
                break

            source_name = _source_name_for_row(row, lineno)

            try:
                chunks = splitter.split_text(text)
                chunk_count = 0

                for chunk_index, chunk_text in enumerate(chunks):
                    chunk_id = build_chunk_id(source_name, chunk_index, chunk_text)
                    metadata = build_chunk_metadata(row, chunk_index, chunk_text)

                    result = ingest_service.ingest_chunk(
                        chunk_id=chunk_id,
                        text=chunk_text,
                        metadata=metadata,
                    )
                    if not (result.document_store_written and result.chroma_written):
                        raise RuntimeError(f"Ingest failed for chunk_id={chunk_id}")

                    chunk_count += 1

                processed_docs += 1
                total_chunks += chunk_count
                print(f"OK line={lineno} source='{source_name}' chunks={chunk_count}")
            except Exception as exc:
                failed_docs += 1
                print(f"FAIL line={lineno} source='{source_name}': {exc}")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130

    print("\nINGEST SUMMARY")
    print(f"processed_docs: {processed_docs}")
    print(f"failed_docs: {failed_docs}")
    print(f"skipped_docs: {skipped_docs}")
    print(f"total_chunks: {total_chunks}")
    print(f"chroma_ids: {len(vector_db.list_ids())}")
    print(f"doc_ids: {len(document_repo.list_chunk_ids())}")

    if failed_docs > 0:
        return 2
    if args.fail_on_skip and skipped_docs > 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
