"""End-to-end CLI orchestrator for vector ingest dataset pipeline.

Runs stages in order:
1) validate
2) normalize
3) precheck
4) ingest (optional apply)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], step_name: str) -> None:
    print(f"\n=== {step_name} ===")
    print(" ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full pre-chunked vector ingest pipeline.")
    parser.add_argument("--input", required=True, help="Input chunks JSONL")
    parser.add_argument("--normalized-output", default="", help="Optional normalized output path")
    parser.add_argument("--apply", action="store_true", help="Apply ingest writes")
    parser.add_argument("--reset-chroma-collection", action="store_true", help="Recreate target collection before ingest")
    parser.add_argument("--limit", type=int, default=0, help="Optional ingest row limit")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return 1

    normalized_output = Path(args.normalized_output) if args.normalized_output else input_path.with_suffix(".normalized.jsonl")

    py = sys.executable
    base = Path(__file__).parent

    run_step([py, str(base / "dataset_validator.py"), "--input", str(input_path)], "Validate")
    run_step(
        [py, str(base / "dataset_normalizer.py"), "--input", str(input_path), "--output", str(normalized_output)],
        "Normalize",
    )
    run_step([py, str(base / "ingest_precheck.py"), "--input", str(normalized_output)], "Precheck")

    ingest_cmd = [py, str(base / "chunk_ingest_runner.py"), "--input", str(normalized_output)]
    if args.limit and args.limit > 0:
        ingest_cmd += ["--limit", str(args.limit)]
    if args.apply:
        ingest_cmd.append("--apply")
    if args.reset_chroma_collection:
        ingest_cmd.append("--reset-chroma-collection")
    run_step(ingest_cmd, "Ingest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

