import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import {
  CARD_FIELDS,
  CONFIDENCES,
  DELETE_REASONS,
  deleteReason,
  GROUPS,
  LAYER_STATUSES,
  STAFF_GROUPS,
  type Confidence,
  type Group,
  type LayerAccess,
  type LayerFeature,
  type LayerStatus,
  type MapLayer,
} from "../lib/layers";
import { layerKeys } from "../lib/layersApi";
import { localized } from "../lib/localized";
import { reasonValid } from "../lib/phase9";
import { useServices } from "../context/services";
import { ErrorBox, Loading } from "./Feedback";
import { Pill } from "./Icon";
import { ReasonField } from "./Phase9Bits";

/**
 * Managing a map layer (phase L1a, docs/phase-l/design-layers.md §3.3–3.6 and §3.10): state, who sees it, columns by
 * audience, settings revisions, review of suggested names and duplicates, deleting and restoring layers and places.
 * The API is the judge: what an audience may not see never leaves it; these screens only set it.
 */

const STATUS_TONE: Record<LayerStatus, "slate" | "green" | "amber"> = {
  draft: "slate",
  published: "green",
  paused: "amber",
};

function ErrorLine({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return (
    <p className="alert alert--error" role="alert">
      {t(errorMessageKey(error))}
    </p>
  );
}

function useRefresh(key: string) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: layerKeys.all });
    void qc.invalidateQueries({ queryKey: ["layers", key] });
  };
}

/** Status, sensitive and quality badges of a layer (list and detail). */
export function LayerBadges({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <span className="layer-badges">
      {layer.deleted_at ? (
        <Pill tone="red">{t("layers.manage.status.deleted")}</Pill>
      ) : (
        <Pill tone={STATUS_TONE[layer.status]}>{t(`layers.manage.status.${layer.status}`)}</Pill>
      )}
      {layer.sensitive && <Pill tone="purple">{t("layers.manage.sensitive")}</Pill>}
      {layer.quality.suggested > 0 && (
        <Pill tone="navy">{t("layers.manage.toReview", { n: fmt.number(layer.quality.suggested) })}</Pill>
      )}
      {layer.quality.duplicates > 0 && (
        <Pill tone="orange">
          {t("layers.manage.duplicates", { n: fmt.number(layer.quality.duplicates) })}
        </Pill>
      )}
    </span>
  );
}

// ---------------------------------------------------------------- who sees it (§3.3)

function accessOf(layer: MapLayer): LayerAccess {
  return {
    status: layer.status,
    audiences: [...layer.audiences],
    scope: [...layer.scope],
    default_on: layer.default_on,
    sensitive: layer.sensitive,
    fields: Object.fromEntries(Object.entries(layer.fields).map(([k, v]) => [k, [...v]])),
    actions: { ...layer.actions },
  };
}

function SaveBar({
  pending,
  error,
  saved,
  reason,
  setReason,
  tried,
  label,
}: {
  pending: boolean;
  error: unknown;
  saved: boolean;
  reason: string;
  setReason: (v: string) => void;
  tried: boolean;
  label: string;
}) {
  const { t } = useTranslation();
  return (
    <>
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={pending}>
        {pending ? t("aiSettings.saving") : label}
      </button>
      <div role="status" aria-live="polite">
        {saved && !pending && <p className="alert alert--ok">{t("aiSettings.saved")}</p>}
      </div>
      {error !== null && error !== undefined && <ErrorLine error={error} />}
    </>
  );
}

function useAccessSave(layer: MapLayer) {
  const { api } = useServices();
  const refresh = useRefresh(layer.key);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: (changes: Partial<LayerAccess> & { group_key?: string }) =>
      api.updateLayer(layer.key, { ...changes, version: layer.version, reason: reason.trim() }),
    onSuccess: () => {
      setReason("");
      setTried(false);
      setSaved(true);
      refresh();
    },
  });
  const submit = (changes: Partial<LayerAccess> & { group_key?: string }) => {
    setTried(true);
    setSaved(false);
    if (reasonValid(reason)) mutation.mutate(changes);
  };
  return { reason, setReason, tried, saved, mutation, submit };
}

