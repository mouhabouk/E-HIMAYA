// covers: phase L2 (docs/phase-l/design-l2.md §2.2 to §2.4, §2.7): one programme, its points on the map, the daily
// follow-up of the regional room, the versions with their differences and the way back.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type SyntheticEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import { LazyPolygonDrawMap } from "../components/LazyPolygonMap";
import type { MapPoi } from "../components/MapView";
import { PageTitle } from "../components/PageTitle";
import { InlineDialog, ReasonField } from "../components/Phase9Bits";
import { DiffView, ProgrammeStatusPill } from "../components/ProgrammeBits";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { LAYER_ICON_PATHS } from "../lib/layers";
import { initialBoundsFor } from "../lib/mapStyle";
import { reasonValid } from "../lib/phase9";
import {
  CONFIDENCES,
  coverage,
  filterPoints,
  isLowCoverage,
  POINT_STATUSES,
  PROGRAMME_CODE,
  programmeKeys,
  totalGaps,
  type PointFilters,
  type PointStatus,
  type Programme,
  type ProgrammeDetail,
  type ProgrammePoint,
} from "../lib/programmes";

const POINT_COLOURS: Record<PointStatus, string> = {
  open: "#188038",
  postponed: "#F5B400",
  closed: "#5B6478",
};
const POINT_TONE: Record<PointStatus, string> = {
  open: "tone-green",
  postponed: "tone-amber",
  closed: "tone-slate",
};
const LIVE = ["approved", "updated"];

function PointStatusPill({ status }: { status: PointStatus }) {
  const { t } = useTranslation();
  return <span className={`pill ${POINT_TONE[status]}`}>{t(`programmes.pointStatus.${status}`)}</span>;
}

/** Writes on the programme refresh the page from the detail the API returns. */
function useDetailWrite<A>(programmeId: string, write: (a: A) => Promise<ProgrammeDetail>, onDone?: () => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: (detail) => {
      qc.setQueryData(programmeKeys.detail(programmeId), detail);
      void qc.invalidateQueries({ queryKey: programmeKeys.list });
      void qc.invalidateQueries({
        queryKey: programmeKeys.revisions(programmeId),
      });
      onDone?.();
    },
  });
}

function MutationError({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p role="alert" className="alert alert--error">
      {t(errorMessageKey(error))}
    </p>
  );
}

// ---------------------------------------------------------------- programme actions (§2.2)

type Action = "approve" | "edit" | "cancel" | "copy" | "delete";

