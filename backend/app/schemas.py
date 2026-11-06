from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RecordsRequest(BaseModel):
    records: list[dict[str, Any]] = Field(..., min_length=1,
                                          description="Patient feature dicts; use null for unknown values.")


class AssessRequest(RecordsRequest):
    labels: list[int] | None = Field(None, description="Optional 0/1 outcomes aligned with records.")


class SignUpRequest(BaseModel):
    name: str = Field(..., max_length=200)
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=256)
    accept_terms: bool = False


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=256)


class ForgotRequest(BaseModel):
    email: str = Field("", max_length=320)


class ResetRequest(BaseModel):
    token: str = Field(..., max_length=512)
    password: str = Field(..., max_length=256)