export function VisibilityCard({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const gouvernorats = useGouvernorats();
  const id = useId();
  const [draft, setDraft] = useState<LayerAccess>(() => accessOf(layer));
  const save = useAccessSave(layer);
  const { api } = useServices();
  const lang = useLanguage();
  // Phase UI-3b: the folder it shows in on the map; a sensitive layer stays in the sensitive folder.
  const groups = useQuery({ queryKey: layerKeys.all, queryFn: ({ signal }) => api.layers(signal) }).data?.groups ?? [];
  const [folder, setFolder] = useState(layer.group ?? "");
  const folders = groups.filter((g) => !g.sensitive);
  const toggle = (group: Group) =>
    setDraft({
      ...draft,
      audiences: draft.audiences.includes(group) ? draft.audiences.filter((a) => a !== group) : [...draft.audiences, group],
    });
  const toggleScope = (code: number) =>
    setDraft({
      ...draft,
      scope: draft.scope.includes(code) ? draft.scope.filter((c) => c !== code) : [...draft.scope, code].sort((a, b) => a - b),
    });
  const { fields: _fields, ...changes } = draft;

  return (
    <form
      noValidate
      className="card"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        const moved = !draft.sensitive && !layer.sensitive && folder !== "" && folder !== layer.group;
        save.submit(moved ? { ...changes, group_key: folder } : changes);
      }}
    >
      <h3 id={`${id}-title`}>{t("layers.manage.visibility.title")}</h3>
      <fieldset className="segmented">
        <legend>{t("layers.manage.visibility.status")}</legend>
        {LAYER_STATUSES.map((s) => (
          <label key={s} className="segmented__item">
            <input
              type="radio"
              name={`${id}-status`}
              checked={draft.status === s}
              onChange={() => setDraft({ ...draft, status: s })}
            />
            <span>{t(`layers.manage.status.${s}`)}</span>
          </label>
        ))}
      </fieldset>
      <p className="muted">{t(`layers.manage.visibility.statusHelp.${draft.status}`)}</p>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={draft.sensitive}
          onChange={(e) => setDraft({ ...draft, sensitive: e.target.checked })}
        />
        <span>{t("layers.manage.visibility.sensitive")}</span>
      </label>
      {draft.sensitive && <p className="alert alert--info">{t("layers.manage.visibility.sensitiveHelp")}</p>}

      <fieldset className="layer-groups" disabled={draft.sensitive}>
        <legend>{t("layers.manage.visibility.audiences")}</legend>
        {GROUPS.map((g) => (
          <label key={g} className="chip-toggle">
            <input type="checkbox" checked={draft.audiences.includes(g)} onChange={() => toggle(g)} />
            <span>{t(`layers.manage.groups.${g}`)}</span>
          </label>
        ))}
        <p className="muted">{t("layers.manage.visibility.audiencesHelp")}</p>
      </fieldset>

      <details className="layer-scope">
        <summary>
          {draft.scope.length === 0
            ? t("layers.manage.visibility.national")
            : t("layers.manage.visibility.scopeCount", { count: draft.scope.length })}
        </summary>
        <p className="muted">{t("layers.manage.visibility.scopeHelp")}</p>
        <fieldset className="layer-groups">
          <legend className="visually-hidden">{t("layers.manage.visibility.scope")}</legend>
          {gouvernorats.list.map((g) => (
            <label key={g.code} className="chip-toggle">
              <input type="checkbox" checked={draft.scope.includes(g.code)} onChange={() => toggleScope(g.code)} />
              <span>{gouvernorats.nameOf(g.code)}</span>
            </label>
          ))}
        </fieldset>
      </details>

      {folders.length > 0 && (
        <div className="field layer-folder-pick">
          <label htmlFor={`${id}-folder`}>{t("layers.groups.pick")}</label>
          <select
            id={`${id}-folder`}
            value={draft.sensitive || layer.sensitive ? "" : folder}
            disabled={draft.sensitive || layer.sensitive}
            aria-describedby={`${id}-folder-help`}
            onChange={(e) => setFolder(e.target.value)}
          >
            {(draft.sensitive || layer.sensitive) && <option value="">{t("layers.groups.pickSensitive")}</option>}
            {folders.map((g) => (
              <option key={g.key} value={g.key}>
                {localized(g.name, lang)}
              </option>
            ))}
          </select>
          <p id={`${id}-folder-help`} className="muted">
            {t("layers.groups.pickHelp")}
          </p>
        </div>
      )}

      <label className="checkbox">
        <input
          type="checkbox"
          checked={draft.default_on}
          onChange={(e) => setDraft({ ...draft, default_on: e.target.checked })}
        />
        <span>{t("layers.manage.visibility.defaultOn")}</span>
      </label>
      <fieldset>
        <legend>{t("layers.manage.visibility.actions")}</legend>
        {(["call", "directions"] as const).map((a) => (
          <label key={a} className="checkbox">
            <input
              type="checkbox"
              checked={draft.actions[a]}
              onChange={(e) => setDraft({ ...draft, actions: { ...draft.actions, [a]: e.target.checked } })}
            />
            <span>{t(`layers.manage.visibility.action_${a}`)}</span>
          </label>
        ))}
      </fieldset>
      <SaveBar
        pending={save.mutation.isPending}
        error={save.mutation.error}
        saved={save.saved}
        reason={save.reason}
        setReason={save.setReason}
        tried={save.tried}
        label={t("aiSettings.save")}
      />
    </form>
  );
}

