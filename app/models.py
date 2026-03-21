from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class MemoryCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    importance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    promote_to_longterm: bool = False


class MemoryUpdate(BaseModel):
    text: str | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None


class MilestoneCreate(BaseModel):
    project: str = Field(..., min_length=1, max_length=128)
    stage: str = Field(..., min_length=1, max_length=128)
    summary: str = Field(..., min_length=1, max_length=2000)
    next_step: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list)


class MemoryOut(BaseModel):
    id: str
    text: str
    tags: list[str]
    meta: dict[str, Any]
    created: str
    updated: str
    score: float | None = None
