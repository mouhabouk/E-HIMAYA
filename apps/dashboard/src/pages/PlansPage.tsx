// covers: phase PL1 (docs/phase-pl/design-plans.md §2): the intervention plans of the national committee by hazard,
// each in the colour of its hazard (the blue plan of the floods), the national plan in force and the annexes of the
// gouvernorats the reader sees, read on the screen; the central room keeps the hazards and their colours.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, iconOr } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { PdfViewer } from "../components/PdfViewer";
import { DocStatus, Validity } from "../components/RegisterBits";
import { SimBadge } from "../components/crisis/CrisisBits";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { simText } from "../lib/crisisText";
import { useFormat } from "../lib/hooks";
import {
  HAZARD_ICONS,
  hazardName,
  planKeys,
  textOn,
  type Hazard,
  type HazardBody,
  type HazardPlans,
  type PlanEntry,
} from "../lib/plans";
import { registerKeys } from "../lib/register";

const enc = encodeURIComponent;

/** The colour of a hazard on a card or a header, with the text that reads on it. */
function hazardStyle(h: Pick<Hazard, "colour">): CSSProperties {
  return { "--hazard": h.colour, "--hazard-text": textOn(h.colour) } as CSSProperties;
}

function PlanRow({ entry, label }: { entry: PlanEntry; label: string }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const d = entry.document;
  const title = simText(d.title);
  return (
    <li className="plan-row">
      <div className="plan-row__text">
        <p className="plan-row__where">
          <strong>{label}</strong> <DocStatus status={d.status} />
          {title.sim && <SimBadge />}
        </p>
        <p dir="auto">
          <Link to={`/register/${enc(d.id)}`}>{title.text}</Link>
        </p>
        <p className="muted">
          {d.issuer} · {t("register.issuedOn", { date: fmt.date(d.issued_on) })} · <Validity d={d} />
          {entry.versions > 1 && <> · {t("plans.versions", { count: entry.versions })}</>}
        </p>
      </div>
      {d.file_type === "application/pdf" ? (
        <Link className="btn btn--small btn--primary" to={`/plans/${enc(d.id)}`}>
          <Icon name="pictureAsPdf" size={18} />
          {t("plans.view")}
        </Link>
      ) : (
        <span className="muted">{t("plans.noFile")}</span>
      )}
    </li>
  );
}

function HazardCard({ group, canCreate }: { group: HazardPlans; canCreate: boolean }) {
  const { t, i18n } = useTranslation();
  const h = group.hazard;
  const name = hazardName(h, i18n.language);
  const headingId = `hazard-${h.key}`;
  return (
    <li className="card plan-card" style={hazardStyle(h)} aria-labelledby={headingId}>
      <div className="plan-card__head">
        <span className="plan-card__icon" aria-hidden="true">
          <Icon name={iconOr(h.icon, "warning")} size={24} />
        </span>
        <h2 id={headingId}>{t("plans.planOf", { hazard: name })}</h2>
      </div>
      {group.national || group.regional.length > 0 ? (
        <ul className="plan-card__list">
          {group.national && <PlanRow entry={group.national} label={t("plans.national")} />}
          {group.regional.map((p) => (
            <PlanRow key={p.document.id} entry={p} label={p.document.gouvernorat_name ?? ""} />
          ))}
        </ul>
      ) : (
        <p className="muted plan-card__empty">{t("plans.none")}</p>
      )}
      {canCreate && (
        <p className="plan-card__foot">
          <Link className="btn btn--small" to={`/register?new=plan&hazard=${enc(h.key)}`}>
            {t("plans.new")}
          </Link>
        </p>
      )}
    </li>
  );
}

