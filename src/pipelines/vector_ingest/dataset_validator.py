"""Validate chunked JSONL dataset quality before ingest.

Checks:
- JSON parsing
- required schema fields
- duplicate chunk IDs
- text presence/type
- numeric field types and chunk index validity
- optional consistency for word/char counters
"""

import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = [
    "chunk_id",
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
    "content_hash",
    "text",
]


def validate_chunks(input_path: Path) -> tuple[bool, dict]:
    rows = []
    json_errors = []
    for line_no, line in enumerate(input_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            obj["_line"] = line_no
            rows.append(obj)
        except Exception as exc:
            json_errors.append((line_no, str(exc)))

    missing = []
    empty_text = []
    bad_types = []
    negative_index = []

    for row in rows:
        missing_fields = [f for f in REQUIRED_FIELDS if f not in row]
        if missing_fields:
            missing.append((row.get("_line"), row.get("chunk_id"), missing_fields))

        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            empty_text.append((row.get("_line"), row.get("chunk_id")))

        if not isinstance(row.get("chunk_index"), int):
            bad_types.append((row.get("_line"), row.get("chunk_id"), "chunk_index", type(row.get("chunk_index")).__name__))
        elif row.get("chunk_index") < 0:
            negative_index.append((row.get("_line"), row.get("chunk_id"), row.get("chunk_index")))

        if not isinstance(row.get("chunk_word_count"), int):
            bad_types.append(
                (row.get("_line"), row.get("chunk_id"), "chunk_word_count", type(row.get("chunk_word_count")).__name__)
            )
        if not isinstance(row.get("chunk_char_count"), int):
            bad_types.append(
                (row.get("_line"), row.get("chunk_id"), "chunk_char_count", type(row.get("chunk_char_count")).__name__)
            )
        if not isinstance(row.get("legal_weight"), int):
            bad_types.append((row.get("_line"), row.get("chunk_id"), "legal_weight", type(row.get("legal_weight")).__name__))

    chunk_ids = [row.get("chunk_id") for row in rows]
    duplicates = [cid for cid, count in Counter(chunk_ids).items() if count > 1]

    word_char_mismatch = []
    for row in rows:
        text = row.get("text", "") if isinstance(row.get("text"), str) else ""
        wc = len(text.split())
        cc = len(text)
        if row.get("chunk_word_count") != wc or row.get("chunk_char_count") != cc:
            word_char_mismatch.append(
                (row.get("_line"), row.get("chunk_id"), row.get("chunk_word_count"), wc, row.get("chunk_char_count"), cc)
            )

    report = {
        "file": str(input_path),
        "total_rows": len(rows),
        "json_errors": len(json_errors),
        "missing_required_field_rows": len(missing),
        "duplicate_chunk_ids": len(duplicates),
        "empty_or_invalid_text_rows": len(empty_text),
        "bad_type_rows": len(bad_types),
        "negative_chunk_index_rows": len(negative_index),
        "word_or_char_count_mismatch_rows": len(word_char_mismatch),
    }
    clean = not any([json_errors, missing, duplicates, empty_text, bad_types, negative_index])
    return clean, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate chunked JSONL dataset.")
    parser.add_argument("--input", required=True, help="Path to chunks JSONL file")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}")
        return 1

    clean, report = validate_chunks(input_path)
    print("VALIDATION REPORT")
    for key in [
        "file",
        "total_rows",
        "json_errors",
        "missing_required_field_rows",
        "duplicate_chunk_ids",
        "empty_or_invalid_text_rows",
        "bad_type_rows",
        "negative_chunk_index_rows",
        "word_or_char_count_mismatch_rows",
    ]:
        print(f"{key}: {report[key]}")
    print(f"status: {'PASS' if clean else 'FAIL'}")
    return 0 if clean else 2


if __name__ == "__main__":
    raise SystemExit(main())

