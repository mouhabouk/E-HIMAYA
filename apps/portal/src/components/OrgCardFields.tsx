import { useTranslation } from "react-i18next";
import { isApiError } from "../lib/api";
import {
  IDENTIFIER_TYPES,
  ORG_KINDS,
  type GeoPoint,
  type IdentifierType,
  type OrgCard,
  type OrgKind,
} from "../lib/types";
import {
  isInTunisia,
  isValidEmail,
  isValidIdentifier,
  isValidPhone,
  normalizeIdentifier,
  normalizePhone,
  parseNumber,
} from "../lib/validators";
import { LocationField } from "./LocationField";

/** Form state of the institution card (strings as typed; converted by draftToCard). */
export interface CardDraft {
  name: string;
  kind: OrgKind;
  identifier_type: IdentifierType;
  identifier: string;
  activity_sector: string;
  activity_type: string;
  capacity: string;
  floors: string;
  height_m: string;
  receives_public: boolean;
  address: string;
  location: GeoPoint | null;
  manager_full_name: string;
  manager_phone: string;
  manager_email: string;
  contact_email: string;
  contact_phone: string;
}
export type DraftField = keyof CardDraft;
export type DraftErrors = Partial<Record<DraftField, string>>;

export const CARD_SECTIONS = ["identity", "building", "location", "contacts"] as const;
export type CardSection = (typeof CARD_SECTIONS)[number];

export const SECTION_FIELDS: Readonly<Record<CardSection, readonly DraftField[]>> = {
  identity: ["name", "kind", "identifier_type", "identifier", "activity_sector", "activity_type"],
  building: ["capacity", "floors", "height_m", "receives_public", "address"],
  location: ["location"],
  contacts: ["manager_full_name", "manager_phone", "manager_email", "contact_email", "contact_phone"],
};

export function emptyDraft(): CardDraft {
  return {
    name: "",
    kind: "industrial",
    identifier_type: "mf",
    identifier: "",
    activity_sector: "",
    activity_type: "",
    capacity: "",
    floors: "",
    height_m: "",
    receives_public: false,
    address: "",
    location: null,
    manager_full_name: "",
    manager_phone: "",
    manager_email: "",
    contact_email: "",
    contact_phone: "",
  };
}

const str = (v: string | number | null | undefined) => (v === null || v === undefined ? "" : String(v));

export function draftFromCard(o: OrgCard): CardDraft {
  return {
    name: o.name,
    kind: o.kind,
    identifier_type: o.identifier_type,
    identifier: o.identifier,
    activity_sector: str(o.activity_sector),
    activity_type: str(o.activity_type),
    capacity: str(o.capacity),
    floors: str(o.floors),
    height_m: str(o.height_m),
    receives_public: o.receives_public,
    address: o.address,
    location: o.location,
    manager_full_name: o.manager.full_name,
    manager_phone: o.manager.phone,
    manager_email: str(o.manager.email),
    contact_email: str(o.contact_email),
    contact_phone: str(o.contact_phone),
  };
}

const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

export function draftToCard(d: CardDraft): OrgCard {
  return {
    name: d.name.trim(),
    kind: d.kind,
    identifier_type: d.identifier_type,
    identifier: normalizeIdentifier(d.identifier),
    activity_sector: orNull(d.activity_sector),
    activity_type: orNull(d.activity_type),
    capacity: parseNumber(d.capacity),
    floors: parseNumber(d.floors),
    height_m: parseNumber(d.height_m),
    receives_public: d.receives_public,
    address: d.address.trim(),
    location: d.location ?? { lat: Number.NaN, lon: Number.NaN },
    manager: {
      full_name: d.manager_full_name.trim(),
      phone: normalizePhone(d.manager_phone),
      email: orNull(d.manager_email),
    },
    contact_email: orNull(d.contact_email),
    contact_phone: d.contact_phone.trim() ? normalizePhone(d.contact_phone) : null,
  };
}

function intError(raw: string, required: boolean, min: number): string | undefined {
  const n = parseNumber(raw);
  if (n === null) return required ? "validation.required" : undefined;
  return Number.isInteger(n) && n >= min ? undefined : "validation.integer";
}

