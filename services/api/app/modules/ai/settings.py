"""Tunable weights and thresholds of BR-10 (grouping) and BR-20 (priority), stored in ``ai.settings``.

Defaults live here; the dashboard can override them (central committee). Every change is audited.
"""

from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import AiSettingsRow
from app.modules.reports.domain import Category

PRIORITY_COMPONENTS = (
    "severity",
    "lives",
    "casualties",
    "reporters",
    "credibility",
    "sensitive_sites",
    "weather",
    "op_level",
    "vision_fire",
)
# Components added after settings may have been saved: a stored value without them takes the default.
_ADDED_WEIGHTS = {"op_level": 10, "vision_fire": 10}


class PrioritySettings(BaseModel):
    # Points out of 100 per component (BR-20). Components without data yet are left out and the others rescaled.
    weights: dict[str, int] = Field(
        default_factory=lambda: {
            "severity": 35,
            "lives": 25,
            "casualties": 10,
            "reporters": 10,
            "credibility": 10,
            "sensitive_sites": 5,
            "weather": 5,
            "op_level": _ADDED_WEIGHTS["op_level"],
            "vision_fire": _ADDED_WEIGHTS["vision_fire"],
        }
    )
    # Intrinsic gravity of each type, 0 to 1.
    category_severity: dict[Category, float] = Field(
        default_factory=lambda: {
            Category.SOS: 0.9,
            Category.FIRE: 0.8,
            Category.FLOOD: 0.75,
            Category.TRAFFIC_ACCIDENT: 0.6,
            Category.DROWNING: 0.9,
            Category.LANDSLIDE: 0.7,
            Category.CHEMICAL_LEAK: 0.85,
            Category.MEDICAL: 0.7,
            Category.OTHER: 0.3,
        }
    )
    # A category suggested by the model raises the severity only above this confidence (never lowers it).
    suggestion_min_confidence: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def _upgrade(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("weights"), dict):
            data = {**data, "weights": {**_ADDED_WEIGHTS, **data["weights"]}}
        return data

    @model_validator(mode="after")
    def _complete(self) -> "PrioritySettings":
        if set(self.weights) != set(PRIORITY_COMPONENTS):
            raise ValueError(f"weights must have exactly: {', '.join(PRIORITY_COMPONENTS)}")
        if any(not 0 <= w <= 100 for w in self.weights.values()) or sum(self.weights.values()) == 0:
            raise ValueError("weights must be between 0 and 100 and not all zero")
        if set(self.category_severity) != set(Category):
            raise ValueError("category_severity must list every category")
        if any(not 0 <= v <= 1 for v in self.category_severity.values()):
            raise ValueError("category_severity values must be between 0 and 1")
        return self


class GroupingSettings(BaseModel):
    # BR-10: same type, closer than the type's radius and within the time window...
    window_min: int = Field(default=60, ge=5, le=1440)
    radius_m: dict[Category, int] = Field(
        default_factory=lambda: {
            Category.SOS: 300,
            Category.FIRE: 500,
            Category.FLOOD: 2000,
            Category.TRAFFIC_ACCIDENT: 200,
            Category.DROWNING: 500,
            Category.LANDSLIDE: 1000,
            Category.CHEMICAL_LEAK: 1000,
            Category.MEDICAL: 100,
            Category.OTHER: 300,
        }
    )
    # ...or semantically close content within a wider area and window.
    semantic_min_similarity: float = Field(default=0.88, ge=0.5, le=0.99)
    semantic_radius_m: int = Field(default=5000, ge=100, le=50_000)
    semantic_window_min: int = Field(default=180, ge=5, le=2880)

    @model_validator(mode="after")
    def _complete(self) -> "GroupingSettings":
        if set(self.radius_m) != set(Category):
            raise ValueError("radius_m must list every category")
        if any(not 10 <= v <= 50_000 for v in self.radius_m.values()):
            raise ValueError("radius_m values must be between 10 and 50000")
        return self


class AssistSettings(BaseModel):
    """AI-01: each suggestion of the local language model in the operations can be switched off here (design-l4.md
    §9, design-l5.md §2.3). Off, the button is refused and nothing queued is read; what was already suggested stays
    with its label."""

    # The task list read from an intervention plan (AI2).
    plan_reading: bool = True


class AiSettings(BaseModel):
    priority: PrioritySettings = Field(default_factory=PrioritySettings)
    grouping: GroupingSettings = Field(default_factory=GroupingSettings)
    assist: AssistSettings = Field(default_factory=AssistSettings)


async def load(session: AsyncSession) -> AiSettings:
    row = await session.get(AiSettingsRow, 1)
    return AiSettings.model_validate(row.value) if row is not None else AiSettings()


async def save(session: AsyncSession, value: AiSettings, actor: str) -> dict[str, Any]:
    data = value.model_dump(mode="json")
    row = await session.get(AiSettingsRow, 1, with_for_update=True)
    if row is None:
        session.add(AiSettingsRow(id=1, value=data, updated_by=actor))
    else:
        row.value = data
        row.updated_by = actor
    await session.flush()
    return data
