// The folders of the map's layer panel (phase UI-3b, docs/phase-ui3/design-layer-groups.md): the system
// administrator names them, gives each an icon, a colour and a place in the list, and deletes an empty one. A folder
// grants nothing: who sees a layer stays in the layer's own settings.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useLanguage } from "../lib/hooks";
import { keyFrom, OTHER_GROUP, type LayerGroup, type LayerGroupBody, type Names } from "../lib/layers";
import { layerKeys } from "../lib/layersApi";
import { localized } from "../lib/localized";
import { IconTile, iconOr, toneOr, type IconName, type Tone } from "./Icon";

/** The same lists as the API (app/modules/layers/domain.py GROUP_ICONS and GROUP_TONES). */
export const GROUP_ICONS = [
  "localFireDepartment",
  "medicalServices",
  "policy",
  "apartment",
  "menuBook",
  "localShipping",
  "inventory2",
  "map",
  "groups",
  "schedule",
  "lockOpen",
  "layers",
  "healthAndSafety",
  "warning",
  "campaign",
  "folderOpen",
] as const satisfies readonly IconName[];

export const GROUP_TONES = [
  "red",
  "navy",
  "purple",
  "green",
  "amber",
  "teal",
  "slate",
  "pink",
  "sky",
  "orange",
] as const satisfies readonly Tone[];

const KEPT = new Set([OTHER_GROUP, "sensitive"]);

interface Draft {
  key: string;
  name: Names;
  icon: string;
  tone: string;
  position: number;
}

function draftOf(group: LayerGroup | null, next: number): Draft {
  return group
    ? { key: group.key, name: { ...group.name }, icon: group.icon, tone: group.tone, position: group.position }
    : { key: "", name: { ar: "", fr: "", en: "" }, icon: "folderOpen", tone: "teal", position: next };
}

