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


class PlaceName(BaseModel):
    """One administrative unit of an address: its identifier (délégation id, imada code, municipality id) and names."""

    id: str
    name_ar: str
    name_fr: str


class AdminAddressOut(BaseModel):
    """Délégation, imada and municipality containing a position (phase M); each null outside the land."""

    delegation: PlaceName | None = None
    sector: PlaceName | None = None
    municipality: PlaceName | None = None