// ---------------------------------------------------------------- columns by audience (§3.4)

export function FieldsCard({ layer, columns }: { layer: MapLayer; columns: string[] }) {
  const { t } = useTranslation();
  const id = useId();
  const [fields, setFields] = useState<Record<string, Group[]>>(() => accessOf(layer).fields);
  const [extra, setExtra] = useState("");
  const save = useAccessSave(layer);
  const groups = layer.sensitive ? STAFF_GROUPS : GROUPS.filter((g) => layer.audiences.includes(g));
  const names = [...new Set([...CARD_FIELDS, ...columns, ...Object.keys(fields)])];
  const allowed = (column: string, g: Group) => (fields[column] ?? groups).includes(g);
  const toggle = (column: string, g: Group) => {
    const current = fields[column] ?? [...groups];
    const next = current.includes(g) ? current.filter((x) => x !== g) : [...current, g];
    // A column every audience of the layer sees is left out of the map (the default).
    const rest = Object.fromEntries(Object.entries(fields).filter(([k]) => k !== column));
    setFields(groups.every((x) => next.includes(x)) ? rest : { ...rest, [column]: next });
  };

  return (
    <form
      noValidate
      className="card"
      aria-labelledby={`${id}-title`}
      onSubmit={(e) => {
        e.preventDefault();
        save.submit({ fields });
      }}
    >
      <h3 id={`${id}-title`}>{t("layers.manage.fields.title")}</h3>
      <p className="muted">{t("layers.manage.fields.help")}</p>
      <div className="table-wrap">
        <table className="table layer-fields">
          <thead>
            <tr>
              <th scope="col">{t("layers.manage.fields.column")}</th>
              {groups.map((g) => (
                <th scope="col" key={g}>
                  {t(`layers.manage.groups.${g}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {names.map((column) => (
              <tr key={column}>
                <th scope="row" dir="auto">
                  {t(`layers.columns.${column}`, { defaultValue: column })}
                </th>
                {groups.map((g) => (
                  <td key={g}>
                    <input
                      type="checkbox"
                      checked={allowed(column, g)}
                      aria-label={t("layers.manage.fields.cell", {
                        column: t(`layers.columns.${column}`, { defaultValue: column }),
                        group: t(`layers.manage.groups.${g}`),
                      })}
                      onChange={() => toggle(column, g)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="field">
        <label htmlFor={`${id}-extra`}>{t("layers.manage.fields.add")}</label>
        <div className="actions">
          <input id={`${id}-extra`} dir="auto" maxLength={64} value={extra} onChange={(e) => setExtra(e.target.value)} />
          <button
            type="button"
            className="btn btn--small"
            disabled={!extra.trim()}
            onClick={() => {
              setFields({ ...fields, [extra.trim()]: groups.filter((g) => g !== "citizen") });
              setExtra("");
            }}
          >
            {t("layers.manage.fields.addButton")}
          </button>
        </div>
      </div>
      <SaveBar
        pending={save.mutation.isPending}
        error={save.mutation.error}
        saved={save.saved}
        reason={save.reason}
        setReason={save.setReason}
        tried={save.tried}
        label={t("aiSettings.save")}
      />
    </form>
  );
}

// ---------------------------------------------------------------- revisions (§3.5)

export function RevisionsCard({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefresh(layer.key);
  const id = useId();
  const [restoring, setRestoring] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const query = useQuery({
    queryKey: layerKeys.revisions(layer.key),
    queryFn: ({ signal }) => api.layerRevisions(layer.key, signal),
  });
  const restore = useMutation({
    mutationFn: (n: number) => api.restoreRevision(layer.key, n, reason.trim()),
    onSuccess: () => {
      setRestoring(null);
      setReason("");
      setTried(false);
      refresh();
    },
  });
  const items = query.data ?? [];
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.manage.revisions.title")}</h3>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {items.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t("layers.manage.revisions.number")}</th>
              <th scope="col">{t("layers.history.when")}</th>
              <th scope="col">{t("layers.manage.revisions.action")}</th>
              <th scope="col">{t("layers.manage.revisions.changes")}</th>
              <th scope="col">{t("layers.history.by")}</th>
              <th scope="col">{t("layers.import.reason")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("layers.history.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((r, i) => (
              <tr key={r.number}>
                <td className="num">{fmt.number(r.number)}</td>
                <td>
                  <time dateTime={r.created_at}>{fmt.dateTime(r.created_at)}</time>
                </td>
                <td>
                  {r.action.startsWith("restore:")
                    ? `${t("layers.manage.revisions.actions.revert")} ${fmt.number(Number(r.action.slice(8)))}`
                    : t(`layers.manage.revisions.actions.${r.action}`, { defaultValue: r.action })}
                </td>
                <td>{r.changes.map((c) => t(`layers.manage.revisions.fields.${c}`, { defaultValue: c })).join("، ") || "—"}</td>
                <td>{r.created_by_name ?? "—"}</td>
                <td dir="auto">{r.reason ?? "—"}</td>
                <td>
                  {i > 0 && !layer.deleted_at && (
                    <button type="button" className="btn btn--small" onClick={() => setRestoring(r.number)}>
                      {t("layers.manage.revisions.restore")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {restoring !== null && (
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setTried(true);
            if (reasonValid(reason)) restore.mutate(restoring);
          }}
        >
          <p>{t("layers.manage.revisions.explain", { n: fmt.number(restoring) })}</p>
          <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
          <div className="actions">
            <button type="submit" className="btn btn--primary" disabled={restore.isPending}>
              {t("layers.manage.revisions.confirm")}
            </button>
            <button type="button" className="btn" onClick={() => setRestoring(null)}>
              {t("common.cancel")}
            </button>
          </div>
          {restore.isError && <ErrorLine error={restore.error} />}
        </form>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- deleting (§3.5, §3.10)

/** Reason chips («duplicate», «invalid», «replaced», «other») and the words; returns the reason to send or null. */
function DeleteReason({
  chip,
  setChip,
  words,
  setWords,
  tried,
}: {
  chip: (typeof DELETE_REASONS)[number] | null;
  setChip: (c: (typeof DELETE_REASONS)[number]) => void;
  words: string;
  setWords: (v: string) => void;
  tried: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  return (
    <>
      <fieldset className="layer-groups">
        <legend>{t("layers.manage.delete.why")}</legend>
        {DELETE_REASONS.map((r) => (
          <label key={r} className="chip-toggle">
            <input type="radio" name={`${id}-why`} checked={chip === r} onChange={() => setChip(r)} />
            <span>{t(`layers.manage.delete.reasons.${r}`)}</span>
          </label>
        ))}
      </fieldset>
      {tried && chip === null && (
        <p className="field__error" role="alert">
          {t("layers.manage.delete.pick")}
        </p>
      )}
      {chip !== null && (
        <ReasonField
          label={chip === "other" ? t("layers.reasonLabel") : t("layers.manage.delete.more")}
          value={words}
          onChange={setWords}
          showError={tried && chip === "other"}
        />
      )}
    </>
  );
}

function useDeleteReason() {
  const { t } = useTranslation();
  const [chip, setChip] = useState<(typeof DELETE_REASONS)[number] | null>(null);
  const [words, setWords] = useState("");
  const reason = deleteReason(chip, words, (k) => t(`layers.manage.delete.reasons.${k}`));
  const ok = chip !== null && reasonValid(reason);
  return { chip, setChip, words, setWords, reason, ok };
}

export function DeleteLayerCard({ layer, onDeleted }: { layer: MapLayer; onDeleted: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const lang = useLanguage();
  const refresh = useRefresh(layer.key);
  const id = useId();
  const [open, setOpen] = useState(false);
  const [tried, setTried] = useState(false);
  const why = useDeleteReason();
  const mutation = useMutation({
    mutationFn: () => api.deleteLayer(layer.key, why.reason),
    onSuccess: () => {
      refresh();
      onDeleted();
    },
  });
  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.manage.delete.title")}</h3>
      <p className="muted">{t("layers.manage.delete.explain")}</p>
      {!open ? (
        <button type="button" className="btn btn--danger" onClick={() => setOpen(true)}>
          {t("layers.manage.delete.button")}
        </button>
      ) : (
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            setTried(true);
            if (why.ok) mutation.mutate();
          }}
        >
          <DeleteReason {...why} tried={tried} />
          <div className="actions">
            <button type="submit" className="btn btn--danger" disabled={mutation.isPending}>
              {t("layers.manage.delete.confirm", { name: localized(layer.name, lang) })}
            </button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>
              {t("common.cancel")}
            </button>
          </div>
          {mutation.isError && <ErrorLine error={mutation.error} />}
        </form>
      )}
    </section>
  );
}

/** The administrator's "deleted" tab: restore as it was (paused), or erase now with a second confirmation. */
export function DeletedLayers({ items }: { items: MapLayer[] }) {
  const { t } = useTranslation();
  const lang = useLanguage();
  const fmt = useFormat();
  if (items.length === 0) return <p className="muted">{t("layers.manage.deleted.empty")}</p>;
  return (
    <table className="table">
      <caption className="visually-hidden">{t("layers.manage.deleted.title")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("layers.list.name")}</th>
          <th scope="col">{t("layers.manage.deleted.when")}</th>
          <th scope="col">{t("layers.import.reason")}</th>
          <th scope="col">{t("layers.manage.deleted.purgeAt")}</th>
          <th scope="col">
            <span className="visually-hidden">{t("layers.history.actions")}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {items.map((l) => (
          <tr key={l.key}>
            <td dir="auto">{localized(l.name, lang)}</td>
            <td>{l.deleted_at && <time dateTime={l.deleted_at}>{fmt.dateTime(l.deleted_at)}</time>}</td>
            <td dir="auto">{l.delete_reason ?? "—"}</td>
            <td>{l.purge_at && <time dateTime={l.purge_at}>{fmt.date(l.purge_at)}</time>}</td>
            <td>
              <DeletedActions layer={l} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DeletedActions({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh(layer.key);
  const [mode, setMode] = useState<"restore" | "purge" | null>(null);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [sure, setSure] = useState(false);
  const mutation = useMutation({
    mutationFn: () =>
      mode === "purge" ? api.purgeLayer(layer.key, reason.trim()) : api.restoreLayer(layer.key, reason.trim()),
    onSuccess: () => {
      setMode(null);
      refresh();
    },
  });
  if (mode === null) {
    return (
      <div className="actions">
        <button type="button" className="btn btn--small" onClick={() => setMode("restore")}>
          {t("layers.manage.deleted.restore")}
        </button>
        <button type="button" className="btn btn--small btn--danger" onClick={() => setMode("purge")}>
          {t("layers.manage.deleted.purge")}
        </button>
      </div>
    );
  }
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (reasonValid(reason) && (mode === "restore" || sure)) mutation.mutate();
      }}
    >
      {mode === "purge" && (
        <label className="checkbox">
          <input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
          <span>{t("layers.manage.deleted.purgeSure")}</span>
        </label>
      )}
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      <div className="actions">
        <button
          type="submit"
          className={mode === "purge" ? "btn btn--danger" : "btn btn--primary"}
          disabled={mutation.isPending || (mode === "purge" && !sure)}
        >
          {t(`layers.manage.deleted.${mode}Confirm`)}
        </button>
        <button type="button" className="btn" onClick={() => setMode(null)}>
          {t("common.cancel")}
        </button>
      </div>
      {mutation.isError && <ErrorLine error={mutation.error} />}
    </form>
  );
}

/** Deleting one place from its row: the reason chips, then it leaves every map. */
export function DeletePlace({ layer, feature, onDone }: { layer: MapLayer; feature: LayerFeature; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh(layer.key);
  const [tried, setTried] = useState(false);
  const why = useDeleteReason();
  const mutation = useMutation({
    mutationFn: () => api.deleteFeature(layer.key, feature.id, why.reason),
    onSuccess: () => {
      refresh();
      onDone();
    },
  });
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (why.ok) mutation.mutate();
      }}
    >
      <DeleteReason {...why} tried={tried} />
      <div className="actions">
        <button type="submit" className="btn btn--danger" disabled={mutation.isPending}>
          {t("layers.manage.delete.placeConfirm")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
      {mutation.isError && <ErrorLine error={mutation.error} />}
    </form>
  );
}

export function DeletedPlaces({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const refresh = useRefresh(layer.key);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const query = useQuery({
    queryKey: layerKeys.deletedFeatures(layer.key),
    queryFn: ({ signal }) => api.deletedFeatures(layer.key, signal),
  });
  const restore = useMutation({
    mutationFn: (id: string) => api.restoreFeature(layer.key, id, reason.trim()),
    onSuccess: () => {
      setReason("");
      setTried(false);
      refresh();
    },
  });
  const items = query.data?.items ?? [];
  return (
    <details className="layer-deleted-places">
      <summary>{t("layers.manage.deletedPlaces.title", { count: layer.quality.deleted })}</summary>
      {query.isLoading && <Loading />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("layers.manage.deletedPlaces.empty")}</p>}
      {items.length > 0 && (
        <>
          <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
          <ul className="layer-deleted-list">
            {items.map((f) => (
              <li key={f.id}>
                <span dir="auto">{f.name}</span>
                <span className="muted">
                  {f.deleted_at && fmt.dateTime(f.deleted_at)} · <span dir="auto">{f.delete_reason ?? "—"}</span>
                </span>
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={restore.isPending}
                  onClick={() => {
                    setTried(true);
                    if (reasonValid(reason)) restore.mutate(f.id);
                  }}
                >
                  {t("layers.manage.deletedPlaces.restore")}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {restore.isError && <ErrorLine error={restore.error} />}
    </details>
  );
}

// ---------------------------------------------------------------- names review (§3.6)

type View = { kind: "names"; confidence: Confidence | null } | { kind: "duplicates" };

export function ReviewCard({ layer }: { layer: MapLayer }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const refresh = useRefresh(layer.key);
  const qc = useQueryClient();
  const id = useId();
  const [view, setView] = useState<View>({ kind: "names", confidence: null });
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const viewKey = view.kind === "duplicates" ? "duplicates" : (view.confidence ?? "all");
  const query = useQuery({
    queryKey: layerKeys.review(layer.key, viewKey),
    queryFn: ({ signal }) =>
      api.reviewQueue(
        layer.key,
        view.kind === "duplicates" ? { duplicates: true } : { confidence: view.confidence ?? undefined },
        signal,
      ),
  });
  const mutation = useMutation({
    mutationFn: (body: Parameters<typeof api.review>[1]) => api.review(layer.key, body),
    onSuccess: (r) => {
      setDone(t("layers.manage.review.done", { ...r }));
      setEdits({});
      setTried(false);
      void qc.invalidateQueries({ queryKey: ["layers", layer.key, "review"] });
      refresh();
    },
  });
  const send = (body: Omit<Parameters<typeof api.review>[1], "reason">) => {
    setTried(true);
    setDone(null);
    if (reasonValid(reason)) mutation.mutate({ ...body, reason: reason.trim() });
  };
  const counts = query.data?.counts ?? {};
  const items = query.data?.items ?? [];

  const row = (f: LayerFeature, actions: ReactNode) => (
    <tr key={f.id}>
      <td dir="auto">
        {f.name}
        {f.source_url && (
          <>
            {" "}
            <a href={f.source_url} target="_blank" rel="noopener noreferrer">
              {t("layers.manage.review.source")}
            </a>
          </>
        )}
      </td>
      <td>{f.name_confidence ? t(`layers.manage.confidence.${f.name_confidence}`) : "—"}</td>
      <td dir="auto">{f.name_source ?? "—"}</td>
      <td>{gouvernorats.nameOf(f.gouvernorat_code) ?? "—"}</td>
      <td>{actions}</td>
    </tr>
  );

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>{t("layers.manage.review.title")}</h3>
      <p className="muted">{t("layers.manage.review.help")}</p>
      <fieldset className="segmented" aria-label={t("layers.manage.review.views")}>
        <label className="segmented__item">
          <input
            type="radio"
            name={`${id}-view`}
            checked={view.kind === "names" && view.confidence === null}
            onChange={() => setView({ kind: "names", confidence: null })}
          />
          <span>{t("layers.manage.review.all")}</span>
        </label>
        {CONFIDENCES.filter((c) => (counts[c] ?? 0) > 0 || (view.kind === "names" && view.confidence === c)).map((c) => (
          <label key={c} className="segmented__item">
            <input
              type="radio"
              name={`${id}-view`}
              checked={view.kind === "names" && view.confidence === c}
              onChange={() => setView({ kind: "names", confidence: c })}
            />
            <span>
              {t(`layers.manage.confidence.${c}`)} ({fmt.number(counts[c] ?? 0)})
            </span>
          </label>
        ))}
        <label className="segmented__item">
          <input
            type="radio"
            name={`${id}-view`}
            checked={view.kind === "duplicates"}
            onChange={() => setView({ kind: "duplicates" })}
          />
          <span>
            {t("layers.manage.review.duplicatesTab")} ({fmt.number(counts.duplicates ?? 0)})
          </span>
        </label>
      </fieldset>
      <ReasonField label={t("layers.reasonLabel")} value={reason} onChange={setReason} showError={tried} />
      {view.kind === "names" && (counts.high ?? 0) + (counts.confirmed ?? 0) > 0 && (
        <button
          type="button"
          className="btn"
          disabled={mutation.isPending}
          onClick={() => send({ accept_confidence: ["confirmed", "high"] })}
        >
          {t("layers.manage.review.acceptHigh", { n: fmt.number((counts.high ?? 0) + (counts.confirmed ?? 0)) })}
        </button>
      )}
      <div role="status" aria-live="polite">
        {done && <p className="alert alert--ok">{done}</p>}
      </div>
      {mutation.isError && <ErrorLine error={mutation.error} />}
      {query.isLoading && <Loading />}
      {query.isError && <ErrorBox error={query.error} onRetry={() => void query.refetch()} />}
      {query.isSuccess && items.length === 0 && <p className="muted">{t("layers.manage.review.empty")}</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("layers.places.name")}</th>
                <th scope="col">{t("layers.manage.review.confidence")}</th>
                <th scope="col">{t("layers.manage.review.nameSource")}</th>
                <th scope="col">{t("layers.places.gouvernorat")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("layers.history.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {view.kind === "names"
                ? items.map((f) =>
                    row(
                      f,
                      <div className="actions">
                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => send({ items: [{ id: f.id, action: "accept" }] })}
                        >
                          {t("layers.manage.review.accept")}
                        </button>
                        {edits[f.id] === undefined ? (
                          <button
                            type="button"
                            className="btn btn--small"
                            onClick={() => setEdits({ ...edits, [f.id]: f.name })}
                          >
                            {t("layers.manage.review.edit")}
                          </button>
                        ) : (
                          <>
                            <input
                              dir="auto"
                              aria-label={t("layers.manage.review.newName", { name: f.name })}
                              maxLength={200}
                              value={edits[f.id]}
                              onChange={(e) => setEdits({ ...edits, [f.id]: e.target.value })}
                            />
                            <button
                              type="button"
                              className="btn btn--small btn--primary"
                              disabled={!edits[f.id]?.trim()}
                              onClick={() => send({ items: [{ id: f.id, action: "edit", name: edits[f.id]?.trim() }] })}
                            >
                              {t("aiSettings.save")}
                            </button>
                          </>
                        )}
                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => send({ items: [{ id: f.id, action: "reject" }] })}
                        >
                          {t("layers.manage.review.reject")}
                        </button>
                      </div>,
                    ),
                  )
                : items.map((f, i) => {
                    const twin = items.find((o, j) => j !== i && o.name === f.name);
                    return row(
                      f,
                      <div className="actions">
                        <button
                          type="button"
                          className="btn btn--small"
                          onClick={() => send({ items: [{ id: f.id, action: "keep" }] })}
                        >
                          {t("layers.manage.review.keep")}
                        </button>
                        {twin && (
                          <button
                            type="button"
                            className="btn btn--small"
                            onClick={() => send({ items: [{ id: f.id, action: "merge", into: twin.id }] })}
                          >
                            {t("layers.manage.review.merge")}
                          </button>
                        )}
                      </div>,
                    );
                  })}
            </tbody>
          </table>
        </div>
      )}
      {(query.data?.total ?? 0) > items.length && (
        <p className="muted">{t("layers.import.moreRows", { count: (query.data?.total ?? 0) - items.length })}</p>
      )}
    </section>
  );
}
