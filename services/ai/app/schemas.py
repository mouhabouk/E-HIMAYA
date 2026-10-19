"""Request and response bodies of the inference API (contract: docs/api/phase-3-contract.md §6)."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "sos", "fire", "flood", "traffic_accident", "drowning", "landslide", "chemical_leak", "medical", "other"
]
Hazard = Literal[
    "gas", "chemical", "electricity", "explosion", "fuel", "building_collapse", "spreading_fire", "rising_water"
]
TextLanguage = Literal["ar", "ar_latn", "fr", "en", "other"]


class TranscribeIn(BaseModel):
    url: str = Field(max_length=4096)
    # Forced language; None = detected among ar, fr, en.
    language: Literal["ar", "fr", "en"] | None = None


class Segment(BaseModel):
    start: float
    end: float
    text: str


class TranscribeOut(BaseModel):
    text: str
    language: str
    language_probability: float
    duration_s: float
    segments: list[Segment]
    model: str


class TranslateIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)
    source: Literal["fr", "en"]


class TranslateOut(BaseModel):
    texts: list[str]
    model: str


class EmbedIn(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)


class EmbedOut(BaseModel):
    vectors: list[list[float]]
    dim: int
    model: str


class ExtractIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    reported_category: Category


class Extraction(BaseModel):
    """What the language model reads in a report. Suggestions only: nothing here is applied automatically."""

    language: TextLanguage
    category: Category
    lives_at_risk: bool
    people_trapped: bool
    injured_count: int = Field(ge=0, le=10_000)
    deaths_reported: bool
    hazards: list[Hazard] = Field(max_length=8)
    keywords: list[str] = Field(max_length=8)
    summary_ar: str = Field(max_length=600)
    confidence: float = Field(ge=0, le=1)


class ExtractOut(Extraction):
    model: str


class CapabilityHealth(BaseModel):
    ready: bool
    model: str | None
    detail: str | None = None


class HealthOut(BaseModel):
    transcribe: CapabilityHealth
    translate_fr: CapabilityHealth
    translate_en: CapabilityHealth
    embed: CapabilityHealth
    extract: CapabilityHealth
