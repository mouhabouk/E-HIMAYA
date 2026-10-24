import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# Specialties a doctor can declare (labels in the clients' translations). A fixed list in C1-a.
Specialty = Literal[
    "general_practice",
    "emergency_medicine",
    "anesthesia_icu",
    "cardiology",
    "pulmonology",
    "neurology",
    "pediatrics",
    "obstetrics_gynecology",
    "internal_medicine",
    "endocrinology",
    "nephrology",
    "gastroenterology",
    "allergy_immunology",
    "infectious_diseases",
    "dermatology_burns",
    "orthopedics",
    "general_surgery",
    "psychiatry",
    "toxicology",
    "ophthalmology",
    "ent",
]
DoctorKind = Literal["volunteer", "civil_protection"]
DoctorStatus = Literal["pending", "approved", "rejected", "suspended", "withdrawn"]
Text = Annotated[str, StringConstraints(strip_whitespace=True)]
# The medical council's registration number, or a staff number: letters, digits, "-" and "/".
Number = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=30, pattern=r"^[A-Za-z0-9/-]+$")
]


class DoctorIn(BaseModel):
    kind: DoctorKind
    specialties: list[Specialty] = Field(min_length=1, max_length=4)
    licence_no: Number
    workplace: Annotated[Text, StringConstraints(min_length=2, max_length=150)]
    gouvernorat_code: int = Field(ge=11, le=83)
    cp_unit: Annotated[Text, StringConstraints(min_length=2, max_length=150)] | None = None
    cp_staff_no: Number | None = None
    # The doctor read and accepted the terms of this version (a remote opinion is advisory, files stay secret).
    terms_version: str = Field(max_length=16)
    version: int | None = None


class DoctorOut(BaseModel):
    kind: DoctorKind
    status: DoctorStatus
    specialties: list[Specialty]
    licence_no: str | None
    workplace: str
    gouvernorat_code: int
    cp_unit: str | None
    cp_staff_no: str | None
    review_reason: str | None
    submitted_at: datetime
    reviewed_at: datetime | None
    available: bool
    available_until: datetime | None
    version: int


class AvailabilityIn(BaseModel):
    available: bool
    hours: int = Field(default=8, ge=1, le=24)


class StaffDoctor(BaseModel):
    id: uuid.UUID
    full_name: str | None
    kind: DoctorKind
    specialties: list[Specialty]
    workplace: str
    gouvernorat_code: int
    cp_unit: str | None
    status: DoctorStatus
    available: bool
    submitted_at: datetime


class StaffDoctorPage(BaseModel):
    items: list[StaffDoctor]
    next_cursor: str | None


class DoctorReviewOut(BaseModel):
    decision: str
    reason: str | None
    at: datetime


class StaffDoctorDetail(StaffDoctor):
    phone: str | None
    email: str | None
    licence_no: str | None
    cp_staff_no: str | None
    review_reason: str | None
    reviews: list[DoctorReviewOut]


class DoctorReviewIn(BaseModel):
    decision: Literal["approve", "reject", "suspend", "reinstate"]
    reason: Annotated[Text, StringConstraints(max_length=1000)] | None = None


class DirectoryDoctor(BaseModel):
    """One line of the referral list: no phone, no registration number."""

    id: uuid.UUID
    full_name: str | None
    kind: DoctorKind
    specialties: list[Specialty]
    workplace: str
    gouvernorat_code: int
    available: bool
