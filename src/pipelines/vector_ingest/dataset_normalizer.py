"""Normalize chunk text before encryption and embedding.

Normalization policy:
- Unicode NFC
- newline normalization
- collapse repeated spaces
- collapse excessive blank lines
- strip leading/trailing whitespace
"""

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path


SPACE_RE = re.compile(r"[ \t]+")
MULTI_NL_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = SPACE_RE.sub(" ", text)
    text = MULTI_NL_RE.sub("\n\n", text)
    return text.strip()


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize chunks JSONL text and refresh counters/hash.")
    parser.add_argument("--input", required=True, help="Source JSONL")
    parser.add_argument("--output", required=True, help="Normalized JSONL output")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    if not in_path.exists():
        print(f"ERROR: file not found: {in_path}")
        return 1

    changed_rows = 0
    changed_hash = 0
    total_rows = 0
    out_lines = []

    for line in in_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        total_rows += 1

        original_text = row.get("text", "")
        normalized_text = normalize_text(original_text) if isinstance(original_text, str) else ""
        if normalized_text != original_text:
            changed_rows += 1

        row["text"] = normalized_text
        row["chunk_word_count"] = len(normalized_text.split())
        row["chunk_char_count"] = len(normalized_text)

        new_chunk_hash = sha256_hex(normalized_text)
        if row.get("chunk_text_hash") != new_chunk_hash:
            changed_hash += 1
        row["chunk_text_hash"] = new_chunk_hash

        out_lines.append(json.dumps(row, ensure_ascii=False))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print("NORMALIZATION REPORT")
    print(f"input: {in_path}")
    print(f"output: {out_path}")
    print(f"total_rows: {total_rows}")
    print(f"text_changed_rows: {changed_rows}")
    print(f"content_hash_changed_rows: {changed_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

