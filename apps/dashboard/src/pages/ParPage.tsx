import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ErrorBox, Loading } from "../components/Feedback";
import { Icon, IconTile, Pill } from "../components/Icon";
import { PageTitle } from "../components/PageTitle";
import { Stepper } from "../components/Stepper";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useCan } from "../lib/features";
import { useFormat, useGouvernorats } from "../lib/hooks";
import {
  PAR_AUTO_EVENTS,
  PAR_CHECK_ALL_WHY,
  PAR_HOT,
  PAR_MAX_AHEAD_MIN,
  PAR_PAUSE_WHY,
  PAR_SITUATION_TONE,
  PAR_STATUS_TONE,
  PAR_WARM,
  mmss,
  nextAt,
  parErrorCode,
  parKeys,
  remainingNow,
  type ParAutoEvent,
  type ParBoard,
  type ParCheckAllWhy,
  type ParPauseWhy,
  type ParSetting,
  type ParTeam,
} from "../lib/par";
import { canManageIncidents } from "../lib/roles";

type Tab = "live" | "settings" | "archive";

/**
 * Crew accountability in danger zones (PAR, OS7, docs/phase-os7/design-os7.md), an optional module. The operations
 * commander and the rooms follow the teams inside a danger zone: the time each has left to confirm that it is complete,
 * the members out for a while, a missing resource with who had it, the leader's word from the scene and the log. They
 * set a time for the next check, pause the check with its reason and resume it, call a general check, and end the
 * check once every team is out: it is archived with the intervention.
 */
export function ParPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("live");
  return (
    <div className="page">
      <PageTitle print icon="groups" tone="red">
        {t("par.title")}
      </PageTitle>
      <p className="muted">{t("par.intro")}</p>
      <div className="aw-tabs" role="group" aria-label={t("par.title")}>
        {(["live", "settings", "archive"] as const).map((k) => (
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}>
            {t(`par.tab.${k}`)}
          </button>
        ))}
      </div>
      {tab === "live" && <Incidents closed={false} />}
      {tab === "settings" && <Settings />}
      {tab === "archive" && <Incidents closed />}
    </div>
  );
}

function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(id);
  }, [ms]);
  return now;
}

