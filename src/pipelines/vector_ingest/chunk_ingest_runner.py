"""Idempotent pre-chunked ingest runner for SQLite + ChromaDB.

Write contract:
1. SQLite document store is written first (encrypted text as source of truth).
2. ChromaDB vector index is written second.
3. If Chroma write fails after SQLite write, SQLite row is rolled back.

This runner assumes the dataset is already chunked and provides a canonical
`chunk_id` for each row. Runtime code must not regenerate chunk IDs.
"""

import argparse
import json
from pathlib import Path

from src.core.dependencies import get_document_repository, get_vector_db_manager
from src.services.chunk_ingest_service import ChunkIngestService


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def build_metadata(row: dict) -> dict:
    fields = [
        "doc_id",
        "chunk_index",
        "title",
        "url",
        "source",
        "authority",
        "jurisdiction",
        "language",
        "topic",
        "source_family",
        "source_type",
        "legal_weight",
        "chunk_word_count",
        "chunk_char_count",
        "content_char_count",
        "content_hash",
        "section_heading",
        "box_range",
    ]
    return {field: row.get(field) for field in fields}


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest pre-chunked JSONL into SQLite and ChromaDB.")
    parser.add_argument("--input", required=True, help="Path to chunks JSONL")
    parser.add_argument("--limit", type=int, default=0, help="Optional max row count (0 means all)")
    parser.add_argument("--apply", action="store_true", help="Execute writes. Without this flag, dry-run only.")
    parser.add_argument(
        "--reset-chroma-collection",
        action="store_true",
        help="Delete and recreate target Chroma collection before ingest.",
    )
    parser.add_argument(
        "--reconcile-missing",
        action="store_true",
        help="After a successful ingest, delete chunk IDs that exist in stores but are not present in the input dataset.",
    )
    parser.add_argument(
        "--reset-document-store",
        action="store_true",
        help="Delete all SQLite chunk rows before ingest.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return 1

    rows = load_rows(input_path)
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]

    input_chunk_ids = {row["chunk_id"] for row in rows}

    vector_db = get_vector_db_manager()
    document_repo = get_document_repository()
    ingest_service = ChunkIngestService(
        document_repo=document_repo,
        vector_db=vector_db,
    )

    if args.reset_chroma_collection:
        collection_name = vector_db.collection_name
        print(f"resetting_chroma_collection: {collection_name}")
        try:
            vector_db.client.delete_collection(name=collection_name)
        except Exception:
            pass
        vector_db.collection = vector_db._init_collection()

    if args.reset_document_store:
        print(f"resetting_document_store: {document_repo.db_path}")
        document_repo.delete_all_chunks()

    chroma_existing = vector_db.list_ids()
    document_store_existing = document_repo.list_chunk_ids()

    stale_in_chroma = chroma_existing - input_chunk_ids
    stale_in_document_store = document_store_existing - input_chunk_ids

    report = {
        "mode": "apply" if args.apply else "dry-run",
        "input_file": str(input_path),
        "input_rows": len(rows),
        "processed": 0,
        "would_create": 0,
        "would_update": 0,
        "written_document_store": 0,
        "written_chroma": 0,
        "failed": 0,
        "failed_chunk_ids": [],
        "stale_in_chroma": len(stale_in_chroma),
        "stale_in_document_store": len(stale_in_document_store),
        "deleted_from_chroma": 0,
        "deleted_from_document_store": 0,
    }

    for row in rows:
        chunk_id = row["chunk_id"]
        text = row.get("text", "")
        metadata = build_metadata(row)

        exists_chroma = chunk_id in chroma_existing
        exists_in_document_store = chunk_id in document_store_existing
        if exists_chroma or exists_in_document_store:
            report["would_update"] += 1
        else:
            report["would_create"] += 1

        if not args.apply:
            report["processed"] += 1
            continue

        result = ingest_service.ingest_chunk(
            chunk_id=chunk_id,
            text=text,
            metadata=metadata,
        )

        if not result.document_store_written:
            report["failed"] += 1
            report["failed_chunk_ids"].append(chunk_id)
            report["processed"] += 1
            continue

        report["written_document_store"] += 1

        if not result.chroma_written:
            report["failed"] += 1
            report["failed_chunk_ids"].append(chunk_id)
            report["processed"] += 1
            continue

        report["written_chroma"] += 1
        report["processed"] += 1

    if args.apply and args.reconcile_missing and report["failed"] == 0:
        if stale_in_chroma:
            vector_db.delete_vectors(sorted(stale_in_chroma))
            report["deleted_from_chroma"] = len(stale_in_chroma)

        if stale_in_document_store:
            document_repo.delete_chunk_ids(sorted(stale_in_document_store))
            report["deleted_from_document_store"] = len(stale_in_document_store)

    print("INGEST REPORT")
    for key in [
        "mode",
        "input_file",
        "input_rows",
        "processed",
        "would_create",
        "would_update",
        "written_document_store",
        "written_chroma",
        "failed",
        "stale_in_chroma",
        "stale_in_document_store",
        "deleted_from_chroma",
        "deleted_from_document_store",
    ]:
        print(f"{key}: {report[key]}")
    if report["failed_chunk_ids"]:
        print("failed_chunk_ids_sample:", report["failed_chunk_ids"][:20])

    return 0 if report["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
