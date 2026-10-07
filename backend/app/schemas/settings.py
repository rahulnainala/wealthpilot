"""Request/response models for the key/value settings store."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any


class SettingWrite(BaseModel):
    value: Any
