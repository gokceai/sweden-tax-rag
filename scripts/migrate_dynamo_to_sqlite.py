#!/usr/bin/env python3
"""
One-time migration: DynamoDB Local → SQLite encrypted document store.

What it does
------------
- Reads every item from the DynamoDB Local table (via boto3 scan).
- Copies the already-Fernet-encrypted text directly into the new SQLite store.
- Never decrypts anything — the ciphertext moves as-is, so MASTER_ENCRYPTION_KEY
  is NOT required to run this script.

Prerequisites
-------------
1. DynamoDB Local must be reachable:
       docker compose up -d dynamodb-local
2. .env must be present with DYNAMO_* variables uncommented (see .env.example).
3. Run from the project root:
       python scripts/migrate_dynamo_to_sqlite.py

After successful migration
--------------------------
- The new SQLite file will be at SQLITE_DB_PATH (default: ./docker/documents.db).
- Comment out / remove the DYNAMO_* variables from .env.
- Shut down the dynamodb-local container:
       docker compose stop dynamodb-local
"""

import json
import os
import sqlite3
import sys

# Allow running from project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.exceptions import ClientError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id       TEXT PRIMARY KEY,
    encrypted_text TEXT NOT NULL,
    source         TEXT DEFAULT 'unknown',
    chunk_index    INTEGER DEFAULT 0,
    extra_metadata TEXT DEFAULT '{}'
)
"""


def main() -> None:
    dynamo_endpoint = os.getenv("DYNAMO_ENDPOINT", "http://localhost:8000")
    dynamo_region = os.getenv("DYNAMO_REGION", "eu-north-1")
    dynamo_access_key = os.getenv("DYNAMO_ACCESS_KEY_ID", "test")
    dynamo_secret_key = os.getenv("DYNAMO_SECRET_ACCESS_KEY", "test")
    dynamo_table_name = os.getenv("DYNAMO_TABLE_NAME", "SwedishTaxDocuments")
    sqlite_path = os.getenv("SQLITE_DB_PATH", "./docker/documents.db")

    print("=" * 60)
    print("DynamoDB Local → SQLite migration")
    print("=" * 60)
    print(f"  Source : {dynamo_endpoint}  table='{dynamo_table_name}'")
    print(f"  Target : {sqlite_path}")
    print()

    # ------------------------------------------------------------------ #
    # Connect to DynamoDB Local                                           #
    # ------------------------------------------------------------------ #
    try:
        resource = boto3.resource(
            "dynamodb",
            endpoint_url=dynamo_endpoint,
            region_name=dynamo_region,
            aws_access_key_id=dynamo_access_key,
            aws_secret_access_key=dynamo_secret_key,
        )
        table = resource.Table(dynamo_table_name)
        table.load()  # raises ClientError if table does not exist
    except ClientError as e:
        print(f"ERROR: Cannot access DynamoDB Local: {e}")
        print("Make sure 'docker compose up -d dynamodb-local' is running.")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Initialise SQLite target                                            #
    # ------------------------------------------------------------------ #
    db_dir = os.path.dirname(sqlite_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(sqlite_path)
    conn.execute(_SCHEMA)
    conn.commit()

    # ------------------------------------------------------------------ #
    # Scan DynamoDB and write to SQLite                                   #
    # ------------------------------------------------------------------ #
    migrated = 0
    skipped = 0
    response = table.scan()

    while True:
        for item in response.get("Items", []):
            chunk_id = item.get("chunk_id")
            encrypted_text = item.get("encrypted_text")

            if not chunk_id or not encrypted_text:
                print(f"  SKIP (missing fields): keys={list(item.keys())}")
                skipped += 1
                continue

            source = item.get("source", "unknown")
            chunk_index = int(item.get("chunk_index", 0))
            extra = {
                k: v
                for k, v in item.items()
                if k not in {"chunk_id", "encrypted_text", "source", "chunk_index"}
            }

            conn.execute(
                """
                INSERT INTO document_chunks
                    (chunk_id, encrypted_text, source, chunk_index, extra_metadata)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    encrypted_text = excluded.encrypted_text,
                    source         = excluded.source,
                    chunk_index    = excluded.chunk_index,
                    extra_metadata = excluded.extra_metadata
                """,
                (chunk_id, encrypted_text, source, chunk_index, json.dumps(extra)),
            )
            migrated += 1
            print(f"  OK   {chunk_id}")

        if "LastEvaluatedKey" not in response:
            break
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"Done: {migrated} chunks migrated, {skipped} skipped.")
    if skipped:
        print("WARNING: Some items were skipped. Check logs above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