/** Client-side checks mirroring the contract; values are i18n keys. */
export function validateDraft(d: CardDraft, sections: readonly CardSection[] = CARD_SECTIONS): DraftErrors {
  const e: DraftErrors = {};
  const fields = new Set(sections.flatMap((s) => SECTION_FIELDS[s]));
  const req = (f: DraftField, v: string) => {
    if (fields.has(f) && !v.trim()) e[f] = "validation.required";
  };
  req("name", d.name);
  req("identifier", d.identifier);
  if (fields.has("identifier") && d.identifier.trim() && !isValidIdentifier(d.identifier_type, d.identifier)) {
    e.identifier = d.identifier_type === "mf" ? "validation.identifierMf" : "validation.identifierRne";
  }
  if (fields.has("capacity")) {
    const err = intError(d.capacity, true, 0);
    if (err) e.capacity = err;
  }
  if (fields.has("floors")) {
    const err = intError(d.floors, false, 0);
    if (err) e.floors = err;
  }
  if (fields.has("height_m")) {
    const h = parseNumber(d.height_m);
    if (h !== null && !(h >= 0)) e.height_m = "validation.positiveNumber";
  }
  req("address", d.address);
  if (fields.has("location")) {
    if (!d.location) e.location = "validation.locationRequired";
    else if (!isInTunisia(d.location)) e.location = "validation.outsideTunisia";
  }
  req("manager_full_name", d.manager_full_name);
  req("manager_phone", d.manager_phone);
  if (fields.has("manager_phone") && d.manager_phone.trim() && !isValidPhone(d.manager_phone)) e.manager_phone = "validation.phone";
  if (fields.has("contact_phone") && d.contact_phone.trim() && !isValidPhone(d.contact_phone)) e.contact_phone = "validation.phone";
  for (const f of ["manager_email", "contact_email"] as const) {
    if (fields.has(f) && d[f].trim() && !isValidEmail(d[f])) e[f] = "validation.email";
  }
  return e;
}

export function sectionOf(field: DraftField): CardSection {
  return CARD_SECTIONS.find((s) => SECTION_FIELDS[s].includes(field)) ?? "identity";
}

/** Body field names (FastAPI `loc`) → form fields. */
const LOC_FIELDS: Readonly<Record<string, DraftField>> = {
  name: "name",
  kind: "kind",
  identifier_type: "identifier_type",
  identifier: "identifier",
  activity_sector: "activity_sector",
  activity_type: "activity_type",
  capacity: "capacity",
  floors: "floors",
  height_m: "height_m",
  receives_public: "receives_public",
  address: "address",
  location: "location",
  contact_email: "contact_email",
  contact_phone: "contact_phone",
};

/**
 * Field a server error belongs to, so the form can show it in place: the contract's codes
 * (`invalid_identifier`, `identifier_already_registered`, `invalid_phone`) and FastAPI's 422 lists
 * (`[{"loc": ["body", "manager", "phone"], …}]`, e.g. a location outside Tunisia).
 */
export function fieldOfServerError(error: unknown, draft: CardDraft): { field: DraftField; key: string } | null {
  if (!isApiError(error)) return null;
  if (error.code === "invalid_identifier" || error.code === "identifier_already_registered") {
    return { field: "identifier", key: `errors.${error.code}` };
  }
  if (error.code === "invalid_phone") {
    const field: DraftField = draft.contact_phone.trim() && !isValidPhone(draft.contact_phone) ? "contact_phone" : "manager_phone";
    return { field, key: "errors.invalid_phone" };
  }
  if (error.status === 422 && Array.isArray(error.detail)) {
    for (const item of error.detail as unknown[]) {
      const loc = (item as { loc?: unknown } | null)?.loc;
      if (!Array.isArray(loc)) continue;
      const path = loc.filter((p): p is string => typeof p === "string" && p !== "body");
      const [head, sub] = path;
      if (head === "manager") {
        const field: DraftField = sub === "phone" ? "manager_phone" : sub === "email" ? "manager_email" : "manager_full_name";
        return { field, key: "errors.validation_error" };
      }
      const field = head ? LOC_FIELDS[head] : undefined;
      if (field) {
        return { field, key: field === "location" ? "validation.outsideTunisia" : "errors.validation_error" };
      }
    }
  }
  return null;
}

// ---------------------------------------------------------------- UI

interface FieldsProps {
  draft: CardDraft;
  errors: DraftErrors;
  onChange: (patch: Partial<CardDraft>) => void;
  disabled?: boolean;
}