function GroupForm({ group, next, onDone }: { group: LayerGroup | null; next: number; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const id = useId();
  const [draft, setDraft] = useState<Draft>(() => draftOf(group, next));
  const [tried, setTried] = useState(false);
  const missing = (["ar", "fr", "en"] as const).some((l) => draft.name[l].trim() === "") || draft.key.length < 2;
  const mutation = useMutation({
    mutationFn: () => {
      const name = { ar: draft.name.ar.trim(), fr: draft.name.fr.trim(), en: draft.name.en.trim() };
      const body: LayerGroupBody = { ...draft, name };
      if (!group) return api.createLayerGroup(body);
      const { key: _key, ...changes } = body;
      return api.updateLayerGroup(group.key, changes);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: layerKeys.all });
      onDone();
    },
  });
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    if (!missing) mutation.mutate();
  };
  const setName = (l: keyof Names, value: string) =>
    setDraft({ ...draft, name: { ...draft.name, [l]: value }, key: !group && l === "fr" ? keyFrom(value) : draft.key });

  return (
    <form noValidate onSubmit={submit} className="card layer-group-form" aria-labelledby={`${id}-title`}>
      <h3 id={`${id}-title`}>
        {group ? t("layers.groups.editTitle", { group: localized(group.name, lang) }) : t("layers.groups.newTitle")}
      </h3>
      <div className="settings-grid">
        {(["ar", "fr", "en"] as const).map((l) => (
          <div className="field" key={l}>
            <label htmlFor={`${id}-name-${l}`}>{t(`layers.form.name_${l}`)}</label>
            <input
              id={`${id}-name-${l}`}
              lang={l}
              dir={l === "ar" ? "rtl" : "ltr"}
              aria-required="true"
              maxLength={100}
              value={draft.name[l]}
              aria-invalid={tried && draft.name[l].trim() === "" ? true : undefined}
              onChange={(e) => setName(l, e.target.value)}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${id}-position`}>{t("layers.groups.position")}</label>
          <input
            id={`${id}-position`}
            type="number"
            min={0}
            max={999}
            inputMode="numeric"
            value={draft.position}
            aria-describedby={`${id}-position-help`}
            onChange={(e) => setDraft({ ...draft, position: Math.max(0, Math.min(999, Number(e.target.value) || 0)) })}
          />
          <p id={`${id}-position-help`} className="muted">
            {t("layers.groups.positionHelp")}
          </p>
        </div>
      </div>
      <fieldset className="layer-groups">
        <legend>{t("layers.form.icon")}</legend>
        {GROUP_ICONS.map((icon) => (
          <label key={icon} className="chip-toggle">
            <input
              type="radio"
              name={`${id}-icon`}
              checked={draft.icon === icon}
              onChange={() => setDraft({ ...draft, icon })}
            />
            <span>
              <IconTile name={icon} tone={toneOr(draft.tone, "slate")} size="sm" />
              {t(`layers.groups.icons.${icon}`)}
            </span>
          </label>
        ))}
      </fieldset>
      <fieldset className="layer-groups">
        <legend>{t("layers.form.colour")}</legend>
        {GROUP_TONES.map((tone) => (
          <label key={tone} className="chip-toggle">
            <input
              type="radio"
              name={`${id}-tone`}
              checked={draft.tone === tone}
              onChange={() => setDraft({ ...draft, tone })}
            />
            <span>
              <span className={`tone-dot tone-${tone}`} aria-hidden="true" />
              {t(`layers.groups.tones.${tone}`)}
            </span>
          </label>
        ))}
      </fieldset>
      {tried && missing && (
        <p className="alert alert--error" role="alert">
          {t("layers.groups.namesRequired")}
        </p>
      )}
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
      <div className="actions">
        <button type="submit" className="btn btn--primary" disabled={mutation.isPending}>
          {mutation.isPending ? t("aiSettings.saving") : t("aiSettings.save")}
        </button>
        <button type="button" className="btn" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function DeleteGroup({ group }: { group: LayerGroup }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const lang = useLanguage();
  const mutation = useMutation({
    mutationFn: () => api.deleteLayerGroup(group.key),
    onSuccess: () => void qc.invalidateQueries({ queryKey: layerKeys.all }),
  });
  if (KEPT.has(group.key)) return <span className="muted">{t("layers.groups.kept")}</span>;
  if (group.layer_count > 0) return <span className="muted">{t("layers.groups.notEmpty")}</span>;
  return (
    <>
      <button
        type="button"
        className="btn btn--small btn--danger"
        disabled={mutation.isPending}
        aria-label={t("layers.groups.deleteNamed", { group: localized(group.name, lang) })}
        onClick={() => mutation.mutate()}
      >
        {t("layers.groups.delete")}
      </button>
      {mutation.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(mutation.error))}
        </p>
      )}
    </>
  );
}

/** The folders of the layer panel, with their layers counted, for the system administrator. */
export function LayerGroupsCard({ groups }: { groups: readonly LayerGroup[] }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const lang = useLanguage();
  const id = useId();
  const [editing, setEditing] = useState<string | null>(null) // a key, "new", or nothing;
  const next = Math.min(999, Math.max(0, ...groups.map((g) => g.position)) + 1);
  const current = groups.find((g) => g.key === editing) ?? null;

  return (
    <section className="card" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>{t("layers.groups.title")}</h2>
      <p className="muted">{t("layers.groups.intro")}</p>
      <table className="table layer-groups-table">
        <caption className="visually-hidden">{t("layers.groups.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("layers.groups.position")}</th>
            <th scope="col">{t("layers.groups.folder")}</th>
            <th scope="col">{t("layers.groups.layers")}</th>
            <th scope="col">
              <span className="visually-hidden">{t("layers.history.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g) => (
            <tr key={g.key} aria-current={g.key === editing ? "true" : undefined}>
              <td className="num">{fmt.number(g.position)}</td>
              <td>
                <span className="layer-group-name">
                  <IconTile name={iconOr(g.icon, "layers")} tone={toneOr(g.tone, "slate")} size="sm" />
                  <span dir="auto">{localized(g.name, lang)}</span>
                  {g.sensitive && <span className="chip">{t("layers.manage.ministerOnly")}</span>}
                </span>
              </td>
              <td className="num">{fmt.number(g.layer_count)}</td>
              <td>
                <div className="actions">
                  <button
                    type="button"
                    className="btn btn--small"
                    aria-label={t("layers.groups.editNamed", { group: localized(g.name, lang) })}
                    onClick={() => setEditing(g.key)}
                  >
                    {t("layers.groups.edit")}
                  </button>
                  <DeleteGroup group={g} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {editing === null && (
        <button type="button" className="btn" onClick={() => setEditing("new")}>
          {t("layers.groups.newTitle")}
        </button>
      )}
      {editing !== null && (
        <GroupForm key={editing} group={current} next={next} onDone={() => setEditing(null)} />
      )}
    </section>
  );
}
