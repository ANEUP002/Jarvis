#!/usr/bin/env python

import json
import os
import sys
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tools.vector_db_advanced import AdvancedVectorStore


def main():
    db_dir = Path("vector_db_advanced")
    metadata_file = db_dir / "metadata.json"
    backup_file = db_dir / "metadata.backup.json"

    if not metadata_file.exists():
        print("No advanced vector metadata found.")
        return

    with open(metadata_file, "r", encoding="utf-8") as f:
        existing_metadata = json.load(f)

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(existing_metadata, f, indent=2)

    store = AdvancedVectorStore(db_dir=str(db_dir), embedding_provider="huggingface")
    store.metadata = {}
    store.embeddings = {}

    for key, meta in existing_metadata.items():
        text = meta.get("text", "")
        user_metadata = meta.get("metadata", {})
        success = store.store(key, text, user_metadata)
        provider = store.embeddings.get(key, {}).get("provider", "unknown")
        print(f"{key}: success={success} provider={provider}")

    print("Rebuild complete.")
    print(f"Provider in use: {store.provider_name}")
    print(f"Fallback active: {store.fallback_active}")


if __name__ == "__main__":
    main()