function TextField({
  field,
  label,
  draft,
  errors,
  onChange,
  disabled,
  type = "text",
  inputMode,
  required = false,
  hint,
  autoComplete,
  dir,
}: FieldsProps & {
  field: Exclude<DraftField, "kind" | "identifier_type" | "receives_public" | "location">;
  label: string;
  type?: string;
  inputMode?: "numeric" | "decimal" | "tel" | "email" | "text";
  required?: boolean;
  hint?: string;
  autoComplete?: string;
  dir?: "ltr";
}) {
  const { t } = useTranslation();
  const id = `card-${field}`;
  const err = errors[field];
  const describedBy = [hint ? `${id}-hint` : null, err ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field${err ? " field--invalid" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required && <span className="required-mark" aria-hidden="true"> *</span>}
      </label>
      <input
        id={id}
        type={type}
        inputMode={inputMode}
        value={draft[field]}
        required={required}
        disabled={disabled}
        autoComplete={autoComplete}
        dir={dir}
        aria-invalid={!!err}
        aria-describedby={describedBy}
        onChange={(e) => onChange({ [field]: e.target.value })}
      />
      {hint && (
        <span id={`${id}-hint`} className="field__hint">
          {hint}
        </span>
      )}
      {err && (
        <span id={`${id}-error`} className="field__error">
          {t(err)}
        </span>
      )}
    </div>
  );
}

/** Fields of one section of the card (used by the registration wizard and the card editor). */
export function CardSectionFields({ section, ...props }: FieldsProps & { section: CardSection }) {
  const { t } = useTranslation();
  const { draft, onChange, disabled, errors } = props;
  if (section === "identity") {
    return (
      <div className="form-grid">
        <TextField {...props} field="name" label={t("org.name")} required autoComplete="organization" />
        <div className="field">
          <label htmlFor="card-kind">{t("org.kind")}</label>
          <select id="card-kind" value={draft.kind} disabled={disabled} onChange={(e) => onChange({ kind: e.target.value as OrgKind })}>
            {ORG_KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`kinds.${k}`)}
              </option>
            ))}
          </select>
        </div>
        <fieldset className="field field--wide">
          <legend>{t("org.identifierType")}</legend>
          <div className="radios">
            {IDENTIFIER_TYPES.map((type) => (
              <label key={type} className="radio">
                <input
                  type="radio"
                  name="identifier_type"
                  value={type}
                  checked={draft.identifier_type === type}
                  disabled={disabled}
                  onChange={() => onChange({ identifier_type: type })}
                />
                {t(`identifierTypes.${type}`)}
              </label>
            ))}
          </div>
        </fieldset>
        <TextField
          {...props}
          field="identifier"
          label={t("org.identifier")}
          required
          dir="ltr"
          hint={t(draft.identifier_type === "mf" ? "org.identifierHintMf" : "org.identifierHintRne")}
        />
        <TextField {...props} field="activity_sector" label={t("org.activitySector")} />
        <TextField {...props} field="activity_type" label={t("org.activityType")} />
      </div>
    );
  }
  if (section === "building") {
    return (
      <div className="form-grid">
        <TextField {...props} field="capacity" label={t("org.capacity")} hint={t("org.capacityHint")} inputMode="numeric" required />
        <TextField {...props} field="floors" label={t("org.floors")} inputMode="numeric" />
        <TextField {...props} field="height_m" label={t("org.heightM")} hint={t("org.heightHint")} inputMode="decimal" />
        <div className="field field--check">
          <label className="radio">
            <input
              type="checkbox"
              checked={draft.receives_public}
              disabled={disabled}
              onChange={(e) => onChange({ receives_public: e.target.checked })}
            />
            {t("org.receivesPublic")}
          </label>
        </div>
        <TextField {...props} field="address" label={t("org.address")} required autoComplete="street-address" />
      </div>
    );
  }
  if (section === "location") {
    return (
      <LocationField
        legend={t("org.location")}
        value={draft.location}
        onChange={(location) => onChange({ location })}
        error={errors.location ? t(errors.location) : null}
      />
    );
  }
  return (
    <div className="form-grid">
      <TextField {...props} field="manager_full_name" label={t("org.managerName")} required autoComplete="name" />
      <TextField {...props} field="manager_phone" label={t("org.managerPhone")} type="tel" inputMode="tel" required dir="ltr" hint={t("org.phoneHint")} />
      <TextField {...props} field="manager_email" label={t("org.managerEmail")} type="email" dir="ltr" />
      <TextField {...props} field="contact_email" label={t("org.contactEmail")} type="email" dir="ltr" />
      <TextField {...props} field="contact_phone" label={t("org.contactPhone")} type="tel" inputMode="tel" dir="ltr" hint={t("org.phoneHint")} />
    </div>
  );
}
