from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class MemoryCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    text: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None


class MemoryOut(BaseModel):
    id: str
    text: str
    tags: list[str]
    meta: dict[str, Any]
    created: str
    updated: str
    score: float | None = None