function ActionDialog({ programme, action, onClose }: { programme: Programme; action: Action; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const id = useId();
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [fields, setFields] = useState({
    title: programme.title,
    season: programme.season,
    valid_from: programme.valid_from,
    valid_to: programme.valid_to,
    source_document: programme.source_document,
    code: "",
  });
  const draft = programme.status === "draft";
  const reasonNeeded = action === "cancel" || (action === "edit" && !draft);
  const write = useDetailWrite(
    programme.id,
    async (): Promise<ProgrammeDetail> => {
      const why = reason.trim();
      if (action === "approve") return api.approveProgramme(programme.id, why);
      if (action === "cancel") return api.cancelProgramme(programme.id, why);
      const { code: _code, ...rest } = fields;
      return api.updateProgramme(programme.id, { ...rest, reason: why });
    },
    onClose,
  );
  const copy = useMutation({
    mutationFn: () =>
      api.copyProgramme(programme.id, {
        code: fields.code.trim().toUpperCase(),
        valid_from: fields.valid_from,
        valid_to: fields.valid_to,
        season: fields.season,
        title: fields.title,
      }),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: programmeKeys.list });
      onClose();
      void navigate(`/programmes/${d.programme.id}`);
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteProgramme(programme.id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: programmeKeys.all });
      void navigate("/programmes");
    },
  });
  const datesOk = Boolean(fields.valid_from && fields.valid_to && fields.valid_from <= fields.valid_to);
  const codeOk = action !== "copy" || PROGRAMME_CODE.test(fields.code.trim().toUpperCase());
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (action === "delete") return remove.mutate();
    if (reasonNeeded && !reasonValid(reason)) return;
    if ((action === "edit" || action === "copy") && (!datesOk || !codeOk)) return;
    if (action === "copy") copy.mutate();
    else write.mutate(undefined);
  };
  const set = (patch: Partial<typeof fields>) => setFields((f) => ({ ...f, ...patch }));
  const dated = action === "edit" || action === "copy";
  return (
    <InlineDialog title={t(`programmes.action.${action}.title`)} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <p>{t(`programmes.action.${action}.explain`)}</p>
        {action === "copy" && (
          <div className="field">
            <label htmlFor={`${id}-code`}>{t("programmes.field.code")}</label>
            <input
              id={`${id}-code`}
              dir="ltr"
              value={fields.code}
              aria-required="true"
              aria-invalid={(tried && !codeOk) || undefined}
              aria-describedby={`${id}-code-help`}
              onChange={(e) => set({ code: e.target.value })}
            />
            <p id={`${id}-code-help`} className={tried && !codeOk ? "field__error" : "muted"}>
              {t("programmes.new.codeHelp")}
            </p>
          </div>
        )}
        {dated && (
          <div className="form-grid">
            <div className="field">
              <label htmlFor={`${id}-title`}>{t("programmes.field.title")}</label>
              <input
                id={`${id}-title`}
                value={fields.title}
                maxLength={300}
                onChange={(e) => set({ title: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor={`${id}-season`}>{t("programmes.field.season")}</label>
              <input
                id={`${id}-season`}
                value={fields.season}
                maxLength={80}
                onChange={(e) => set({ season: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor={`${id}-from`}>{t("programmes.field.valid_from")}</label>
              <input
                id={`${id}-from`}
                type="date"
                value={fields.valid_from}
                aria-invalid={(tried && !datesOk) || undefined}
                onChange={(e) => set({ valid_from: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor={`${id}-to`}>{t("programmes.field.valid_to")}</label>
              <input
                id={`${id}-to`}
                type="date"
                value={fields.valid_to}
                aria-invalid={(tried && !datesOk) || undefined}
                onChange={(e) => set({ valid_to: e.target.value })}
              />
            </div>
            {action === "edit" && (
              <div className="field">
                <label htmlFor={`${id}-source`}>{t("programmes.field.source_document")}</label>
                <input
                  id={`${id}-source`}
                  value={fields.source_document}
                  maxLength={300}
                  onChange={(e) => set({ source_document: e.target.value })}
                />
              </div>
            )}
          </div>
        )}
        {dated && tried && !datesOk && <p className="field__error">{t("programmes.new.datesHelp")}</p>}
        {action !== "delete" && action !== "copy" && (
          <ReasonField
            label={t(reasonNeeded ? "programmes.reason" : "programmes.reasonOptional")}
            value={reason}
            onChange={setReason}
            showError={tried && reasonNeeded}
          />
        )}
        <MutationError error={write.error ?? copy.error ?? remove.error} />
        <div className="actions">
          <button
            type="submit"
            className={`btn ${action === "cancel" || action === "delete" ? "btn--danger" : "btn--primary"}`}
            disabled={write.isPending || copy.isPending || remove.isPending}
          >
            {t(`programmes.action.${action}.confirm`)}
          </button>
        </div>
      </form>
    </InlineDialog>
  );
}

// ---------------------------------------------------------------- points (§2.3, §2.4)

function PointFiltersForm({ value, onChange }: { value: PointFilters; onChange: (f: PointFilters) => void }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const id = useId();
  return (
    <form className="filters card" aria-label={t("programmes.points.filters")} onSubmit={(e) => e.preventDefault()}>
      <div className="filters__row">
        <div className="field">
          <label htmlFor={`${id}-text`}>{t("programmes.points.search")}</label>
          <input
            id={`${id}-text`}
            type="search"
            value={value.text ?? ""}
            onChange={(e) => onChange({ ...value, text: e.target.value || undefined })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-gov`}>{t("programmes.field.gouvernorat_code")}</label>
          <select
            id={`${id}-gov`}
            value={value.gouvernorat ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                gouvernorat: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          >
            <option value="">{t("programmes.all")}</option>
            {gouvernorats.list.map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-status`}>{t("programmes.field.status")}</label>
          <select
            id={`${id}-status`}
            value={value.status ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                status: (e.target.value || undefined) as PointStatus | undefined,
              })
            }
          >
            <option value="">{t("programmes.all")}</option>
            {POINT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`programmes.pointStatus.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-conf`}>{t("programmes.field.geo_confidence")}</label>
          <select
            id={`${id}-conf`}
            value={value.confidence ?? ""}
            onChange={(e) =>
              onChange({
                ...value,
                confidence: (e.target.value || undefined) as PointFilters["confidence"],
              })
            }
          >
            <option value="">{t("programmes.all")}</option>
            <option value="unlocated">{t("programmes.points.unlocated")}</option>
            {CONFIDENCES.map((c) => (
              <option key={c} value={c}>
                {t(`programmes.confidence.${c}`)}
              </option>
            ))}
          </select>
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={Boolean(value.lowCoverage)}
            onChange={(e) => onChange({ ...value, lowCoverage: e.target.checked || undefined })}
          />
          {t("programmes.points.lowCoverage")}
        </label>
      </div>
    </form>
  );
}

type PointDraft = Record<string, string> & {
  ref: string;
  place_name: string;
  lat: string;
  lon: string;
  geo_confidence: string;
  status: string;
};
const TEXT_FIELDS = ["place_name", "sub_points", "staff_composition", "equipment", "hours", "notes"] as const;
const NUMBER_FIELDS = ["staff_count", "supervisors", "lifeguards_planned", "lifeguards_deployed"] as const;
const DATE_FIELDS = ["opening_date", "closing_date"] as const;
const ROOM_FIELDS = ["supervisor_name", "supervisor_phone"] as const;

function draftOf(p: ProgrammePoint | null): PointDraft {
  const d: PointDraft = {
    ref: "",
    place_name: "",
    lat: "",
    lon: "",
    geo_confidence: "",
    status: "open",
  };
  const all = [
    "ref",
    "gouvernorat_code",
    "lat",
    "lon",
    "geo_confidence",
    "status",
    ...TEXT_FIELDS,
    ...NUMBER_FIELDS,
    ...DATE_FIELDS,
    ...ROOM_FIELDS,
  ];
  for (const k of all) {
    const v = p ? (p as unknown as Record<string, unknown>)[k] : null;
    d[k] = typeof v === "string" || typeof v === "number" ? String(v) : "";
  }
  if (!p) d.status = "open";
  return d;
}

/** The fields that changed, typed for the API (an emptied field is sent as null). */
function changesOf(before: PointDraft, after: PointDraft): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(after)) {
    if (k === "ref" || before[k] === v) continue;
    const trimmed = v.trim();
    if (!trimmed) out[k] = null;
    else if ((NUMBER_FIELDS as readonly string[]).includes(k) || ["gouvernorat_code", "lat", "lon"].includes(k))
      out[k] = Number(trimmed);
    else out[k] = trimmed;
  }
  return out;
}

function PointForm({
  programme,
  point,
  room,
  onClose,
}: {
  programme: Programme;
  point: ProgrammePoint | null;
  room: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const lang = useLanguage();
  const id = useId();
  const [initial] = useState(() => draftOf(point));
  const [form, setForm] = useState(initial);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [bounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const reasonNeeded = programme.status !== "draft";
  const save = useDetailWrite(
    programme.id,
    (body: Record<string, unknown>) =>
      point
        ? api.updateProgrammePoint(programme.id, point.id, {
            ...body,
            reason: reason.trim(),
          })
        : api.addProgrammePoint(programme.id, {
            ...body,
            ref: form.ref.trim(),
            place_name: form.place_name.trim(),
            reason: reason.trim(),
          }),
    onClose,
  );
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const lat = Number(form.lat);
  const lon = Number(form.lon);
  const located = form.lat !== "" && form.lon !== "" && Number.isFinite(lat) && Number.isFinite(lon);
  const changes = changesOf(initial, form);
  const valid = (point || form.ref.trim()) && form.place_name.trim().length >= 2;
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!valid || (reasonNeeded && !reasonValid(reason))) return;
    if (point && Object.keys(changes).length === 0) return;
    save.mutate(changes);
  };
  const input = (k: string, label: string, props: { type?: string; dir?: "ltr"; step?: string } = {}): ReactNode => (
    <div className="field" key={k}>
      <label htmlFor={`${id}-${k}`}>{label}</label>
      <input id={`${id}-${k}`} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} {...props} />
    </div>
  );
  return (
    <InlineDialog
      title={point ? t("programmes.points.edit", { ref: point.ref }) : t("programmes.points.add")}
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate>
        <div className="form-grid">
          {!point && input("ref", t("programmes.field.ref"), { dir: "ltr" })}
          {input("place_name", t("programmes.field.place_name"))}
          {input("sub_points", t("programmes.field.sub_points"))}
          <div className="field">
            <label htmlFor={`${id}-gov`}>{t("programmes.field.gouvernorat_code")}</label>
            <select
              id={`${id}-gov`}
              value={form.gouvernorat_code ?? ""}
              onChange={(e) => set("gouvernorat_code", e.target.value)}
            >
              <option value="">—</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-status`}>{t("programmes.field.status")}</label>
            <select id={`${id}-status`} value={form.status} onChange={(e) => set("status", e.target.value)}>
              {POINT_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`programmes.pointStatus.${s}`)}
                </option>
              ))}
            </select>
          </div>
          {NUMBER_FIELDS.map((k) => input(k, t(`programmes.field.${k}`), { type: "number" }))}
          {input("staff_composition", t("programmes.field.staff_composition"))}
          {input("equipment", t("programmes.field.equipment"))}
          {input("hours", t("programmes.field.hours"))}
          {DATE_FIELDS.map((k) => input(k, t(`programmes.field.${k}`), { type: "date" }))}
          {room &&
            ROOM_FIELDS.map((k) =>
              input(k, t(`programmes.field.${k}`), k === "supervisor_phone" ? { dir: "ltr" } : {}),
            )}
          {input("notes", t("programmes.field.notes"))}
        </div>
        <fieldset className="programme-locate">
          <legend>{t("programmes.points.position")}</legend>
          <p className="muted">{t("programmes.points.positionHelp")}</p>
          <div className="form-grid">
            {input("lat", t("programmes.field.lat"), {
              type: "number",
              dir: "ltr",
              step: "0.000001",
            })}
            {input("lon", t("programmes.field.lon"), {
              type: "number",
              dir: "ltr",
              step: "0.000001",
            })}
            <div className="field">
              <label htmlFor={`${id}-conf`}>{t("programmes.field.geo_confidence")}</label>
              <select
                id={`${id}-conf`}
                value={form.geo_confidence}
                onChange={(e) => set("geo_confidence", e.target.value)}
              >
                <option value="">—</option>
                {CONFIDENCES.map((c) => (
                  <option key={c} value={c}>
                    {t(`programmes.confidence.${c}`)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Suspense fallback={<Loading />}>
            <LazyPolygonDrawMap
              className="map programme-locate__map"
              vertices={located ? [[lon, lat]] : []}
              onAddVertex={(x, y) =>
                setForm((f) => ({
                  ...f,
                  lon: x.toFixed(6),
                  lat: y.toFixed(6),
                  geo_confidence:
                    f.geo_confidence === "" || f.geo_confidence === "unknown" ? "confirmed" : f.geo_confidence,
                }))
              }
              bounds={bounds}
              ariaLabel={t("programmes.points.positionMap")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
            />
          </Suspense>
        </fieldset>
        <ReasonField
          label={t(reasonNeeded ? "programmes.reason" : "programmes.reasonOptional")}
          value={reason}
          onChange={setReason}
          showError={tried && reasonNeeded}
        />
        {tried && !valid && <p className="field__error">{t("programmes.points.required")}</p>}
        {tried && point && Object.keys(changes).length === 0 && (
          <p className="muted">{t("programmes.points.nothing")}</p>
        )}
        <MutationError error={save.error} />
        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("programmes.points.save")}
          </button>
        </div>
      </form>
    </InlineDialog>
  );
}

/** The daily follow-up of the regional room (§2.4): open or closed, lifeguards on the beach, a note. */
function FollowUp({ programme, point, onClose }: { programme: Programme; point: ProgrammePoint; onClose: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const id = useId();
  const [status, setStatus] = useState<PointStatus>(point.status);
  const [deployed, setDeployed] = useState(point.lifeguards_deployed === null ? "" : String(point.lifeguards_deployed));
  const [notes, setNotes] = useState(point.notes ?? "");
  const save = useDetailWrite(
    programme.id,
    () => {
      const body: Record<string, unknown> = {};
      if (status !== point.status) body.status = status;
      const n = deployed.trim() === "" ? null : Number(deployed);
      if (n !== point.lifeguards_deployed) body.lifeguards_deployed = n;
      if (notes.trim() !== (point.notes ?? "")) body.notes = notes.trim() || null;
      return api.updateProgrammePoint(programme.id, point.id, {
        ...body,
        reason: "",
      });
    },
    onClose,
  );
  return (
    <InlineDialog title={t("programmes.followUp.title", { place: point.place_name })} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate(undefined);
        }}
      >
        <div className="form-grid">
          <div className="field">
            <label htmlFor={`${id}-status`}>{t("programmes.field.status")}</label>
            <select id={`${id}-status`} value={status} onChange={(e) => setStatus(e.target.value as PointStatus)}>
              {POINT_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`programmes.pointStatus.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor={`${id}-deployed`}>{t("programmes.field.lifeguards_deployed")}</label>
            <input
              id={`${id}-deployed`}
              type="number"
              min={0}
              value={deployed}
              onChange={(e) => setDeployed(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-notes`}>{t("programmes.field.notes")}</label>
            <input id={`${id}-notes`} value={notes} maxLength={1000} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <MutationError error={save.error} />
        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={save.isPending}>
            {t("programmes.followUp.save")}
          </button>
        </div>
      </form>
    </InlineDialog>
  );
}

function PointsTable({
  programme,
  points,
  room,
  onEdit,
  onFollow,
  onDelete,
}: {
  programme: Programme;
  points: ProgrammePoint[];
  room: boolean;
  onEdit: (p: ProgrammePoint) => void;
  onFollow: (p: ProgrammePoint) => void;
  onDelete: (p: ProgrammePoint) => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  return (
    <div className="table-wrap">
      <table className="table table--compact">
        <caption>{t("programmes.points.caption", { count: points.length })}</caption>
        <thead>
          <tr>
            <th scope="col">{t("programmes.field.place_name")}</th>
            <th scope="col">{t("programmes.field.gouvernorat_code")}</th>
            <th scope="col">{t("programmes.field.status")}</th>
            <th scope="col">{t("programmes.field.geo_confidence")}</th>
            <th scope="col">{t("programmes.figures.coverage")}</th>
            <th scope="col">{t("programmes.field.staff_count")}</th>
            <th scope="col">{t("programmes.field.hours")}</th>
            {room && <th scope="col">{t("programmes.field.supervisor_name")}</th>}
            <th scope="col">
              <span className="visually-hidden">{t("programmes.points.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {points.length === 0 && (
            <tr>
              <td colSpan={room ? 9 : 8} className="muted">
                {t("programmes.points.none")}
              </td>
            </tr>
          )}
          {points.map((p) => {
            const c = coverage(p.lifeguards_planned, p.lifeguards_deployed);
            return (
              <tr key={p.id}>
                <th scope="row">
                  <span dir="auto">{p.place_name}</span>
                  <div className="muted" dir="ltr">
                    {p.ref}
                  </div>
                </th>
                <td>{gouvernorats.nameOf(p.gouvernorat_code) ?? "—"}</td>
                <td>
                  <PointStatusPill status={p.status} />
                </td>
                <td>
                  {p.lat === null ? (
                    <span className="pill tone-amber">{t("programmes.points.unlocated")}</span>
                  ) : (
                    t(`programmes.confidence.${p.geo_confidence}`)
                  )}
                </td>
                <td>
                  {c === null
                    ? "—"
                    : `${fmt.percent(c)} (${fmt.number(p.lifeguards_deployed ?? 0)}/${fmt.number(p.lifeguards_planned ?? 0)})`}
                  {isLowCoverage(p) && (
                    <>
                      {" "}
                      <span className="pill tone-red">{t("programmes.points.low")}</span>
                    </>
                  )}
                </td>
                <td>{p.staff_count === null ? "—" : fmt.number(p.staff_count)}</td>
                <td dir="auto">{p.hours ?? "—"}</td>
                {room && (
                  <td>
                    <span dir="auto">{p.supervisor_name ?? "—"}</span>
                    {p.supervisor_phone && (
                      <div dir="ltr">
                        <a href={`tel:${p.supervisor_phone}`}>{p.supervisor_phone}</a>
                      </div>
                    )}
                  </td>
                )}
                <td className="ops-row-actions">
                  {programme.can_edit && (
                    <button type="button" className="btn btn--small" onClick={() => onEdit(p)}>
                      {t("programmes.points.editShort")}
                      <span className="visually-hidden"> {p.ref}</span>
                    </button>
                  )}
                  {!programme.can_edit && p.can_follow_up && (
                    <button type="button" className="btn btn--small" onClick={() => onFollow(p)}>
                      {t("programmes.followUp.open")}
                      <span className="visually-hidden"> {p.ref}</span>
                    </button>
                  )}
                  {programme.can_edit && programme.status === "draft" && (
                    <button type="button" className="btn btn--small btn--danger" onClick={() => onDelete(p)}>
                      {t("programmes.points.delete")}
                      <span className="visually-hidden"> {p.ref}</span>
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- versions (§2.2)

function Revisions({ programme }: { programme: Programme }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const [shown, setShown] = useState<number | null>(null);
  const [restoring, setRestoring] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const revisions = useQuery({
    queryKey: programmeKeys.revisions(programme.id),
    queryFn: ({ signal }) => api.programmeRevisions(programme.id, signal),
  });
  const diff = useQuery({
    queryKey: programmeKeys.diff(programme.id, shown ?? 0),
    queryFn: ({ signal }) => api.programmeDiff(programme.id, shown ?? 0, signal),
    enabled: shown !== null,
  });
  const restore = useDetailWrite(
    programme.id,
    (n: number) => api.restoreProgramme(programme.id, n, reason.trim()),
    () => {
      setRestoring(null);
      setReason("");
      setTried(false);
    },
  );
  const canRestore = programme.can_edit && (programme.status === "draft" || LIVE.includes(programme.status));
  const actionText = (a: string) => t(`programmes.revisionAction.${a}`, { defaultValue: a });
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("programmes.revisions.title")}</h2>
      {revisions.isLoading && <Loading />}
      {revisions.isError && <ErrorBox error={revisions.error} onRetry={() => void revisions.refetch()} />}
      {revisions.data && (
        <div className="table-wrap">
          <table className="table table--compact">
            <thead>
              <tr>
                <th scope="col">{t("programmes.revisions.number")}</th>
                <th scope="col">{t("programmes.revisions.action")}</th>
                <th scope="col">{t("programmes.revisions.who")}</th>
                <th scope="col">{t("programmes.figures.points")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("programmes.points.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {revisions.data.map((r) => (
                <tr key={r.number}>
                  <th scope="row">v{fmt.number(r.number)}</th>
                  <td>
                    {actionText(r.action)}
                    {r.reason && (
                      <div className="muted" dir="auto">
                        {r.reason}
                      </div>
                    )}
                  </td>
                  <td>
                    {r.created_by_name ?? t("programmes.revisions.system")}
                    <div className="muted">{fmt.dateTime(r.created_at)}</div>
                  </td>
                  <td>{fmt.number(r.points)}</td>
                  <td className="ops-row-actions">
                    {r.number > 1 && (
                      <button
                        type="button"
                        className="btn btn--small"
                        aria-expanded={shown === r.number}
                        onClick={() => setShown(shown === r.number ? null : r.number)}
                      >
                        {t("programmes.revisions.diff", { n: r.number })}
                      </button>
                    )}
                    {canRestore && r.number < programme.version && (
                      <button type="button" className="btn btn--small" onClick={() => setRestoring(r.number)}>
                        {t("programmes.revisions.restore", { n: r.number })}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {shown !== null && (
        <div className="card" aria-live="polite">
          <h3>
            {t("programmes.revisions.diffTitle", {
              n: shown,
              previous: shown - 1,
            })}
          </h3>
          {diff.isLoading && <Loading />}
          {diff.isError && <ErrorBox error={diff.error} onRetry={() => void diff.refetch()} />}
          {diff.data && <DiffView diff={diff.data} />}
        </div>
      )}
      {restoring !== null && (
        <InlineDialog
          title={t("programmes.revisions.restoreTitle", { n: restoring })}
          onClose={() => setRestoring(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setTried(true);
              if (reasonValid(reason)) restore.mutate(restoring);
            }}
          >
            <p>
              {t("programmes.revisions.restoreExplain", {
                n: restoring,
                next: programme.version + 1,
              })}
            </p>
            <ReasonField label={t("programmes.reason")} value={reason} onChange={setReason} showError={tried} />
            <MutationError error={restore.error} />
            <div className="actions">
              <button type="submit" className="btn btn--primary" disabled={restore.isPending}>
                {t("programmes.revisions.confirm")}
              </button>
            </div>
          </form>
        </InlineDialog>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- page

export function ProgrammeDetailPage() {
  const { id = "" } = useParams();
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const lang = useLanguage();
  const detail = useQuery({
    queryKey: programmeKeys.detail(id),
    queryFn: ({ signal }) => api.programme(id, signal),
  });
  const [filters, setFilters] = useState<PointFilters>({});
  const [action, setAction] = useState<Action | null>(null);
  const [editing, setEditing] = useState<ProgrammePoint | "new" | null>(null);
  const [following, setFollowing] = useState<ProgrammePoint | null>(null);
  const [bounds] = useState(() => initialBoundsFor(user?.identity.gouvernoratCode ?? null));
  const removePoint = useDetailWrite(id, (p: ProgrammePoint) => api.deleteProgrammePoint(id, p.id));
  const roles = user?.identity.roles ?? [];
  const room = roles.includes("operator") || roles.includes("ops_manager");
  const d = detail.data;
  const points = useMemo(() => (d ? filterPoints(d.points, filters) : []), [d, filters]);
  const pois = useMemo<MapPoi[]>(
    () =>
      points
        .filter((p) => p.lat !== null && p.lon !== null)
        .map((p) => ({
          id: p.id,
          lat: p.lat as number,
          lon: p.lon as number,
          kind: "place",
          title: p.place_name,
          subtitle: `${p.ref} · ${t(`programmes.pointStatus.${p.status}`)}`,
          iconPath: LAYER_ICON_PATHS.pin,
          colour: POINT_COLOURS[p.status],
          details: [p.hours, p.sub_points].filter((x): x is string => Boolean(x)),
        })),
    [points, t],
  );
  if (detail.isLoading) return <Loading />;
  if (detail.isError || !d) return <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />;
  const p = d.programme;
  const f = p.figures;
  const live = LIVE.includes(p.status);
  const gaps = totalGaps(p.declared, d.computed);
  const c = coverage(f.lifeguards_planned, f.lifeguards_deployed);
  const kpis: [string, string][] = [
    ["points", fmt.number(f.points)],
    ["open", fmt.number(f.open)],
    ["unlocated", fmt.number(f.unlocated)],
    ["gouvernorats", fmt.number(f.gouvernorats)],
    ["staff", fmt.number(f.staff)],
    [
      "coverage",
      c === null ? "—" : `${fmt.percent(c)} (${fmt.number(f.lifeguards_deployed)}/${fmt.number(f.lifeguards_planned)})`,
    ],
  ];
  return (
    <div className="page programme-page">
      <p>
        <Link to="/programmes">{t("programmes.back")}</Link>
      </p>
      <PageTitle icon="schedule" tone="orange">
        <span dir="auto">{p.title}</span>
      </PageTitle>
      <p>
        <span dir="ltr">
          {p.code} · v{p.version}
        </span>{" "}
        <ProgrammeStatusPill status={p.status} live={p.live} /> · {t(`programmes.kind.${p.kind}`)} ·{" "}
        {fmt.date(p.valid_from)} – {fmt.date(p.valid_to)}
        {p.season && ` · ${p.season}`}
      </p>
      <p className="muted">
        {p.approved_at
          ? t("programmes.approvedBy", {
              name: p.approved_by_name ?? "—",
              date: fmt.dateTime(p.approved_at),
            })
          : t("programmes.notApproved")}
        {p.source_document && ` · ${t("programmes.source", { source: p.source_document })}`}
        {p.layer_key && (
          <>
            {" · "}
            {t("programmes.layer")} <Link to="/layers">{p.layer_key}</Link>
          </>
        )}
      </p>
      {p.cancel_reason && (
        <p className="alert alert--warn" dir="auto">
          {t("programmes.cancelledBecause", { reason: p.cancel_reason })}
        </p>
      )}
      {p.status === "approved" && !p.live && <p className="alert alert--info">{t("programmes.waitingDates")}</p>}
      <dl className="kpis" aria-label={t("programmes.figures.label")}>
        {kpis.map(([k, v]) => (
          <div className="kpi" key={k}>
            <dt className="kpi__label">{t(`programmes.figures.${k}`)}</dt>
            <dd className="kpi__value">{v}</dd>
          </div>
        ))}
      </dl>
      {gaps.length > 0 && (
        <p className="alert alert--warn">
          {gaps
            .map(([k, stated, computed]) =>
              t("programmes.import.gap", {
                field: t(`programmes.totals.${k}`, { defaultValue: k }),
                stated: fmt.number(stated),
                computed: fmt.number(computed),
              }),
            )
            .join(t("common.listSeparator"))}
        </p>
      )}
      {p.can_edit && (
        <div className="actions">
          {p.status === "draft" && (
            <button type="button" className="btn btn--primary" onClick={() => setAction("approve")}>
              {t("programmes.action.approve.title")}
            </button>
          )}
          {(p.status === "draft" || live) && (
            <>
              <button type="button" className="btn" onClick={() => setAction("edit")}>
                {t("programmes.action.edit.title")}
              </button>
              <button type="button" className="btn" onClick={() => setEditing("new")}>
                {t("programmes.points.add")}
              </button>
            </>
          )}
          <button type="button" className="btn" onClick={() => setAction("copy")}>
            {t("programmes.action.copy.title")}
          </button>
          {live && (
            <button type="button" className="btn btn--danger" onClick={() => setAction("cancel")}>
              {t("programmes.action.cancel.title")}
            </button>
          )}
          {p.status === "draft" && (
            <button type="button" className="btn btn--danger" onClick={() => setAction("delete")}>
              {t("programmes.action.delete.title")}
            </button>
          )}
        </div>
      )}
      {action && <ActionDialog programme={p} action={action} onClose={() => setAction(null)} />}
      {editing && (
        <PointForm
          programme={p}
          point={editing === "new" ? null : editing}
          room={room}
          onClose={() => setEditing(null)}
        />
      )}
      {following && <FollowUp programme={p} point={following} onClose={() => setFollowing(null)} />}
      <MutationError error={removePoint.error} />
      <PointFiltersForm value={filters} onChange={setFilters} />
      <Suspense fallback={<Loading />}>
        <LazyMapView
          className="map programme-map"
          markers={[]}
          bounds={bounds}
          ariaLabel={t("programmes.points.map")}
          styleUrl={mapStyleUrl}
          dir={directionOf(lang)}
          pois={pois}
        />
      </Suspense>
      <ul className="coastal-legend" aria-label={t("programmes.points.legend")}>
        {POINT_STATUSES.map((s) => (
          <li key={s}>
            <span className="coastal-legend__dot" style={{ background: POINT_COLOURS[s] }} aria-hidden="true" />
            {t(`programmes.pointStatus.${s}`)}
          </li>
        ))}
      </ul>
      <PointsTable
        programme={p}
        points={points}
        room={room}
        onEdit={setEditing}
        onFollow={setFollowing}
        onDelete={(pt) => removePoint.mutate(pt)}
      />
      <Revisions programme={p} />
    </div>
  );
}
