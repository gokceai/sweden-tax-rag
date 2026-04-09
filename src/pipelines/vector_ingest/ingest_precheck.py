"""Dry-run precheck for pre-chunked ingest.

Reports collision status between dataset chunk IDs and current
Chroma/Dynamo contents without writing any data.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from src.core.dependencies import get_document_repository, get_vector_db_manager


def load_chunk_ids(path: Path) -> list[str]:
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        ids.append(row["chunk_id"])
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run precheck for chunk ingest.")
    parser.add_argument("--input", required=True, help="Path to chunks JSONL file")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return 1

    chunk_ids = load_chunk_ids(input_path)
    total_input = len(chunk_ids)
    duplicate_ids = [cid for cid, count in Counter(chunk_ids).items() if count > 1]
    unique_ids = set(chunk_ids)

    vector_db = get_vector_db_manager()
    repo = get_document_repository()
    chroma_ids = vector_db.list_ids()
    dynamo_ids = repo.list_chunk_ids()

    in_chroma = unique_ids & chroma_ids
    in_dynamo = unique_ids & dynamo_ids
    in_both = in_chroma & in_dynamo
    only_chroma = in_chroma - in_dynamo
    only_dynamo = in_dynamo - in_chroma
    in_neither = unique_ids - (in_chroma | in_dynamo)

    print("INGEST PRECHECK REPORT (DRY RUN)")
    print(f"input_file: {input_path}")
    print(f"total_rows: {total_input}")
    print(f"unique_chunk_ids: {len(unique_ids)}")
    print(f"duplicate_chunk_ids_in_input: {len(duplicate_ids)}")
    if duplicate_ids:
        print(f"duplicate_samples: {sorted(duplicate_ids)[:10]}")
    print(f"existing_in_chroma: {len(in_chroma)}")
    print(f"existing_in_dynamo: {len(in_dynamo)}")
    print(f"already_consistent_in_both: {len(in_both)}")
    print(f"drift_only_in_chroma: {len(only_chroma)}")
    print(f"drift_only_in_dynamo: {len(only_dynamo)}")
    print(f"new_ids_in_neither: {len(in_neither)}")
    print("planned_actions:")
    print(f"  upsert_chroma: {len(in_neither) + len(in_dynamo) + len(in_both)}")
    print(f"  write_dynamo: {len(in_neither) + len(in_chroma) + len(in_both)}")
    print("note: this script performs no writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

