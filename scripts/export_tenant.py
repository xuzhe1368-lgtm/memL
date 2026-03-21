#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import chromadb


def main():
    p = argparse.ArgumentParser(description="Export a memL tenant collection to JSONL")
    p.add_argument("--data-dir", default="/opt/memL/data/chromadb")
    p.add_argument("--collection", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    client = chromadb.PersistentClient(path=args.data_dir)
    col = client.get_or_create_collection(name=args.collection)
    rows = col.get(include=["documents", "metadatas", "embeddings"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for i, mem_id in enumerate(rows.get("ids", [])):
            embs = rows.get("embeddings")
            rec = {
                "id": mem_id,
                "document": rows.get("documents", [])[i],
                "metadata": rows.get("metadatas", [])[i],
                "embedding": embs[i] if embs is not None else None,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"exported={len(rows.get('ids', []))} file={out}")


if __name__ == "__main__":
    main()
