import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useSoftphone } from "../context/softphone";
import {
  CALL_RESULTS,
  FOLLOW_UP_MINUTES,
  RESULT_TONE,
  categoryLook,
  liaisonKeys,
  partyNumber,
  rankBodies,
  type CallResult,
  type ContactBody,
  type IncidentLiaison,
  type Party,
  type PartyPick,
  type PickerData,
  type Suggestion,
} from "../lib/liaison";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { canManageIncidents, canUseTelephony } from "../lib/roles";
import type { IncidentDetail } from "../lib/types";
import { ErrorBox, Loading } from "./Feedback";
import { Icon, IconTile, Pill } from "./Icon";
import { ContactForm } from "./LiaisonContactForm";
import { InlineDialog } from "./Phase9Bits";
import { Stepper } from "./Stepper";

/**
 * Informing the partner bodies by phone (OS20, docs/phase-os20/design-os20.md), in the incident file.
 * The room sets the level of the report: 1, handled in the room and closed without informing anyone; 2, bodies are
 * informed. The decision engine suggests the bodies; the picker adds several at once from the suggestions, the whole
 * contact system (searched, matches first) or the history of the reports, then returns to the report. Each body is
 * called from the softphone or by hand, and the call is recorded: result, what was asked and promised, expected
 * arrival, note, a reminder to call back. The bodies informed stay in the report's history.
 */
