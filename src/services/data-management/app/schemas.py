"""Pydantic models exposed by the Data Management API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

DatasetStatus = Literal["uploading", "validating", "validated", "invalid", "failed"]


class DatasetVersion(BaseModel):
    version: str
    name: Optional[str] = None
    images: int = 0
    cats: int = 0
    dogs: int = 0
    cat_pct: float = 0.0
    status: DatasetStatus = "uploading"
    object_key: Optional[str] = None
    dvc_file: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    created_at: str = ""


class DatasetList(BaseModel):
    total: int
    datasets: list[DatasetVersion]


class HealthResponse(BaseModel):
    status: str
    service: str