function HazardForm({ hazard, onDone }: { hazard: Hazard | null; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const id = useId();
  const [key, setKey] = useState(hazard?.key ?? "");
  const [f, setF] = useState<HazardBody>(() =>
    hazard
      ? { name: { ...hazard.name }, colour: hazard.colour, icon: hazard.icon, position: hazard.position, active: hazard.active }
      : { name: { ar: "", fr: "", en: "" }, colour: "#1976D2", icon: "warning", position: 50, active: true },
  );
  const save = useMutation({
    mutationFn: () => api.saveHazard(key, { ...f, colour: f.colour.toUpperCase() }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: planKeys.all });
      onDone();
    },
  });
  const keyOk = /^[a-z][a-z0-9_]{1,39}$/.test(key);
  const namesOk = (["ar", "fr", "en"] as const).every((l) => f.name[l].trim());
  return (
    <form
      className="card hazard-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (keyOk && namesOk) save.mutate();
      }}
    >
      <h3>{hazard ? t("plans.hazards.edit", { name: hazard.name.ar }) : t("plans.hazards.add")}</h3>
      <div className="form-grid">
        {!hazard && (
          <div className="field">
            <label htmlFor={`${id}-k`}>{t("plans.hazards.key")}</label>
            <input id={`${id}-k`} dir="ltr" value={key} maxLength={40} required pattern="[a-z][a-z0-9_]{1,39}" onChange={(e) => setKey(e.target.value)} />
            <p className="field__hint">{t("plans.hazards.keyHint")}</p>
          </div>
        )}
        {(["ar", "fr", "en"] as const).map((l) => (
          <div className="field" key={l}>
            <label htmlFor={`${id}-${l}`}>{t(`plans.hazards.name_${l}`)}</label>
            <input
              id={`${id}-${l}`}
              dir={l === "ar" ? "rtl" : "ltr"}
              lang={l}
              value={f.name[l]}
              maxLength={80}
              required
              onChange={(e) => setF((x) => ({ ...x, name: { ...x.name, [l]: e.target.value } }))}
            />
          </div>
        ))}
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${id}-c`}>{t("plans.hazards.colour")}</label>
          <input id={`${id}-c`} type="color" value={f.colour.toLowerCase()} onChange={(e) => setF((x) => ({ ...x, colour: e.target.value.toUpperCase() }))} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-i`}>{t("plans.hazards.icon")}</label>
          <select id={`${id}-i`} value={f.icon} onChange={(e) => setF((x) => ({ ...x, icon: e.target.value }))}>
            {HAZARD_ICONS.map((i) => (
              <option key={i} value={i}>
                {t(`plans.icons.${i}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${id}-p`}>{t("plans.hazards.position")}</label>
          <input
            id={`${id}-p`}
            type="number"
            min={0}
            max={999}
            value={f.position}
            onChange={(e) => setF((x) => ({ ...x, position: Math.min(999, Math.max(0, Number(e.target.value) || 0)) }))}
          />
        </div>
      </div>
      <label className="checkbox">
        <input type="checkbox" checked={f.active} onChange={(e) => setF((x) => ({ ...x, active: e.target.checked }))} />
        {t("plans.hazards.active")}
      </label>
      <p className="hazard-swatch" style={hazardStyle(f)}>
        <Icon name={iconOr(f.icon, "warning")} size={20} />
        {f.name.ar || t("plans.hazards.preview")}
      </p>
      {save.isError && (
        <p role="alert" className="field__error">
          {t(errorMessageKey(save.error))}
        </p>
      )}
      <div className="form-actions">
        <button type="submit" className="btn btn--primary" disabled={!keyOk || !namesOk || save.isPending}>
          {t("plans.hazards.save")}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onDone}>
          {t("common.cancel")}
        </button>
      </div>
    </form>
  );
}

function HazardsTab() {
  const { t, i18n } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const list = useQuery({ queryKey: planKeys.hazards, queryFn: ({ signal }) => api.hazards(signal) });
  const [editing, setEditing] = useState<Hazard | "new" | null>(null);
  if (list.isPending) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;
  return (
    <section aria-labelledby="hazards-title">
      <div className="page__head">
        <h2 id="hazards-title">{t("plans.hazards.title")}</h2>
        {editing === null && (
          <button type="button" className="btn" onClick={() => setEditing("new")}>
            {t("plans.hazards.add")}
          </button>
        )}
      </div>
      <p className="muted">{t("plans.hazards.intro")}</p>
      {editing !== null && <HazardForm key={editing === "new" ? "new" : editing.key} hazard={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
      <table className="table">
        <caption className="visually-hidden">{t("plans.hazards.title")}</caption>
        <thead>
          <tr>
            <th scope="col">{t("plans.hazards.colour")}</th>
            <th scope="col">{t("plans.hazards.name")}</th>
            <th scope="col">{t("plans.hazards.position")}</th>
            <th scope="col">{t("plans.hazards.state")}</th>
            <th scope="col">{t("plans.hazards.updated")}</th>
            <th scope="col">
              <span className="visually-hidden">{t("plans.hazards.actions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {list.data.map((h) => (
            <tr key={h.key}>
              <td>
                <span className="hazard-swatch hazard-swatch--small" style={hazardStyle(h)}>
                  <Icon name={iconOr(h.icon, "warning")} size={18} />
                  <bdi dir="ltr">{h.colour}</bdi>
                </span>
              </td>
              <td>{hazardName(h, i18n.language)}</td>
              <td>{fmt.number(h.position)}</td>
              <td>{h.active ? t("plans.hazards.on") : t("plans.hazards.off")}</td>
              <td className="muted">
                {h.updated_by_name ?? "—"} · {fmt.dateTime(h.updated_at)}
              </td>
              <td>
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => setEditing(h)}
                  aria-label={t("plans.hazards.edit", { name: hazardName(h, i18n.language) })}
                >
                  {t("plans.hazards.editShort")}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function PlansPage() {
  const { t } = useTranslation();
  const { api } = useServices();
  const [tab, setTab] = useState<"plans" | "hazards">("plans");
  const overview = useQuery({ queryKey: planKeys.overview, queryFn: ({ signal }) => api.plans(signal) });
  const data = overview.data;
  return (
    <div className="page plans-page">
      <div className="page__head">
        <PageTitle icon="menuBook" tone="navy">
          {t("plans.title")}
        </PageTitle>
      </div>
      <p className="muted">{t("plans.intro")}</p>
      {data?.can_manage_hazards && (
        <div role="tablist" aria-label={t("plans.tabs.label")} className="tabs">
          {(["plans", "hazards"] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={`tabs__tab${tab === k ? " tabs__tab--active" : ""}`}
              onClick={() => setTab(k)}
            >
              {t(`plans.tabs.${k}`)}
            </button>
          ))}
        </div>
      )}
      {overview.isPending && <Loading />}
      {overview.isError && <ErrorBox error={overview.error} onRetry={() => void overview.refetch()} />}
      {data &&
        (tab === "hazards" && data.can_manage_hazards ? (
          <HazardsTab />
        ) : (
          <ul className="plan-cards">
            {data.hazards.map((g) => (
              <HazardCard key={g.hazard.key} group={g} canCreate={data.can_create} />
            ))}
          </ul>
        ))}
    </div>
  );
}

/** A plan read on the screen, under a header in the colour of its hazard. */
export function PlanViewerPage() {
  const { t, i18n } = useTranslation();
  const { api } = useServices();
  const fmt = useFormat();
  const { id = "" } = useParams();
  const detail = useQuery({ queryKey: registerKeys.document(id), queryFn: ({ signal }) => api.registerDocument(id, signal) });
  const hazards = useQuery({ queryKey: planKeys.hazards, queryFn: ({ signal }) => api.hazards(signal) });
  if (detail.isPending) return <Loading />;
  if (detail.isError) return <ErrorBox error={detail.error} onRetry={() => void detail.refetch()} />;
  const d = detail.data.document;
  const hazard = hazards.data?.find((h) => h.key === d.hazard_key);
  const title = simText(d.title);
  return (
    <div className="page plan-viewer-page">
      <p>
        <Link to="/plans">{t("plans.back")}</Link>
      </p>
      <header className="plan-viewer-page__head" style={hazard ? hazardStyle(hazard) : undefined}>
        {hazard && (
          <p className="plan-viewer-page__hazard">
            <Icon name={iconOr(hazard.icon, "warning")} size={20} />
            {t("plans.planOf", { hazard: hazardName(hazard, i18n.language) })}
          </p>
        )}
        <h1 dir="auto">
          {title.text} {title.sim && <SimBadge />}
        </h1>
        <p>
          <DocStatus status={d.status} /> {d.level === "central" ? t("plans.national") : d.gouvernorat_name} · {d.issuer} ·{" "}
          {t("register.issuedOn", { date: fmt.date(d.issued_on) })} · <Link to={`/register/${enc(d.id)}`}>{t("plans.record")}</Link>
        </p>
        {d.status === "repealed" && <p className="alert alert--warn">{t("plans.repealed")}</p>}
      </header>
      {d.file_type === "application/pdf" ? <PdfViewer documentId={d.id} title={d.title} /> : <p className="card ops-empty">{t("plans.noFile")}</p>}
    </div>
  );
}