function RefusalBox({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const code = parErrorCode(error);
  if (code && t(`par.error.${code}`, { defaultValue: "" })) {
    return (
      <p className="alert alert--error" role="alert">
        {t(`par.error.${code}`)}
      </p>
    );
  }
  return <ErrorBox error={error} />;
}

// ---------------------------------------------------------------- the incidents

function Incidents({ closed }: { closed: boolean }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const gouvernorats = useGouvernorats();
  const [chosen, setChosen] = useState<string | null>(null);
  const list = useQuery({
    queryKey: parKeys.incidents(closed),
    queryFn: ({ signal }) => api.parIncidents(closed, signal),
    refetchInterval: closed ? false : 10_000,
  });
  const rows = (list.data ?? []).filter((r) => r.closed === closed);
  const current = chosen ?? (rows.length === 1 ? rows[0]?.incident_id ?? null : null);
  if (list.isLoading) return <Loading />;
  if (list.isError) return <ErrorBox error={list.error} onRetry={() => void list.refetch()} />;
  return (
    <>
      {rows.length === 0 ? (
        <p className="card muted">{t(closed ? "par.noArchive" : "par.noTeams")}</p>
      ) : (
        <ul className="par-incidents" aria-label={t(closed ? "par.tab.archive" : "par.tab.live")}>
          {rows.map((r) => (
            <li key={r.incident_id}>
              <button
                type="button"
                className="par-incident card"
                aria-pressed={current === r.incident_id}
                onClick={() => setChosen(r.incident_id)}
              >
                <IconTile name="localFireDepartment" tone={r.alarms || r.missing_open ? "red" : "navy"} />
                <span className="par-incident__body">
                  <strong>
                    {t(`category.${r.incident_kind}`)} ·{" "}
                    {gouvernorats.nameOf(r.gouvernorat_code) ?? "—"}
                  </strong>
                  <span className="par-pills">
                    <Pill tone="navy">{t("par.row.teams", { n: r.teams_in })}</Pill>
                    <Pill tone="navy">{t("par.row.agents", { n: r.agents_in })}</Pill>
                    {r.alarms > 0 && <Pill tone="red">{t("par.row.alarms", { n: r.alarms })}</Pill>}
                    {r.missing_open > 0 && <Pill tone="red">{t("par.row.missing", { n: r.missing_open })}</Pill>}
                    {r.last_sitrep && (
                      <Pill tone={PAR_SITUATION_TONE[r.last_sitrep]}>{t(`par.situation.${r.last_sitrep}`)}</Pill>
                    )}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {current && <Board incidentId={current} />}
    </>
  );
}

// ---------------------------------------------------------------- the board of one incident

function Board({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const qc = useQueryClient();
  const now = useNow();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const canTiming = useCan("par.timing", canWrite);
  const canTeams = useCan("par.teams", canWrite);
  const canClose = useCan("par.close", canWrite);
  const board = useQuery({
    queryKey: parKeys.board(incidentId),
    queryFn: ({ signal }) => api.parBoard(incidentId, signal),
    refetchInterval: 5_000,
  });
  const act = useMutation({
    mutationFn: (run: () => Promise<ParBoard>) => run(),
    onSuccess: (b) => {
      qc.setQueryData(parKeys.board(incidentId), b);
      void qc.invalidateQueries({ queryKey: ["par", "incidents"] });
    },
  });
  if (board.isLoading) return <Loading />;
  if (board.isError) return <ErrorBox error={board.error} onRetry={() => void board.refetch()} />;
  const b = board.data;
  if (!b) return null;
  const closed = b.closure !== null;
  const inside = b.teams.filter((x) => x.out_at === null);
  const alarms = inside.filter((x) => x.status === "alarm");
  const run = (f: () => Promise<ParBoard>) => act.mutate(f);
  return (
    <section className="par-board" aria-label={t("par.board.title")}>
      <h2 className="par-board__title">
        {t("par.board.title")} · {t(`category.${b.incident_kind}`)}
      </h2>
      {alarms.map((x) => (
        <div key={x.id} className="alert alert--error par-alarm" role="alert">
          <Icon name="crisisAlert" size={20} /> {t("par.board.alarm", { team: x.label, late: mmss(-(remainingNow(x, b.now, now) ?? 0)) })}
        </div>
      ))}
      {act.isError && <RefusalBox error={act.error} />}
      {closed && b.closure && (
        <div className="card par-closed">
          <IconTile name="folderOpen" tone="navy" />
          <div>
            <strong>{t(b.closure.automatic ? "par.closure.automatic" : "par.closure.manual")}</strong>
            <p className="muted">
              {t("par.closure.summary", {
                at: fmt.dateTime(b.closure.closed_at),
                by: b.closure.closed_by_name ?? "—",
                teams: b.closure.summary.teams ?? 0,
                agents: b.closure.summary.agents ?? 0,
              })}
            </p>
          </div>
        </div>
      )}
      <ul className="kpis par-kpis">
        <Kpi icon="groups" tone="red" value={b.kpis.agents_in} label={t("par.kpi.agents")} />
        <Kpi icon="localShipping" tone="navy" value={b.kpis.teams_in} label={t("par.kpi.teams")} />
        <Kpi icon="check" tone={b.kpis.not_confirmed ? "red" : "green"} value={b.kpis.not_confirmed} label={t("par.kpi.notConfirmed")} />
        <Kpi icon="warning" tone={b.kpis.missing_open ? "red" : "slate"} value={b.kpis.missing_open} label={t("par.kpi.missing")} />
      </ul>
      <div className="par-grid">
        <div className="par-teams">
          {b.teams.map((team) => (
            <TeamCard
              key={team.id}
              team={team}
              left={remainingNow(team, b.now, now)}
              canAct={canTeams && !closed}
              onAct={(action) => run(() => api.parTeam(incidentId, team.id, action))}
            />
          ))}
          {b.teams.length === 0 && <p className="card muted">{t("par.noTeams")}</p>}
        </div>
        <div className="par-side">
          {b.missing.length > 0 && (
            <MissingCard
              board={b}
              canAct={canTeams && !closed}
              onAct={(id, action) => run(() => api.parMissing(incidentId, id, action))}
            />
          )}
          <SitrepCard board={b} />
          <LogCard board={b} />
        </div>
      </div>
      {!closed && canTiming && inside.length > 0 && (
        <div className="par-controls">
          <NextCard board={b} busy={act.isPending} onApply={(at, team) => run(() => api.parSetNext(incidentId, at, team))} onClear={(team) => run(() => api.parClearNext(incidentId, team))} />
          <PauseCard
            board={b}
            busy={act.isPending}
            onPause={(why, detail, team) => run(() => api.parPause(incidentId, why, detail, team))}
            onResume={(team) => run(() => api.parResume(incidentId, team))}
          />
          <CheckAllCard busy={act.isPending} onPick={(why) => run(() => api.parCheckAll(incidentId, why))} />
        </div>
      )}
      {!closed && canClose && b.teams.length > 0 && (
        <div className="card par-end">
          <IconTile name="logout" tone={b.all_out ? "green" : "slate"} />
          <div>
            <strong>{t("par.end.title")}</strong>
            <p className="muted">{t(b.all_out ? "par.end.ready" : "par.end.notYet")}</p>
          </div>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!b.all_out || b.kpis.missing_open > 0 || act.isPending}
            onClick={() => run(() => api.parClose(incidentId))}
          >
            <Icon name="folderOpen" size={18} /> {t("par.end.button")}
          </button>
        </div>
      )}
    </section>
  );
}

function Kpi({ icon, tone, value, label }: { icon: Parameters<typeof IconTile>[0]["name"]; tone: Parameters<typeof IconTile>[0]["tone"]; value: number; label: string }) {
  return (
    <li className="card par-kpi">
      <IconTile name={icon} tone={tone} />
      <span>
        <span className="kpi__value">{value}</span>
        <span className="kpi__label">{label}</span>
      </span>
    </li>
  );
}

function TeamCard({
  team,
  left,
  canAct,
  onAct,
}: {
  team: ParTeam;
  left: number | null;
  canAct: boolean;
  onAct: (action: "radio" | "confirm" | "out") => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const tone = PAR_STATUS_TONE[team.status];
  const live = team.out_at === null;
  const share = left === null ? 0 : Math.max(0, Math.min(1, left / team.interval_s));
  return (
    <article className={`card par-team par-team--${tone}`} aria-label={team.label}>
      <header className="par-team__head">
        <IconTile name={team.zone === "hot" ? "localFireDepartment" : "warning"} tone={team.zone === "hot" ? "red" : "amber"} />
        <div>
          <h3>{team.label}</h3>
          <p className="muted">
            {team.task ?? "—"}
            {team.leader_name ? ` · ${team.leader_name}` : ""}
          </p>
        </div>
      </header>
      <p className="par-pills">
        <Pill tone={tone}>{t(`par.status.${team.status}`)}</Pill>
        <Pill tone={team.zone === "hot" ? "red" : "amber"}>{t(`par.zone.${team.zone}`)}</Pill>
        <Pill tone="slate">
          <Icon name="groups" size={14} /> {t("par.team.present", { present: team.present, total: team.members.length })}
        </Pill>
      </p>
      {live ? (
        <div className="par-timer" role="timer" aria-live="off">
          <span className="par-timer__value">{team.status === "paused" ? "‖" : left === null ? "—" : mmss(left)}</span>
          <span className="muted">
            {team.status === "paused"
              ? t("par.team.paused", { reason: team.pause_reason ?? "" })
              : t("par.team.due")}
            {team.next_at && ` · ${t("par.team.special", { at: fmt.time(team.next_at) })}`}
            {` · ${t("par.team.last", { at: fmt.time(team.last_confirmed_at) })}`}
          </span>
          <span className="par-timer__bar" aria-hidden="true">
            <span style={{ inlineSize: `${Math.round(share * 100)}%` }} />
          </span>
        </div>
      ) : (
        <p className="muted">{t("par.team.out", { at: team.out_at ? fmt.time(team.out_at) : "—", n: team.out_count ?? team.members.length })}</p>
      )}
      <ul className="par-members" aria-label={t("par.team.members")}>
        {team.members.map((m) => (
          <li key={m.key} className={m.away_why ? "par-member par-member--away" : "par-member"}>
            {m.name}
            {m.away_why && ` · ${t(`par.away.${m.away_why}`)}`}
          </li>
        ))}
      </ul>
      {live && canAct && (
        <div className="par-actions">
          <button type="button" className="btn" onClick={() => onAct("radio")}>
            <Icon name="call" size={18} /> {t("par.team.radio")}
          </button>
          <button type="button" className="btn" onClick={() => onAct("confirm")} disabled={team.status === "paused"}>
            <Icon name="check" size={18} /> {t("par.team.confirm")}
          </button>
          <button type="button" className="btn" onClick={() => onAct("out")}>
            <Icon name="logout" size={18} /> {t("par.team.recordOut")}
          </button>
        </div>
      )}
    </article>
  );
}

function MissingCard({
  board,
  canAct,
  onAct,
}: {
  board: ParBoard;
  canAct: boolean;
  onAct: (id: string, action: "replacement" | "recovered") => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="healthAndSafety" tone="red" /> {t("par.missing.title")}
      </h3>
      <ul className="par-list">
        {board.missing.map((m) => (
          <li key={m.id}>
            <strong>{m.resource}</strong> · {t("par.missing.carrier", { name: m.carrier, team: m.team_label })}
            <span className="muted">
              {" "}
              · {fmt.time(m.reported_at)}
              {m.place ? ` · ${m.place}` : ""}
            </span>
            <span className="par-pills">
              {m.recovered_at ? (
                <Pill tone="green">{t("par.missing.recovered", { at: fmt.time(m.recovered_at) })}</Pill>
              ) : m.replacement_at ? (
                <Pill tone="amber">{t("par.missing.replacementSent")}</Pill>
              ) : (
                <Pill tone="red">{t("par.missing.open")}</Pill>
              )}
            </span>
            {canAct && !m.recovered_at && (
              <span className="par-actions">
                {!m.replacement_at && (
                  <button type="button" className="btn" onClick={() => onAct(m.id, "replacement")}>
                    {t("par.missing.sendReplacement")}
                  </button>
                )}
                <button type="button" className="btn" onClick={() => onAct(m.id, "recovered")}>
                  {t("par.missing.markRecovered")}
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function SitrepCard({ board }: { board: ParBoard }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="campaign" tone="navy" /> {t("par.sitrep.title")}
      </h3>
      {board.sitreps.length === 0 ? (
        <p className="muted">{t("par.sitrep.none")}</p>
      ) : (
        <ul className="par-list">
          {board.sitreps.map((s) => (
            <li key={s.id}>
              <span className="par-pills">
                <Pill tone={PAR_SITUATION_TONE[s.situation]}>{t(`par.situation.${s.situation}`)}</Pill>
                {s.reinforcement && <Pill tone="red">{t("par.sitrep.reinforcement")}</Pill>}
                {s.voice_seconds && (
                  <Pill tone="slate">
                    <Icon name="mic" size={14} /> {t(s.edited ? "par.sitrep.voiceEdited" : "par.sitrep.voice")}
                  </Pill>
                )}
              </span>
              <strong>{s.team_label}</strong> · <span className="muted">{fmt.time(s.at)}</span>
              {s.text && <p className="par-sitrep__text">{s.text}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function LogCard({ board }: { board: ParBoard }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="historyEdu" tone="navy" /> {t("par.log.title")}
      </h3>
      <ol className="par-log">
        {board.events.slice(0, 40).map((e, i) => (
          <li key={`${e.at}-${i}`} className={`par-log__${e.kind}`}>
            <time dateTime={e.at}>{fmt.time(e.at)}</time> <span>{e.text}</span>
            {e.by_name && <span className="muted"> · {e.by_name}</span>}
          </li>
        ))}
      </ol>
      <p className="muted">{t("par.log.kept")}</p>
    </section>
  );
}

// ---------------------------------------------------------------- the commander's and the room's controls

function TeamSelect({ board, value, onChange, label }: { board: ParBoard; value: string; onChange: (v: string) => void; label: string }) {
  const { t } = useTranslation();
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t("par.allTeams")}</option>
      {board.teams
        .filter((x) => x.out_at === null)
        .map((x) => (
          <option key={x.id} value={x.id}>
            {x.label}
          </option>
        ))}
    </select>
  );
}

/** A small hour and minute picker (Yamen 2026-11-12): no typing, the past and more than 12 hours ahead are blocked. */
export function TimePicker({ value, onChange, now }: { value: Date | null; onChange: (d: Date) => void; now: Date }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const [open, setOpen] = useState(false);
  const base = useId();
  const ok = (h: number, m: number) => {
    const d = nextAt(h, m, now);
    return (d.getTime() - now.getTime()) / 60_000 <= PAR_MAX_AHEAD_MIN;
  };
  const start = value ?? new Date(now.getTime() + 5 * 60_000);
  const [h, setH] = useState(start.getHours());
  const [m, setM] = useState(start.getMinutes());
  const panel = useRef<HTMLDivElement>(null);
  // The chosen hour and minute stay in view in their columns (without scrolling the page).
  useEffect(() => {
    if (!open) return;
    panel.current?.querySelectorAll<HTMLElement>('[aria-selected="true"]').forEach((el) => {
      const col = el.parentElement;
      if (col) col.scrollTop = el.offsetTop - col.offsetTop - col.clientHeight / 2 + el.clientHeight / 2;
    });
  }, [open, h, m]);
  const pick = (hh: number, mm: number) => {
    setH(hh);
    setM(mm);
  };
  const minutesOk = (hh: number) => Array.from({ length: 60 }, (_, i) => i).filter((mm) => ok(hh, mm));
  const two = (n: number) => String(n).padStart(2, "0");
  return (
    <div className="par-tp">
      <button
        type="button"
        className="par-tp__field"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={`${base}-panel`}
        onClick={() => setOpen((o) => !o)}
      >
        <Icon name="schedule" size={18} /> {value ? fmt.time(value.toISOString()) : t("par.next.choose")}
      </button>
      {open && (
        <div ref={panel} className="par-tp__panel card" id={`${base}-panel`} role="dialog" aria-label={t("par.next.pickTitle")}>
          <p className="par-tp__head">
            <strong>{t("par.next.pickTitle")}</strong>
            <span className="muted">{t("par.next.now", { at: fmt.time(now.toISOString()) })}</span>
          </p>
          <div className="par-tp__quick">
            {[5, 10, 15, 30].map((q) => {
              const d = new Date(now.getTime() + q * 60_000);
              return (
                <button key={q} type="button" className="aw-chip" onClick={() => pick(d.getHours(), d.getMinutes())}>
                  {t("par.next.plus", { n: q })}
                </button>
              );
            })}
          </div>
          <div className="par-tp__cols">
            <div role="listbox" aria-label={t("par.next.hour")} className="par-tp__col">
              {Array.from({ length: 24 }, (_, i) => i).map((hh) => {
                const any = minutesOk(hh).length > 0;
                return (
                  <button
                    key={hh}
                    type="button"
                    role="option"
                    aria-selected={hh === h}
                    disabled={!any}
                    onClick={() => pick(hh, ok(hh, m) ? m : (minutesOk(hh)[0] ?? 0))}
                  >
                    {two(hh)}
                  </button>
                );
              })}
            </div>
            <div role="listbox" aria-label={t("par.next.minute")} className="par-tp__col">
              {Array.from({ length: 60 }, (_, i) => i).map((mm) => (
                <button key={mm} type="button" role="option" aria-selected={mm === m} disabled={!ok(h, mm)} onClick={() => pick(h, mm)}>
                  {two(mm)}
                </button>
              ))}
            </div>
          </div>
          <div className="par-actions">
            <button
              type="button"
              className="btn btn--primary"
              disabled={!ok(h, m)}
              onClick={() => {
                onChange(nextAt(h, m, now));
                setOpen(false);
              }}
            >
              {t("par.next.ok")}
            </button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>
              {t("common.close")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function NextCard({
  board,
  busy,
  onApply,
  onClear,
}: {
  board: ParBoard;
  busy: boolean;
  onApply: (at: string, team: string | null) => void;
  onClear: (team: string | null) => void;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const tick = useNow(15_000);
  const now = useMemo(() => new Date(tick), [tick]);
  const [team, setTeam] = useState("");
  const [at, setAt] = useState<Date | null>(null);
  const special = board.teams.filter((x) => x.out_at === null && x.next_at);
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="schedule" tone="navy" /> {t("par.next.title")}
      </h3>
      <p className="muted">{t("par.next.help")}</p>
      <div className="par-form">
        <TeamSelect board={board} value={team} onChange={setTeam} label={t("par.team.label")} />
        <TimePicker value={at} onChange={setAt} now={now} />
        <button
          type="button"
          className="btn btn--primary"
          disabled={!at || at.getTime() <= now.getTime() || busy}
          onClick={() => at && onApply(at.toISOString(), team || null)}
        >
          {t("par.next.apply")}
        </button>
      </div>
      {special.length === 0 ? (
        <p className="muted">{t("par.next.none")}</p>
      ) : (
        <ul className="par-list">
          {special.map((x) => (
            <li key={x.id}>
              {t("par.next.set", { team: x.label, at: x.next_at ? fmt.time(x.next_at) : "" })}{" "}
              <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => onClear(x.id)}>
                {t("par.next.clear")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PauseCard({
  board,
  busy,
  onPause,
  onResume,
}: {
  board: ParBoard;
  busy: boolean;
  onPause: (why: ParPauseWhy, detail: string | null, team: string | null) => void;
  onResume: (team: string | null) => void;
}) {
  const { t } = useTranslation();
  const [team, setTeam] = useState("");
  const [why, setWhy] = useState<ParPauseWhy | null>(null);
  const [detail, setDetail] = useState("");
  const paused = board.teams.filter((x) => x.out_at === null && x.paused_at);
  const needsText = why === "other" && detail.trim().length < 2;
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="stop" tone="slate" /> {t("par.pause.title")}
      </h3>
      <p className="muted">{t("par.pause.help")}</p>
      <TeamSelect board={board} value={team} onChange={setTeam} label={t("par.team.label")} />
      <fieldset className="par-chips">
        <legend>
          {t("par.pause.reason")} <span className="required">*</span>
        </legend>
        {PAR_PAUSE_WHY.map((w) => (
          <button key={w} type="button" className={why === w ? "aw-chip aw-chip--on" : "aw-chip"} aria-pressed={why === w} onClick={() => setWhy(w)}>
            {t(`par.pauseWhy.${w}`)}
          </button>
        ))}
      </fieldset>
      {why === "other" && (
        <textarea
          aria-label={t("par.pause.detail")}
          placeholder={t("par.pause.detail")}
          maxLength={300}
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
        />
      )}
      <div className="par-actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!why || needsText || busy}
          onClick={() => why && onPause(why, detail.trim() || null, team || null)}
        >
          <Icon name="stop" size={18} /> {t("par.pause.button")}
        </button>
        {paused.length > 0 && (
          <button type="button" className="btn" disabled={busy} onClick={() => onResume(team || null)}>
            <Icon name="playArrow" size={18} /> {t("par.pause.resume")}
          </button>
        )}
      </div>
    </section>
  );
}

function CheckAllCard({ busy, onPick }: { busy: boolean; onPick: (why: ParCheckAllWhy) => void }) {
  const { t } = useTranslation();
  return (
    <section className="card par-card">
      <h3 className="par-card__title">
        <IconTile name="campaign" tone="amber" /> {t("par.checkAll.title")}
      </h3>
      <p className="muted">{t("par.checkAll.help")}</p>
      <div className="par-chips">
        {PAR_CHECK_ALL_WHY.map((w) => (
          <button key={w} type="button" className="btn" disabled={busy} onClick={() => onPick(w)}>
            {t(`par.checkAllWhy.${w}`)}
          </button>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- settings

function Settings() {
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = useCan("par.settings", canManageIncidents(user?.identity.roles ?? []));
  const setting = useQuery({ queryKey: parKeys.setting, queryFn: ({ signal }) => api.parSetting(signal) });
  if (setting.isLoading) return <Loading />;
  if (setting.isError) return <ErrorBox error={setting.error} onRetry={() => void setting.refetch()} />;
  if (!setting.data) return null;
  return (
    <SettingsForm
      key={setting.data.updated_at ?? "default"}
      initial={setting.data}
      canWrite={canWrite && setting.data.gouvernorat_code !== null}
      onSaved={(s) => qc.setQueryData(parKeys.setting, s)}
      save={(body) => api.parSaveSetting(body)}
    />
  );
}

function SettingsForm({
  initial,
  canWrite,
  onSaved,
  save,
}: {
  initial: ParSetting;
  canWrite: boolean;
  onSaved: (s: ParSetting) => void;
  save: (body: { hot_s: number; warm_s: number; grace_s: number; auto_events: ParAutoEvent[] }) => Promise<ParSetting>;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const base = useId();
  const [hot, setHot] = useState(initial.hot_s);
  const [warm, setWarm] = useState(initial.warm_s);
  const [grace, setGrace] = useState(initial.grace_s);
  const [auto, setAuto] = useState<ParAutoEvent[]>(initial.auto_events);
  const mutation = useMutation({ mutationFn: save, onSuccess: onSaved });
  const seg = (values: readonly number[], value: number, set: (v: number) => void, label: string) => (
    <div className="aw-tabs" role="group" aria-label={label}>
      {values.map((v) => (
        <button key={v} type="button" aria-pressed={value === v} disabled={!canWrite} onClick={() => set(v)}>
          {t("par.settings.minutes", { n: v / 60 })}
        </button>
      ))}
    </div>
  );
  return (
    <div className="par-settings">
      <section className="card par-card">
        <h3 className="par-card__title">
          <IconTile name="schedule" tone="navy" /> {t("par.settings.interval")}
        </h3>
        <div className="par-row">
          <div>
            <strong>{t("par.zone.hot")}</strong>
            <p className="muted">{t("par.settings.hotHelp")}</p>
          </div>
          {seg(PAR_HOT, hot, setHot, t("par.zone.hot"))}
        </div>
        <div className="par-row">
          <div>
            <strong>{t("par.zone.warm")}</strong>
            <p className="muted">{t("par.settings.warmHelp")}</p>
          </div>
          {seg(PAR_WARM, warm, setWarm, t("par.zone.warm"))}
        </div>
        <div className="par-row">
          <div>
            <label htmlFor={`${base}-grace`}>
              <strong>{t("par.settings.grace")}</strong>
            </label>
            <p className="muted">{t("par.settings.graceHelp")}</p>
          </div>
          <Stepper
            id={`${base}-grace`}
            min={30}
            max={180}
            step={15}
            value={grace}
            unit={t("par.settings.seconds")}
            disabled={!canWrite}
            onChange={setGrace}
          />
        </div>
        <p className="muted">{t("par.settings.appliesNext")}</p>
      </section>
      <section className="card par-card">
        <h3 className="par-card__title">
          <IconTile name="campaign" tone="amber" /> {t("par.settings.auto")}
        </h3>
        {PAR_AUTO_EVENTS.map((ev) => (
          <label key={ev} className="par-row par-switch">
            <span>
              <strong>{t(`par.autoEvent.${ev}`)}</strong>
            </span>
            <input
              type="checkbox"
              role="switch"
              disabled={!canWrite}
              checked={auto.includes(ev)}
              onChange={(e) => setAuto(e.target.checked ? [...auto, ev] : auto.filter((x) => x !== ev))}
            />
          </label>
        ))}
      </section>
      {initial.updated_at && (
        <p className="muted">{t("par.settings.updated", { at: fmt.dateTime(initial.updated_at), by: initial.updated_by_name ?? "—" })}</p>
      )}
      {!canWrite && <p className="muted">{t("par.settings.readOnly")}</p>}
      {mutation.isError && <RefusalBox error={mutation.error} />}
      {mutation.isSuccess && <p className="alert alert--success">{t("par.settings.saved")}</p>}
      {canWrite && (
        <div className="par-actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate({ hot_s: hot, warm_s: warm, grace_s: grace, auto_events: auto })}
          >
            {t("par.settings.save")}
          </button>
        </div>
      )}
    </div>
  );
}
