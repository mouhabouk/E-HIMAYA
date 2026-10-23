import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyMapView } from "../components/LazyMap";
import { iconPathOf, LayerSwatch } from "../components/MapDataLayers";
import type { MapPoi } from "../components/MapView";
import { pointsBounds } from "../components/OrgBits";
import { RequiredNote } from "../components/PhaseASettings";
import { ReasonField } from "../components/Phase9Bits";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import {
  formatPhone,
  inTunisiaBox,
  keyFrom,
  LAYER_ICONS,
  validateLayer,
  type Change,
  type ImportMode,
  type LayerBody,
  type LayerFeature,
  type LayerImport,
  type LayerImportDetail,
  type MapLayer,
  type MapLayers,
} from "../lib/layers";
import { layerKeys, type Download } from "../lib/layersApi";
import { localized } from "../lib/localized";
import { TUNISIA_BOUNDS } from "../lib/mapStyle";
import { reasonValid } from "../lib/phase9";

const CHANGE_COLOURS: Record<Change, string> = {
  new: "#2E7D32",
  updated: "#1565C0",
  unchanged: "#37474F",
  removed: "#C62828",
};
const SHOWN_ROWS = 100;

function save(download: Download): void {
  const url = URL.createObjectURL(download.blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = download.filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

// ---------------------------------------------------------------- layer form

type Draft = Omit<LayerBody, "reason"> & { enabled: boolean };

function draftOf(layer: MapLayer | null, palette: readonly string[]): Draft {
  if (!layer) {
    return {
      key: "",
      name: { ar: "", fr: "", en: "" },
      icon: "pin",
      colour: palette[0] ?? "#37474F",
      audience: "staff",
      source: "",
      licence: "",
      to_verify: true,
      staff_only: ["manager"],
      editors_allowed: false,
      enabled: true,
    };
  }
  return {
    key: layer.key,
    name: { ...layer.name },
    icon: layer.icon,
    colour: layer.colour,
    audience: layer.audience,
    source: layer.source,
    licence: layer.licence,
    to_verify: layer.to_verify,
    staff_only: [...layer.staff_only],
    editors_allowed: layer.editors_allowed,
    enabled: layer.enabled,
  };
}

function LayerForm({
  layer,
  meta,
  onDone,
}: {
  layer: MapLayer | null;
  meta: MapLayers;
  onDone: (layer: MapLayer) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [draft, setDraft] = useState<Draft>(() => draftOf(layer, meta.palette));
  const [keyTouched, setKeyTouched] = useState(layer !== null);
  const [staffOnly, setStaffOnly] = useState(() => draft.staff_only.join(", "));
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [saved, setSaved] = useState(false);
  const problem = validateLayer(draft, meta.palette);

  const mutation = useMutation({
    mutationFn: () => {
      const staff_only = staffOnly
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const { key, enabled, ...rest } = draft;
      return layer
        ? api.updateLayer(layer.key, { ...rest, staff_only, enabled, version: layer.version, reason: reason.trim() })
        : api.createLayer({ ...rest, key, staff_only, reason: reason.trim() });
    },
    onSuccess: (updated) => {
      void qc.invalidateQueries({ queryKey: layerKeys.all });
      setReason("");
      setTried(false);
      setSaved(true);
      onDone(updated);
    },
  });

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    setSaved(false);
    if (problem || !reasonValid(reason)) return;
    mutation.mutate();
  };
  const setName = (lang: "ar" | "fr" | "en", value: string) => {
    const name = { ...draft.name, [lang]: value };
    setDraft({ ...draft, name, key: !keyTouched && lang === "fr" ? keyFrom(value) : draft.key });
  };

  return (
    <form noValidate onSubmit={submit} className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{layer ? t("layers.form.editTitle") : t("layers.form.newTitle")}</h2>
      <RequiredNote />
      <div className="settings-grid">
        {(["ar", "fr", "en"] as const).map((lang) => (
          <div className="field" key={lang}>
            <label htmlFor={`${id}-name-${lang}`}>{t(`layers.form.name_${lang}`)}</label>
            <input
              id={`${id}-name-${lang}`}
              lang={lang}
              dir={lang === "ar" ? "rtl" : "ltr"}
              aria-required="true"
              maxLength={100}
              value={draft.name[lang]}
              aria-invalid={tried && problem === "name" && draft.name[lang].trim() === "" ? true : undefined}
              onChange={(e) => setName(lang, e.target.value)}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${id}-key`}>{t("layers.form.key")}</label>
          <input
            id={`${id}-key`}
            dir="ltr"
            aria-required="true"
            disabled={layer !== null}
            value={draft.key}
            aria-describedby={`${id}-key-help`}
            aria-invalid={tried && problem === "key" ? true : undefined}
            onChange={(e) => {
              setKeyTouched(true);
              setDraft({ ...draft, key: e.target.value.trim() });
            }}
          />
          <p id={`${id}-key-help`} className="muted">
            {t("layers.form.keyHelp")}
          </p>
        </div>
        <div className="field">
          <label htmlFor={`${id}-audience`}>{t("layers.form.audience")}</label>
          <select
            id={`${id}-audience`}
            aria-required="true"
            value={draft.audience}
            onChange={(e) => setDraft({ ...draft, audience: e.target.value === "public" ? "public" : "staff" })}
          >
            <option value="staff">{t("layers.audience.staff")}</option>
            <option value="public">{t("layers.audience.public")}</option>
          </select>
        </div>
      </div>
      <fieldset className="layer-icons">
        <legend>{t("layers.form.icon")}</legend>
        {LAYER_ICONS.map((icon) => (
          <label key={icon} className="layer-choice">
            <input
              type="radio"
              name={`${id}-icon`}
              value={icon}
              checked={draft.icon === icon}
              onChange={() => setDraft({ ...draft, icon })}
            />
            <LayerSwatch layer={{ icon, colour: draft.colour }} />
            <span>{t(`layers.icons.${icon}`)}</span>
          </label>
        ))}
      </fieldset>
      <fieldset className="layer-colours">
        <legend>{t("layers.form.colour")}</legend>
        {meta.palette.map((colour, i) => (
          <label key={colour} className="layer-choice">
            <input
              type="radio"
              name={`${id}-colour`}
              value={colour}
              checked={draft.colour.toUpperCase() === colour}
              onChange={() => setDraft({ ...draft, colour })}
            />
            <span className="layer-swatch" style={{ background: colour }} aria-hidden="true" />
            <span className="visually-hidden">{t("layers.form.colourN", { n: i + 1, colour })}</span>
          </label>
        ))}
      </fieldset>
      <div className="settings-grid">
        <div className="field">
          <label htmlFor={`${id}-source`}>{t("layers.form.source")}</label>
          <input
            id={`${id}-source`}
            dir="auto"
            maxLength={200}
            placeholder="OpenStreetMap"
            value={draft.source}
            onChange={(e) => setDraft({ ...draft, source: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-licence`}>{t("layers.form.licence")}</label>
          <input
            id={`${id}-licence`}
            dir="auto"
            maxLength={200}
            placeholder="ODbL"
            value={draft.licence}
            onChange={(e) => setDraft({ ...draft, licence: e.target.value })}
          />
        </div>
        <div className="field">
          <label htmlFor={`${id}-staff-only`}>{t("layers.form.staffOnly")}</label>
          <input
            id={`${id}-staff-only`}
            dir="auto"
            value={staffOnly}
            aria-describedby={`${id}-staff-only-help`}
            onChange={(e) => setStaffOnly(e.target.value)}
          />
          <p id={`${id}-staff-only-help`} className="muted">
            {t("layers.form.staffOnlyHelp")}
          </p>
        </div>
      </div>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={draft.to_verify}
          onChange={(e) => setDraft({ ...draft, to_verify: e.target.checked })}
        />
        <span>{t("layers.form.toVerify")}</span>
      </label>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={draft.editors_allowed}
          onChange={(e) => setDraft({ ...draft, editors_allowed: e.target.checked })}
        />
        <span>{t("layers.form.editorsAllowed")}</span>
      </label>
      {layer && (
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
          />
          <span>{t("layers.form.enabled")}</span>
        </label>
      )}
      {tried && problem && (
        <p className="field__error" role="alert">
          {t(`layers.form.errors.${problem}`)}
        </p>
      )}
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
        {mutation.isPending ? t("aiSettings.saving") : layer ? t("aiSettings.save") : t("layers.form.create")}
      </button>
      <div role="status" aria-live="polite">
        {saved && !mutation.isPending && <p className="alert alert--ok">{t("aiSettings.saved")}</p>}
      </div>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </form>
  );
}

// ---------------------------------------------------------------- import

function Counts({ counts }: { counts: LayerImport["counts"] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const keys = ["new", "updated", "unchanged", "removed", "rejected", "warnings"] as const;
  return (
    <dl className="layer-counts">
      {keys.map((k) => (
        <div key={k} className={`layer-counts__item layer-counts__item--${k}`}>
          <dt>{t(`layers.import.counts.${k}`)}</dt>
          <dd>{fmt.number(counts[k] ?? 0)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ProblemTable({ detail }: { detail: LayerImport }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const rejectedTotal = detail.counts.rejected ?? detail.rejected.length;
  const warningsTotal = detail.counts.warnings ?? detail.warnings.length;
  return (
    <>
      {detail.rejected.length > 0 && (
        <section aria-label={t("layers.import.rejectedTitle")}>
          <h4>{t("layers.import.rejectedTitle")}</h4>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("layers.import.line")}</th>
                <th scope="col">{t("layers.places.name")}</th>
                <th scope="col">{t("layers.import.reason")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.rejected.slice(0, SHOWN_ROWS).map((r) => (
                <tr key={`${r.line}-${r.reason}`}>
                  <td className="num">{fmt.number(r.line)}</td>
                  <td dir="auto">{r.name ?? "—"}</td>
                  <td>{t(`layers.reasons.${r.reason}`, { defaultValue: r.reason })}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {rejectedTotal > SHOWN_ROWS && (
            <p className="muted">{t("layers.import.moreRows", { count: rejectedTotal - SHOWN_ROWS })}</p>
          )}
        </section>
      )}
      {detail.warnings.length > 0 && (
        <details>
          <summary>{t("layers.import.warningsTitle", { count: warningsTotal })}</summary>
          <ul>
            {detail.warnings.slice(0, SHOWN_ROWS).map((w) => (
              <li key={`${w.line}-${w.column}-${w.reason}`}>
                {t("layers.import.warningLine", {
                  line: fmt.number(w.line),
                  reason: t(`layers.reasons.${w.reason}`, { defaultValue: w.reason }),
                })}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function PreviewMap({ detail }: { detail: LayerImportDetail }) {
  const { t } = useTranslation();
  const { mapStyleUrl } = useServices();
  const lang = useLanguage();
  const pois = useMemo<MapPoi[]>(
    () =>
      detail.points
        .filter((p) => p.change !== "unchanged")
        .map((p) => ({
          id: `${p.change}:${p.ref}`,
          lon: p.lon,
          lat: p.lat,
          kind: "place",
          title: p.name,
          subtitle: t(`layers.changes.${p.change}`),
          colour: CHANGE_COLOURS[p.change],
          iconPath: iconPathOf("pin"),
        })),
    [detail.points, t],
  );
  if (pois.length === 0) return null;
  return (
    <Suspense fallback={<Loading />}>
      <LazyMapView
        className="map map--preview"
        markers={[]}
        bounds={pointsBounds(pois, 0.05) ?? TUNISIA_BOUNDS}
        ariaLabel={t("layers.import.mapLabel")}
        styleUrl={mapStyleUrl}
        dir={directionOf(lang)}
        pois={pois}
      />
    </Suspense>
  );
}

function ImportPanel({ layer, limits }: { layer: MapLayer; limits: MapLayers["limits"] }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<ImportMode>("merge");
  const [detail, setDetail] = useState<LayerImportDetail | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const tooLarge = file !== null && file.size > limits.file_bytes;

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: layerKeys.all });
    void qc.invalidateQueries({ queryKey: ["layers", layer.key] });
  };
  const preview = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("no file");
      return api.previewImport(layer.key, file, mode);
    },
    onSuccess: (d) => {
      setDetail(d);
      setDone(null);
      void qc.invalidateQueries({ queryKey: layerKeys.imports(layer.key) });
    },
  });
  const apply = useMutation({
    mutationFn: () => {
      if (!detail) throw new Error("no preview");
      return api.applyImport(layer.key, detail.id, reason.trim());
    },
    onSuccess: () => {
      setDone(t("layers.import.applied"));
      setDetail(null);
      setFile(null);
      setReason("");
      setTried(false);
      refresh();
    },
  });
  const discard = useMutation({
    mutationFn: () => {
      if (!detail) throw new Error("no preview");
      return api.discardImport(layer.key, detail.id);
    },
    onSuccess: () => {
      setDetail(null);
      refresh();
    },
  });

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.import.title")}</h3>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          if (file && !tooLarge) preview.mutate();
        }}
      >
        <div className="field">
          <label htmlFor={`${id}-file`}>{t("layers.import.file")}</label>
          <input
            id={`${id}-file`}
            type="file"
            accept=".csv,.txt,.xlsx,.json,.geojson"
            aria-required="true"
            aria-describedby={`${id}-file-help`}
            aria-invalid={tooLarge || undefined}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setDetail(null);
            }}
          />
          <p id={`${id}-file-help`} className="muted">
            {t("layers.import.fileHelp", {
              size: fmt.bytes(limits.file_bytes),
              rows: fmt.number(limits.rows),
            })}
          </p>
          {tooLarge && (
            <p className="field__error" role="alert">
              {t("errors.file_too_large")}
            </p>
          )}
        </div>
        <fieldset>
          <legend>{t("layers.import.mode")}</legend>
          {(["merge", "replace"] as const).map((m) => (
            <label key={m} className="radio">
              <input type="radio" name={`${id}-mode`} checked={mode === m} onChange={() => setMode(m)} />
              <span>
                <strong>{t(`layers.import.${m}`)}</strong> — {t(`layers.import.${m}Help`)}
              </span>
            </label>
          ))}
        </fieldset>
        <button type="submit" className="btn" disabled={!file || tooLarge || preview.isPending}>
          {preview.isPending ? t("layers.import.previewing") : t("layers.import.preview")}
        </button>
      </form>
      {preview.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(preview.error))}
        </p>
      )}
      <div role="status" aria-live="polite">
        {done && <p className="alert alert--ok">{done}</p>}
      </div>
      {detail && (
        <div className="layer-preview">
          <h4>{t("layers.import.previewTitle", { file: detail.file_name })}</h4>
          <Counts counts={detail.counts} />
          <PreviewMap detail={detail} />
          <ProblemTable detail={detail} />
          {detail.mode === "replace" && (detail.counts.removed ?? 0) > 0 && (
            <p className="alert alert--info">
              {t("layers.import.replaceWarning", { count: detail.counts.removed ?? 0 })}
            </p>
          )}
          <form
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              setTried(true);
              if (reasonValid(reason)) apply.mutate();
            }}
          >
            <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
            <div className="actions">
              <button type="submit" className="btn btn--primary" disabled={!detail.can_apply || apply.isPending}>
                {apply.isPending ? t("layers.import.applying") : t("layers.import.apply")}
              </button>
              <button
                type="button"
                className="btn"
                disabled={discard.isPending}
                onClick={() => discard.mutate()}
              >
                {t("layers.import.discard")}
              </button>
            </div>
          </form>
          {apply.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(apply.error))}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- history

function History({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const qc = useQueryClient();
  const id = useId();
  const [undoing, setUndoing] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const query = useQuery({
    queryKey: layerKeys.imports(layer.key),
    queryFn: ({ signal }) => api.layerImports(layer.key, signal),
  });
  const undo = useMutation({
    mutationFn: (importId: string) => api.undoImport(layer.key, importId, reason.trim()),
    onSuccess: () => {
      setUndoing(null);
      setReason("");
      setTried(false);
      void qc.invalidateQueries({ queryKey: layerKeys.all });
      void qc.invalidateQueries({ queryKey: ["layers", layer.key] });
    },
  });
  const items = (query.data ?? []).filter((j) => j.status !== "preview" || !j.expired);

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.history.title")}</h3>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("layers.history.empty")}</p>}
      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("layers.history.when")}</th>
              <th scope="col">{t("layers.history.file")}</th>
              <th scope="col">{t("layers.import.mode")}</th>
              <th scope="col">{t("layers.history.status")}</th>
              <th scope="col">{t("layers.history.counts")}</th>
              <th scope="col">{t("layers.history.by")}</th>
              <th scope="col">{t("layers.import.reason")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("layers.history.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id}>
                <td>
                  <time dateTime={j.applied_at ?? j.created_at}>{fmt.dateTime(j.applied_at ?? j.created_at)}</time>
                </td>
                <td dir="auto">{j.file_name}</td>
                <td>{t(`layers.import.${j.mode}`)}</td>
                <td>{t(`layers.history.statuses.${j.status}`)}</td>
                <td>
                  {t("layers.history.countsLine", {
                    new: fmt.number(j.counts.new ?? 0),
                    updated: fmt.number(j.counts.updated ?? 0),
                    removed: fmt.number(j.counts.removed ?? 0),
                    rejected: fmt.number(j.counts.rejected ?? 0),
                  })}
                </td>
                <td>{j.created_by_name ?? "—"}</td>
                <td dir="auto">{j.reason ?? "—"}</td>
                <td>
                  {j.can_undo && (
                    <button type="button" className="btn btn--small" onClick={() => setUndoing(j.id)}>
                      {t("layers.history.undo")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {undoing && (
        <form
          noValidate
          className="layer-undo"
          onSubmit={(e) => {
            e.preventDefault();
            setTried(true);
            if (reasonValid(reason)) undo.mutate(undoing);
          }}
        >
          <p>{t("layers.history.undoExplain")}</p>
          <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={undo.isPending}>
              {t("layers.history.undoConfirm")}
            </button>
            <button type="button" className="btn" onClick={() => setUndoing(null)}>
              {t("common.cancel")}
            </button>
          </div>
          {undo.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(undo.error))}
            </p>
          )}
        </form>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- places

function PlaceRow({ layer, feature }: { layer: MapLayer; feature: LayerFeature }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(feature.name);
  const [kind, setKind] = useState(feature.kind ?? "");
  const [phone, setPhone] = useState(feature.phone ?? "");
  const [hidden, setHidden] = useState(feature.hidden);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      api.updateFeature(layer.key, feature.id, {
        version: feature.version,
        reason: reason.trim(),
        name: name.trim(),
        kind: kind.trim() || null,
        phone: phone.trim() || null,
        hidden,
      }),
    onSuccess: () => {
      setEditing(false);
      setReason("");
      setTried(false);
      void qc.invalidateQueries({ queryKey: ["layers", layer.key] });
      void qc.invalidateQueries({ queryKey: layerKeys.all });
    },
  });

  return (
    <>
      <tr className={feature.hidden ? "row--muted" : undefined}>
        <td dir="auto">{feature.name}</td>
        <td dir="auto">{feature.kind ?? "—"}</td>
        <td dir="ltr">{feature.phone ? formatPhone(feature.phone) : "—"}</td>
        <td>{gouvernorats.nameOf(feature.gouvernorat_code) ?? "—"}</td>
        <td>{feature.hidden ? t("layers.places.hidden") : t("layers.places.visible")}</td>
        <td>
          {layer.can_import && (
            <button
              type="button"
              className="btn btn--small"
              aria-expanded={editing}
              aria-controls={`${id}-edit`}
              onClick={() => setEditing(!editing)}
            >
              {t("layers.places.edit")}
            </button>
          )}
        </td>
      </tr>
      {editing && (
        <tr id={`${id}-edit`}>
          <td colSpan={6}>
            <form
              noValidate
              onSubmit={(e) => {
                e.preventDefault();
                setTried(true);
                if (name.trim() && reasonValid(reason)) mutation.mutate();
              }}
            >
              <div className="settings-grid">
                <div className="field">
                  <label htmlFor={`${id}-name`}>{t("layers.places.name")}</label>
                  <input
                    id={`${id}-name`}
                    dir="auto"
                    aria-required="true"
                    maxLength={200}
                    value={name}
                    aria-invalid={tried && !name.trim() ? true : undefined}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor={`${id}-kind`}>{t("layers.places.type")}</label>
                  <input id={`${id}-kind`} dir="auto" maxLength={64} value={kind} onChange={(e) => setKind(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor={`${id}-phone`}>{t("layers.places.phone")}</label>
                  <input
                    id={`${id}-phone`}
                    dir="ltr"
                    inputMode="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
              </div>
              <label className="checkbox">
                <input type="checkbox" checked={hidden} onChange={(e) => setHidden(e.target.checked)} />
                <span>{t("layers.places.hide")}</span>
              </label>
              <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
              <div className="actions">
                <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
                  {t("aiSettings.save")}
                </button>
                <button type="button" className="btn" onClick={() => setEditing(false)}>
                  {t("common.cancel")}
                </button>
              </div>
              {mutation.isError && (
                <p className="alert alert--error" role="alert">
                  {t(errorMessageKey(mutation.error))}
                </p>
              )}
            </form>
          </td>
        </tr>
      )}
    </>
  );
}

function AddPlace({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [name, setName] = useState("");
  const [lat, setLat] = useState("");
  const [lon, setLon] = useState("");
  const [kind, setKind] = useState("");
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const latN = Number(lat.replace(",", "."));
  const lonN = Number(lon.replace(",", "."));
  const positionOk = lat !== "" && lon !== "" && inTunisiaBox(latN, lonN);
  const mutation = useMutation({
    mutationFn: () =>
      api.createFeature(layer.key, {
        name: name.trim(),
        lat: latN,
        lon: lonN,
        kind: kind.trim() || null,
        phone: phone.trim() || null,
        reason: reason.trim(),
      }),
    onSuccess: () => {
      setName("");
      setLat("");
      setLon("");
      setKind("");
      setPhone("");
      setReason("");
      setTried(false);
      void qc.invalidateQueries({ queryKey: ["layers", layer.key] });
      void qc.invalidateQueries({ queryKey: layerKeys.all });
    },
  });
  return (
    <details className="layer-add">
      <summary>{t("layers.places.add")}</summary>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setTried(true);
          if (name.trim() && positionOk && reasonValid(reason)) mutation.mutate();
        }}
      >
        <RequiredNote />
        <div className="settings-grid">
          <div className="field">
            <label htmlFor={`${id}-name`}>{t("layers.places.name")}</label>
            <input
              id={`${id}-name`}
              dir="auto"
              aria-required="true"
              maxLength={200}
              value={name}
              aria-invalid={tried && !name.trim() ? true : undefined}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-lat`}>{t("layers.places.lat")}</label>
            <input
              id={`${id}-lat`}
              dir="ltr"
              inputMode="decimal"
              aria-required="true"
              placeholder="36.8065"
              value={lat}
              aria-invalid={tried && !positionOk ? true : undefined}
              onChange={(e) => setLat(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-lon`}>{t("layers.places.lon")}</label>
            <input
              id={`${id}-lon`}
              dir="ltr"
              inputMode="decimal"
              aria-required="true"
              placeholder="10.1815"
              value={lon}
              aria-invalid={tried && !positionOk ? true : undefined}
              onChange={(e) => setLon(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor={`${id}-kind`}>{t("layers.places.type")}</label>
            <input id={`${id}-kind`} dir="auto" maxLength={64} value={kind} onChange={(e) => setKind(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-phone`}>{t("layers.places.phone")}</label>
            <input id={`${id}-phone`} dir="ltr" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
          </div>
        </div>
        {tried && !positionOk && (
          <p className="field__error" role="alert">
            {t("layers.reasons.outside_tunisia")}
          </p>
        )}
        <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {t("layers.places.addConfirm")}
        </button>
        {mutation.isError && (
          <p className="alert alert--error" role="alert">
            {t(errorMessageKey(mutation.error))}
          </p>
        )}
      </form>
    </details>
  );
}

function Places({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const id = useId();
  const [filter, setFilter] = useState("");
  const query = useQuery({
    queryKey: layerKeys.features(layer.key, null),
    queryFn: ({ signal }) => api.layerFeatures(layer.key, null, signal),
  });
  const needle = filter.trim().toLowerCase();
  const items = (query.data?.items ?? []).filter(
    (f) => !needle || f.name.toLowerCase().includes(needle) || (f.kind ?? "").toLowerCase().includes(needle),
  );
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.places.title", { count: layer.feature_count })}</h3>
      {layer.can_import && <AddPlace layer={layer} />}
      <div className="field">
        <label htmlFor={`${id}-filter`}>{t("layers.places.filter")}</label>
        <input id={`${id}-filter`} type="search" dir="auto" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </div>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("layers.places.empty")}</p>}
      {items.length > 0 && (
        <>
          <p className="muted" role="status">
            {t("layers.places.count", { shown: fmt.number(Math.min(items.length, SHOWN_ROWS)), total: fmt.number(items.length) })}
          </p>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("layers.places.name")}</th>
                <th scope="col">{t("layers.places.type")}</th>
                <th scope="col">{t("layers.places.phone")}</th>
                <th scope="col">{t("layers.places.gouvernorat")}</th>
                <th scope="col">{t("layers.places.state")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("layers.history.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, SHOWN_ROWS).map((f) => (
                <PlaceRow key={`${f.id}-${f.version}`} layer={layer} feature={f} />
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- page

function ExportButtons({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const download = useMutation({
    mutationFn: (format: "csv" | "xlsx" | "geojson") => api.exportLayer(layer.key, format, lang),
    onSuccess: save,
  });
  return (
    <div className="actions" role="group" aria-label={t("layers.export.title")}>
      {(["csv", "xlsx", "geojson"] as const).map((format) => (
        <button
          key={format}
          type="button"
          className="btn btn--small"
          disabled={download.isPending}
          onClick={() => download.mutate(format)}
        >
          {t(`layers.export.${format}`)}
        </button>
      ))}
      {download.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(download.error))}
        </p>
      )}
    </div>
  );
}

function LayerDetail({ layer, meta }: { layer: MapLayer; meta: MapLayers }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  return (
    <section className="layer-detail" aria-label={localized(layer.name, lang)}>
      <h2 dir="auto">
        <LayerSwatch layer={layer} /> {localized(layer.name, lang)}
      </h2>
      <p className="muted">
        {[layer.source, layer.licence].filter(Boolean).join(" · ") || t("layers.list.noSource")}
        {layer.to_verify && <span className="chip chip--to-verify">{t("layers.toVerify")}</span>}
      </p>
      <ExportButtons layer={layer} />
      {layer.can_manage && <LayerForm key={`${layer.key}-${layer.version}`} layer={layer} meta={meta} onDone={() => undefined} />}
      {layer.can_import && <ImportPanel layer={layer} limits={meta.limits} />}
      <History layer={layer} />
      <Places layer={layer} />
    </section>
  );
}

function TemplateLinks() {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const download = useMutation({
    mutationFn: (format: "csv" | "xlsx") => api.layerTemplate(format, lang),
    onSuccess: save,
  });
  return (
    <div className="actions">
      <span>{t("layers.template.title")}</span>
      {(["csv", "xlsx"] as const).map((format) => (
        <button key={format} type="button" className="btn btn--small" onClick={() => download.mutate(format)}>
          {t(`layers.export.${format}`)}
        </button>
      ))}
    </div>
  );
}

/** Map data layers (phase B1, docs/phase-b/design.md §2.3): create, import, check, publish, undo, export. */
export function LayersPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const lang = useLanguage();
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) });
  const meta = query.data;
  const layers = meta?.items ?? [];
  const current = layers.find((l) => l.key === selected) ?? null;

  return (
    <div className="page">
      <div className="page__head">
        <h1>{t("layers.title")}</h1>
        <p className="muted">{t("layers.intro")}</p>
      </div>
      <TemplateLinks />
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {meta && (
        <>
          {meta.can_manage && (
            <button type="button" className="btn" aria-expanded={creating} onClick={() => setCreating(!creating)}>
              {t("layers.form.newTitle")}
            </button>
          )}
          {creating && (
            <LayerForm
              layer={null}
              meta={meta}
              onDone={(l) => {
                setCreating(false);
                setSelected(l.key);
              }}
            />
          )}
          {layers.length === 0 ? (
            <p className="muted">{t("layers.list.empty")}</p>
          ) : (
            <table className="table">
              <caption className="visually-hidden">{t("layers.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("layers.list.name")}</th>
                  <th scope="col">{t("layers.form.audience")}</th>
                  <th scope="col">{t("layers.list.places")}</th>
                  <th scope="col">{t("layers.list.lastImport")}</th>
                  <th scope="col">{t("layers.list.state")}</th>
                  <th scope="col">
                    <span className="visually-hidden">{t("layers.history.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {layers.map((l) => (
                  <tr key={l.key} aria-current={l.key === selected ? "true" : undefined}>
                    <td>
                      <LayerSwatch layer={l} /> <span dir="auto">{localized(l.name, lang)}</span>
                      {l.to_verify && <span className="chip chip--to-verify">{t("layers.toVerify")}</span>}
                    </td>
                    <td>{t(`layers.audience.${l.audience}`)}</td>
                    <td className="num">
                      {fmt.number(l.feature_count)}
                      {l.hidden_count > 0 && ` (${t("layers.list.hiddenCount", { count: l.hidden_count })})`}
                    </td>
                    <td>
                      {l.last_import ? (
                        <time dateTime={l.last_import.at}>{fmt.dateTime(l.last_import.at)}</time>
                      ) : (
                        t("layers.list.none")
                      )}
                    </td>
                    <td>{l.enabled ? t("layers.list.enabled") : t("layers.list.disabled")}</td>
                    <td>
                      <button type="button" className="btn btn--small" onClick={() => setSelected(l.key)}>
                        {t("layers.list.open")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {current && <LayerDetail key={current.key} layer={current} meta={meta} />}
        </>
      )}
    </div>
  );
}
