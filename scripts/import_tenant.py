#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import chromadb


def batched(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def main():
    p = argparse.ArgumentParser(description="Import JSONL into a memL tenant collection")
    p.add_argument("--data-dir", default="/opt/memL/data/chromadb")
    p.add_argument("--collection", required=True)
    p.add_argument("--in", dest="in_file", required=True)
    p.add_argument("--batch", type=int, default=256)
    args = p.parse_args()

    in_path = Path(args.in_file)
    if not in_path.exists():
        raise SystemExit(f"input file not found: {in_path}")

    client = chromadb.PersistentClient(path=args.data_dir)
    col = client.get_or_create_collection(name=args.collection)

    ids, docs, metas, embs = [], [], [], []
    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ids.append(rec["id"])
            docs.append(rec.get("document", ""))
            metas.append(rec.get("metadata", {}))
            embs.append(rec.get("embedding"))

    imported = 0
    for idxs in batched(list(range(len(ids))), args.batch):
        b_ids = [ids[i] for i in idxs]
        b_docs = [docs[i] for i in idxs]
        b_metas = [metas[i] for i in idxs]
        b_embs = [embs[i] for i in idxs]
        if all(e is not None for e in b_embs):
            col.upsert(ids=b_ids, documents=b_docs, metadatas=b_metas, embeddings=b_embs)
        else:
            col.upsert(ids=b_ids, documents=b_docs, metadatas=b_metas)
        imported += len(b_ids)

    print(f"imported={imported} collection={args.collection}")


if __name__ == "__main__":
    main()