export function LiaisonPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const lang = useLanguage();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const [picking, setPicking] = useState(false);
  const top = useRef<HTMLElement>(null);
  const q = useQuery({
    queryKey: liaisonKeys.incident(incident.id),
    queryFn: ({ signal }) => api.liaisonIncident(incident.id, signal),
  });
  const follow = useQuery({
    queryKey: liaisonKeys.followUps(incident.id),
    queryFn: ({ signal }) => api.liaisonFollowUps(incident.id, signal),
    refetchInterval: 30_000,
  });
  const put = (data: IncidentLiaison) => {
    qc.setQueryData(liaisonKeys.incident(incident.id), data);
    void qc.invalidateQueries({ queryKey: liaisonKeys.picker(incident.id) });
  };
  const level = useMutation({
    mutationFn: (l: 1 | 2) => api.liaisonSetLevel(incident.id, l),
    onSuccess: put,
  });
  const add = useMutation({
    mutationFn: (picks: PartyPick[]) =>
      api.liaisonAddParties(incident.id, picks),
    onSuccess: (data) => {
      put(data);
      setPicking(false);
      top.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    },
  });
  const done = useMutation({
    mutationFn: (callId: string) => api.liaisonFollowUpDone(callId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: liaisonKeys.all }),
  });
  const data = q.data;
  const current = data?.level?.level ?? null;
  const due = (follow.data ?? []).filter((c) => !c.follow_up_done_at);
  return (
    <section
      ref={top}
      className="card liaison-panel"
      aria-labelledby="sec-liaison"
    >
      <div className="liaison-panel__head">
        <h2 id="sec-liaison">
          <IconTile name="call" tone="teal" size="sm" />{" "}
          {t("liaison.panel.title")}
        </h2>
        {current && (
          <Pill tone={current === 1 ? "slate" : "teal"}>
            {t(`liaison.level.short${current}`)}
          </Pill>
        )}
        {data && data.parties.length > 0 && (
          <Pill tone="navy">
            {t("liaison.panel.parties", { n: data.parties.length })}
          </Pill>
        )}
      </div>
      {q.isLoading && <Loading />}
      {q.isError && (
        <ErrorBox error={q.error} onRetry={() => void q.refetch()} />
      )}
      {(level.isError || add.isError) && (
        <ErrorBox error={level.error ?? add.error} />
      )}
      {data && (
        <>
          <fieldset
            className="liaison-levels"
            disabled={!canWrite || level.isPending}
          >
            <legend>{t("liaison.level.legend")}</legend>
            {([1, 2] as const).map((l) => (
              <label
                key={l}
                className={`liaison-level${current === l ? " liaison-level--on" : ""}`}
              >
                <input
                  type="radio"
                  name={`liaison-level-${incident.id}`}
                  checked={current === l}
                  onChange={() => level.mutate(l)}
                />
                <span>
                  <strong>{t(`liaison.level.title${l}`)}</strong>
                  <small className="muted">{t(`liaison.level.hint${l}`)}</small>
                </span>
              </label>
            ))}
          </fieldset>
          {data.level?.set_by_name && (
            <p className="muted liaison-by">
              {t("liaison.level.by", { name: data.level.set_by_name })}
            </p>
          )}

          {due.length > 0 && (
            <ul
              className="liaison-due"
              aria-label={t("liaison.followUps.title")}
            >
              {due.map((c) => (
                <li
                  key={c.id}
                  className={
                    c.follow_up_due
                      ? "liaison-due__item liaison-due__item--now"
                      : "liaison-due__item"
                  }
                >
                  <Icon name="schedule" size={18} />
                  <span>
                    {t(
                      c.follow_up_due
                        ? "liaison.followUps.now"
                        : "liaison.followUps.later",
                      {
                        body: c.body_name,
                        who: c.official_name ?? "—",
                      },
                    )}
                  </span>
                  {canWrite && (
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={done.isPending}
                      onClick={() => done.mutate(c.id)}
                    >
                      {t("liaison.followUps.done")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {current === 2 && (
            <>
              <Suggestions
                items={data.suggestions}
                lang={lang}
                canWrite={canWrite}
                busy={add.isPending}
                onAdd={(s) =>
                  s.body_id &&
                  add.mutate([
                    {
                      body_id: s.body_id,
                      suggested: true,
                      reason: lang === "fr" ? s.reason.fr : s.reason.ar,
                    },
                  ])
                }
              />
              <div className="liaison-panel__actions">
                {canWrite && (
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={() => setPicking((v) => !v)}
                  >
                    <Icon name="groups" size={18} /> {t("liaison.picker.open")}
                  </button>
                )}
              </div>
              {picking && (
                <PartyPicker
                  incident={incident}
                  inReport={new Set(data.parties.map((p) => p.body_id))}
                  busy={add.isPending}
                  onConfirm={(picks) => add.mutate(picks)}
                  onClose={() => setPicking(false)}
                />
              )}
              {data.parties.length === 0 && (
                <p className="muted">{t("liaison.panel.noParties")}</p>
              )}
              <ul className="liaison-parties">
                {data.parties.map((p) => (
                  <PartyRow
                    key={p.id}
                    incidentId={incident.id}
                    party={p}
                    canWrite={canWrite}
                    onChange={put}
                  />
                ))}
              </ul>
            </>
          )}
          {current === 1 && (
            <p className="muted">{t("liaison.level.roomOnly")}</p>
          )}
          {current === null && (
            <p className="muted">{t("liaison.level.unset")}</p>
          )}
        </>
      )}
    </section>
  );
}

function Suggestions({
  items,
  lang,
  canWrite,
  busy,
  onAdd,
}: {
  items: Suggestion[];
  lang: string;
  canWrite: boolean;
  busy: boolean;
  onAdd: (s: Suggestion) => void;
}) {
  const { t } = useTranslation();
  if (items.length === 0) return null;
  return (
    <div className="liaison-sugg">
      <h3>{t("liaison.suggestions.title")}</h3>
      <ul>
        {items.map((s) => (
          <li
            key={s.agency}
            className={
              s.missing
                ? "liaison-sugg__item liaison-sugg__item--missing"
                : "liaison-sugg__item"
            }
          >
            <IconTile
              name={s.kind === "internal" ? "localFireDepartment" : "call"}
              tone={s.kind === "internal" ? "red" : "teal"}
              size="sm"
            />
            <span className="liaison-sugg__body">
              <strong dir="auto">{s.name}</strong>
              <small className="muted" dir="auto">
                {lang === "fr" ? s.reason.fr : s.reason.ar}
                {s.public_phone && (
                  <>
                    {" · "}
                    <span className="mono" dir="ltr">
                      {s.public_phone}
                    </span>
                  </>
                )}
              </small>
            </span>
            {s.in_report ? (
              <Pill tone="slate">{t("liaison.suggestions.inReport")}</Pill>
            ) : s.missing ? (
              <Pill tone="amber">{t("liaison.suggestions.missing")}</Pill>
            ) : (
              canWrite && (
                <button
                  type="button"
                  className="btn btn--small"
                  disabled={busy}
                  onClick={() => onAdd(s)}
                >
                  {t("liaison.suggestions.add")}
                </button>
              )
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- a party and its calls

function PartyRow({
  incidentId,
  party,
  canWrite,
  onChange,
}: {
  incidentId: string;
  party: Party;
  canWrite: boolean;
  onChange: (data: IncidentLiaison) => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const phone = useSoftphone();
  const [calling, setCalling] = useState<"softphone" | "manual" | null>(null);
  const remove = useMutation({
    mutationFn: () => api.liaisonRemoveParty(incidentId, party.id),
    onSuccess: onChange,
  });
  const look = categoryLook(party.category);
  const number = partyNumber(party);
  const soft = Boolean(phone) && canUseTelephony(user?.identity.roles ?? []);
  return (
    <li className="liaison-party">
      <div className="liaison-party__head">
        <IconTile name={look.icon} tone={look.tone} />
        <div className="liaison-party__who">
          <strong dir="auto">{party.body_name}</strong>
          <span className="muted" dir="auto">
            {party.official_name ?? t("liaison.party.noOfficial")}
            {party.official_role ? ` · ${party.official_role}` : ""}
            {number && (
              <>
                {" · "}
                <span className="mono" dir="ltr">
                  {number}
                </span>
              </>
            )}
          </span>
        </div>
        {party.last_result ? (
          <Pill tone={RESULT_TONE[party.last_result]}>
            {t(`liaison.result.${party.last_result}`)}
          </Pill>
        ) : (
          <Pill tone="slate">{t("liaison.party.notCalled")}</Pill>
        )}
        {party.suggested && (
          <Pill tone="green">{t("liaison.party.suggested")}</Pill>
        )}
      </div>
      {canWrite && calling === null && (
        <div className="liaison-party__actions">
          {soft && number && (
            <button
              type="button"
              className="btn btn--small btn--call"
              onClick={() => setCalling("softphone")}
            >
              <Icon name="call" size={16} /> {t("liaison.call.soft")}
            </button>
          )}
          <button
            type="button"
            className="btn btn--small"
            onClick={() => setCalling("manual")}
          >
            {t("liaison.call.manual")}
          </button>
          {party.calls.length === 0 && (
            <button
              type="button"
              className="btn btn--small btn--ghost"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              {t("liaison.party.remove")}
            </button>
          )}
        </div>
      )}
      {remove.isError && <ErrorBox error={remove.error} />}
      {calling && (
        <CallRecorder
          incidentId={incidentId}
          party={party}
          via={calling}
          onClose={() => setCalling(null)}
        />
      )}
      {party.calls.length > 0 && (
        <ol className="liaison-calls">
          {party.calls.map((c) => (
            <li key={c.id}>
              <span className="mono muted">{fmt.time(c.at)}</span>{" "}
              <Pill tone={RESULT_TONE[c.result]}>
                {t(`liaison.result.${c.result}`)}
              </Pill>{" "}
              <span dir="auto">{c.official_name ?? ""}</span>{" "}
              <span className="muted">· {t(`liaison.via.${c.via}`)}</span>
              {c.promised && (
                <div dir="auto">
                  <strong>{t("liaison.call.promised")}:</strong> {c.promised}
                  {c.eta_min !== null &&
                    ` · ${t("liaison.call.etaShort", { n: c.eta_min })}`}
                </div>
              )}
              {c.asked && (
                <div className="muted" dir="auto">
                  {t("liaison.call.asked")}: {c.asked}
                </div>
              )}
              {c.note && (
                <div className="muted" dir="auto">
                  {c.note}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </li>
  );
}

function CallRecorder({
  incidentId,
  party,
  via,
  onClose,
}: {
  incidentId: string;
  party: Party;
  via: "softphone" | "manual";
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const phone = useSoftphone();
  const qc = useQueryClient();
  const base = useId();
  const body = useQuery({
    queryKey: liaisonKeys.body(party.body_id),
    queryFn: ({ signal }) => api.liaisonBody(party.body_id, signal),
  });
  const officials = body.data?.officials ?? [];
  const [officialId, setOfficialId] = useState<string | null>(
    party.official_id,
  );
  const official = officials.find((o) => o.id === officialId);
  const number = official?.phones[0] ?? partyNumber(party) ?? "";
  const [result, setResult] = useState<CallResult | null>(null);
  const [asked, setAsked] = useState("");
  const [promised, setPromised] = useState("");
  const [eta, setEta] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [followUp, setFollowUp] = useState<number>(0);
  const [phoneCallId, setPhoneCallId] = useState<string | null>(null);
  const dial = useMutation({
    mutationFn: (n: string) =>
      phone
        ? phone.dial({ number: n.replace(/\s+/g, "") })
        : Promise.reject(new Error("softphone_not_registered")),
    onSuccess: (r) => setPhoneCallId(r.id),
  });
  const save = useMutation({
    mutationFn: () =>
      api.liaisonAddCall(incidentId, party.id, {
        official_id: officialId,
        number,
        via,
        telephony_call_id: phoneCallId,
        result: result ?? "answered",
        asked: asked.trim() || null,
        promised: promised.trim() || null,
        eta_min: eta,
        note: note.trim() || null,
        follow_up_min: followUp,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: liaisonKeys.all });
      onClose();
    },
  });
  const unanswered = result === "no_answer" || result === "busy";
  const next = unanswered
    ? (officials.find(
        (o) => o.id !== officialId && o.position >= (official?.position ?? 0),
      ) ?? officials.find((o) => o.id !== officialId))
    : undefined;
  return (
    <InlineDialog
      title={t("liaison.call.title", { body: party.body_name })}
      onClose={onClose}
    >
      <div className="liaison-call">
        {officials.length > 0 && (
          <div className="field">
            <label htmlFor={`${base}-off`}>{t("liaison.call.official")}</label>
            <select
              id={`${base}-off`}
              value={officialId ?? ""}
              onChange={(e) => setOfficialId(e.target.value || null)}
            >
              {officials.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                  {o.role ? ` · ${o.role}` : ""} · {o.phones.join(" / ")}
                </option>
              ))}
            </select>
          </div>
        )}
        <p className="liaison-call__number">
          <Icon name="call" size={18} />{" "}
          <span className="mono" dir="ltr">
            {number || "—"}
          </span>{" "}
          {via === "softphone" ? (
            <button
              type="button"
              className="btn btn--small btn--call"
              disabled={!number || dial.isPending}
              onClick={() => dial.mutate(number)}
            >
              {dial.isPending ? t("phone.dialing") : t("liaison.call.dial")}
            </button>
          ) : (
            <span className="muted">{t("liaison.call.manualHint")}</span>
          )}
          {dial.isSuccess && (
            <span className="muted"> {t("phone.dialStarted")}</span>
          )}
        </p>
        {dial.isError && <ErrorBox error={dial.error} />}
        <fieldset className="segmented" aria-label={t("liaison.call.result")}>
          <legend>
            {t("liaison.call.result")} <span className="required">*</span>
          </legend>
          {CALL_RESULTS.map((r) => (
            <label key={r} className="segmented__item">
              <input
                type="radio"
                name={`${base}-res`}
                checked={result === r}
                onChange={() => setResult(r)}
              />
              <span>{t(`liaison.result.${r}`)}</span>
            </label>
          ))}
        </fieldset>
        {unanswered && next && (
          <p className="liaison-call__next">
            {t("liaison.call.next", { name: next.name, role: next.role ?? "" })}{" "}
            <button
              type="button"
              className="btn btn--small"
              onClick={() => setOfficialId(next.id)}
            >
              {t("liaison.call.useNext")}
            </button>
          </p>
        )}
        {result === "answered" && (
          <div className="liaison-call__grid">
            <div className="field">
              <label htmlFor={`${base}-ask`}>{t("liaison.call.asked")}</label>
              <input
                id={`${base}-ask`}
                value={asked}
                maxLength={500}
                onChange={(e) => setAsked(e.target.value)}
                dir="auto"
              />
            </div>
            <div className="field">
              <label htmlFor={`${base}-pro`}>
                {t("liaison.call.promised")}
              </label>
              <input
                id={`${base}-pro`}
                value={promised}
                maxLength={500}
                onChange={(e) => setPromised(e.target.value)}
                dir="auto"
              />
            </div>
            <div className="field">
              <span className="field__label" id={`${base}-eta`}>
                {t("liaison.call.eta")}
              </span>
              <Stepper
                labelledBy={`${base}-eta`}
                value={eta}
                onChange={setEta}
                onClear={() => setEta(null)}
                min={0}
                max={1440}
                step={5}
                start={15}
                unit={t("liaison.call.minutes")}
              />
            </div>
          </div>
        )}
        <div className="field">
          <label htmlFor={`${base}-note`}>{t("liaison.call.note")}</label>
          <input
            id={`${base}-note`}
            value={note}
            maxLength={500}
            onChange={(e) => setNote(e.target.value)}
            dir="auto"
          />
        </div>
        <fieldset
          className="segmented segmented--small"
          aria-label={t("liaison.call.followUp")}
        >
          <legend>{t("liaison.call.followUp")}</legend>
          {FOLLOW_UP_MINUTES.map((m) => (
            <label key={m} className="segmented__item">
              <input
                type="radio"
                name={`${base}-fu`}
                checked={followUp === m}
                onChange={() => setFollowUp(m)}
              />
              <span>
                {m === 0
                  ? t("liaison.call.noFollowUp")
                  : t("liaison.call.inMinutes", { n: m })}
              </span>
            </label>
          ))}
        </fieldset>
        {save.isError && <ErrorBox error={save.error} />}
        <div className="actions">
          <button type="button" className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!result || !number || save.isPending}
            onClick={() => save.mutate()}
          >
            {t("liaison.call.save")}
          </button>
        </div>
      </div>
    </InlineDialog>
  );
}

// ---------------------------------------------------------------- the picker

type PickerView = "list" | "history";

function PartyPicker({
  incident,
  inReport,
  busy,
  onConfirm,
  onClose,
}: {
  incident: IncidentDetail;
  inReport: ReadonlySet<string>;
  busy: boolean;
  onConfirm: (picks: PartyPick[]) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const fmt = useFormat();
  const lang = useLanguage();
  const base = useId();
  const central = Boolean(user?.identity.national);
  const [gov, setGov] = useState<number | null>(
    incident.gouvernorat_code ?? null,
  );
  const [query, setQuery] = useState("");
  const [view, setView] = useState<PickerView>("list");
  const [adding, setAdding] = useState(false);
  // body id → official id (null: the first in calling order).
  const [selected, setSelected] = useState<
    Map<
      string,
      { official: string | null; suggested: boolean; reason: string | null }
    >
  >(new Map());
  const bodies = useQuery({
    queryKey: liaisonKeys.bodies({ gouvernorat: gov }),
    queryFn: ({ signal }) => api.liaisonBodies({ gouvernorat: gov }, signal),
  });
  const picker = useQuery({
    queryKey: liaisonKeys.picker(incident.id),
    queryFn: ({ signal }) => api.liaisonPicker(incident.id, signal),
  });
  const p: PickerData | undefined = picker.data;
  const reasons = useMemo(() => {
    const m = new Map<string, string>();
    for (const s of p?.suggestions ?? [])
      if (s.body_id)
        m.set(s.body_id, lang === "fr" ? s.reason.fr : s.reason.ar);
    return m;
  }, [p, lang]);
  const usedBefore = useMemo(
    () => new Map((p?.used_before ?? []).map((u) => [u.body_id, u])),
    [p],
  );
  const first = useMemo(
    () => new Set([...reasons.keys(), ...usedBefore.keys()]),
    [reasons, usedBefore],
  );
  const ranked = rankBodies(bodies.data ?? [], query, first);
  const q = query.trim();
  const top = q ? [] : ranked.filter((b) => first.has(b.id));
  const rest = q ? ranked : ranked.filter((b) => !first.has(b.id));
  const toggle = (bodyId: string, official: string | null, on: boolean) =>
    setSelected((prev) => {
      const next = new Map(prev);
      if (on)
        next.set(bodyId, {
          official,
          suggested: reasons.has(bodyId),
          reason: reasons.get(bodyId) ?? null,
        });
      else next.delete(bodyId);
      return next;
    });
  const mark = (s: string) => {
    if (!q) return s;
    const i = s.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return s;
    return (
      <>
        {s.slice(0, i)}
        <mark>{s.slice(i, i + q.length)}</mark>
        {s.slice(i + q.length)}
      </>
    );
  };
  const officialRow = (
    b: ContactBody,
    officialId: string | null,
    label: React.ReactNode,
    extra?: React.ReactNode,
  ) => {
    const locked = inReport.has(b.id);
    const pick = selected.get(b.id);
    const checked =
      locked || (pick !== undefined && pick.official === officialId);
    return (
      <label
        key={`${b.id}:${officialId ?? ""}`}
        className={`liaison-pick${locked ? " liaison-pick--locked" : ""}`}
      >
        <input
          type="checkbox"
          checked={checked}
          disabled={locked}
          onChange={(e) => toggle(b.id, officialId, e.target.checked)}
        />
        <span className="liaison-pick__text">
          {label}
          {extra}
        </span>
        {locked && <Pill tone="slate">{t("liaison.picker.inReport")}</Pill>}
      </label>
    );
  };
  const block = (b: ContactBody) => {
    const look = categoryLook(b.category);
    const used = usedBefore.get(b.id);
    return (
      <div key={b.id} className="liaison-pick-body">
        <div className="liaison-pick-body__head">
          <IconTile name={look.icon} tone={look.tone} size="sm" />
          <span className="liaison-pick-body__name">
            <strong dir="auto">{mark(b.name)}</strong>
            <small className="muted" dir="auto">
              {b.domain ? mark(b.domain) : ""} ·{" "}
              {b.gouvernorat_code
                ? gouvernorats.nameOf(b.gouvernorat_code)
                : t("liaison.national")}
            </small>
          </span>
          {reasons.has(b.id) && (
            <Pill tone="green">{t("liaison.picker.suggested")}</Pill>
          )}
          {used && (
            <Pill tone="navy">
              {t("liaison.picker.usedBefore", { n: used.times })}
            </Pill>
          )}
          <Pill tone={look.tone}>{t(`liaison.category.${b.category}`)}</Pill>
        </div>
        {b.officials.length === 0
          ? officialRow(
              b,
              null,
              <span className="muted">{t("liaison.picker.noOfficial")}</span>,
              b.public_phone ? (
                <small className="mono" dir="ltr">
                  {" "}
                  {b.public_phone}
                </small>
              ) : null,
            )
          : b.officials.map((o) =>
              officialRow(
                b,
                o.id,
                <>
                  {mark(o.name)}
                  {o.role ? <> · {mark(o.role)}</> : null}
                </>,
                <small className="muted">
                  {" "}
                  <span className="mono" dir="ltr">
                    {mark(o.phones.join(" · "))}
                  </span>
                  {o.duty ? ` · ${o.duty}` : ""}
                </small>,
              ),
            )}
      </div>
    );
  };
  const byId = new Map((bodies.data ?? []).map((b) => [b.id, b]));
  const historyRows = (p?.history ?? [])
    .flatMap((h) => h.parties.map((x) => ({ h, x })))
    .filter(({ x }) => byId.has(x.body_id))
    .filter(
      ({ x }) =>
        !q ||
        `${x.body_name} ${x.official_name ?? ""}`
          .toLowerCase()
          .includes(q.toLowerCase()),
    );
  const seen = new Set<string>();
  return (
    <InlineDialog title={t("liaison.picker.title")} onClose={onClose}>
      <div className="liaison-picker">
        <div className="liaison-picker__bar">
          {central ? (
            <select
              aria-label={t("liaison.picker.gouvernorat")}
              value={gov ?? ""}
              onChange={(e) =>
                setGov(e.target.value ? Number(e.target.value) : null)
              }
            >
              <option value="">{t("liaison.national")}</option>
              {gouvernorats.list.map((g) => (
                <option key={g.code} value={g.code}>
                  {gouvernorats.nameOf(g.code)}
                </option>
              ))}
            </select>
          ) : (
            <Pill tone="navy">
              <Icon name="lockOpen" size={14} />{" "}
              {t("liaison.scope.regional", {
                gov: gouvernorats.nameOf(gov) ?? "",
              })}
            </Pill>
          )}
          <input
            type="search"
            className="liaison-picker__search"
            aria-label={t("liaison.picker.search")}
            placeholder={t("liaison.picker.search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <fieldset
            className="segmented segmented--small"
            aria-label={t("liaison.picker.view")}
          >
            {(["list", "history"] as const).map((v) => (
              <label key={v} className="segmented__item">
                <input
                  type="radio"
                  name={`${base}-view`}
                  checked={view === v}
                  onChange={() => setView(v)}
                />
                <span>{t(`liaison.picker.${v}`)}</span>
              </label>
            ))}
          </fieldset>
        </div>
        {(bodies.isLoading || picker.isLoading) && <Loading />}
        {bodies.isError && (
          <ErrorBox
            error={bodies.error}
            onRetry={() => void bodies.refetch()}
          />
        )}
        <div className="liaison-picker__list">
          {view === "list" ? (
            <>
              {top.length > 0 && (
                <>
                  <h4 className="liaison-picker__sect">
                    {t("liaison.picker.suggestedSection")}
                  </h4>
                  {top.map(block)}
                </>
              )}
              <h4 className="liaison-picker__sect">
                {q
                  ? t("liaison.picker.results", { q, n: ranked.length })
                  : t("liaison.picker.all")}
              </h4>
              {rest.map(block)}
              {bodies.data && ranked.length === 0 && (
                <p className="muted">{t("liaison.picker.none")}</p>
              )}
            </>
          ) : (
            <>
              <h4 className="liaison-picker__sect">
                {t("liaison.picker.historySection")}
              </h4>
              {historyRows.length === 0 && (
                <p className="muted">{t("liaison.picker.noHistory")}</p>
              )}
              {historyRows.map(({ h, x }) => {
                const key = `${x.body_id}:${x.official_id ?? ""}`;
                if (seen.has(key)) return null;
                seen.add(key);
                const b = byId.get(x.body_id);
                if (!b) return null;
                return (
                  <div key={key} className="liaison-pick-hist">
                    <small className="muted">
                      {t("liaison.picker.lastIn", {
                        kind: t(`category.${h.category}`),
                        date: fmt.dateTime(h.opened_at),
                      })}
                    </small>
                    {officialRow(
                      b,
                      x.official_id,
                      <>
                        <strong dir="auto">{x.body_name}</strong> ·{" "}
                        <span dir="auto">{x.official_name ?? "—"}</span>
                      </>,
                    )}
                  </div>
                );
              })}
            </>
          )}
        </div>
        {adding && (
          <ContactForm
            fixedGouvernorat={central ? gov : null}
            originIncidentId={incident.id}
            existing={bodies.data ?? []}
            onCancel={() => setAdding(false)}
            onSaved={(b) => {
              setAdding(false);
              toggle(b.id, b.officials[0]?.id ?? null, true);
            }}
          />
        )}
        <div className="liaison-picker__foot">
          {!adding && (
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setAdding(true)}
            >
              <Icon name="addLocationAlt" size={18} />{" "}
              {t("liaison.picker.addMissing")}
            </button>
          )}
          <span className="liaison-picker__count">
            <Pill tone="teal">
              {t("liaison.picker.selected", { n: selected.size })}
            </Pill>
          </span>
          <button type="button" className="btn" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={selected.size === 0 || busy}
            onClick={() =>
              onConfirm(
                [...selected.entries()].map(([bodyId, v]) => ({
                  body_id: bodyId,
                  official_id: v.official,
                  suggested: v.suggested,
                  reason: v.reason,
                })),
              )
            }
          >
            <Icon name="check" size={18} /> {t("liaison.picker.confirm")}
          </button>
        </div>
      </div>
    </InlineDialog>
  );
}
