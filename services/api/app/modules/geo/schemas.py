from pydantic import BaseModel, ConfigDict


class DelegationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    gouvernorat_code: int
    name: str
    name_ar: str
    name_fr: str


class GouvernoratOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: int
    iso_code: str
    name: str
    name_ar: str
    name_fr: str
    name_en: str
    delegation_count: int
