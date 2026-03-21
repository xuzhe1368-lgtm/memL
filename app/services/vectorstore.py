from __future__ import annotations

import json
import chromadb
from app.config import settings


def _pack_meta(meta: dict, tags: list[str], created: str, updated: str) -> dict:
    # Chroma metadata 推荐标量；这里把复杂字段 json 化
    return {
        "_tags_json": json.dumps(tags, ensure_ascii=False),
        "_meta_json": json.dumps(meta, ensure_ascii=False),
        "_created": created,
        "_updated": updated,
    }


def _unpack_meta(md: dict) -> tuple[list[str], dict, str, str]:
    tags = json.loads(md.get("_tags_json", "[]"))
    meta = json.loads(md.get("_meta_json", "{}"))
    created = md.get("_created", "")
    updated = md.get("_updated", "")
    return tags, meta, created, updated


class VectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.data_dir)

    def collection(self, name: str):
        return self.client.get_or_create_collection(name=name)

    def add(self, collection_name: str, mem_id: str, text: str, embedding: list[float], metadata: dict):
        col = self.collection(collection_name)
        col.add(ids=[mem_id], documents=[text], embeddings=[embedding], metadatas=[metadata])

    def get(self, collection_name: str, mem_id: str):
        col = self.collection(collection_name)
        res = col.get(ids=[mem_id], include=["documents", "metadatas"])
        if not res["ids"]:
            return None
        return {
            "id": res["ids"][0],
            "text": res["documents"][0],
            "metadata": res["metadatas"][0],
        }

    def update(self, collection_name: str, mem_id: str, text: str | None, embedding: list[float] | None, metadata: dict | None):
        col = self.collection(collection_name)
        kwargs = {"ids": [mem_id]}
        if text is not None:
            kwargs["documents"] = [text]
        if embedding is not None:
            kwargs["embeddings"] = [embedding]
        if metadata is not None:
            kwargs["metadatas"] = [metadata]
        col.update(**kwargs)

    def delete(self, collection_name: str, mem_id: str):
        self.collection(collection_name).delete(ids=[mem_id])

    def query(self, collection_name: str, query_embedding: list[float], n_results: int):
        col = self.collection(collection_name)
        return col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    def list_all(self, collection_name: str):
        col = self.collection(collection_name)
        return col.get(include=["documents", "metadatas"])

    def count(self, collection_name: str) -> int:
        return self.collection(collection_name).count()
