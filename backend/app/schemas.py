from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class PrefsIn(BaseModel):
    types: list[str] = Field(default_factory=list, max_length=12)
    genders: list[str] = Field(default_factory=list, max_length=6)
    colours: list[str] = Field(default_factory=list, max_length=12)
    max_price: float | None = Field(default=None, gt=0, le=5000)
    sustain: float = Field(default=0.3, ge=0, le=1)


class InteractionIn(BaseModel):
    pid: int = Field(ge=0)
    event: Literal["view", "click", "like", "dislike", "clear_reaction"]


class WishlistIn(BaseModel):
    pid: int = Field(ge=0)


class SocialCsvIn(BaseModel):
    csv_text: str = Field(min_length=10, max_length=5_000_000)
