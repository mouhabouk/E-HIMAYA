import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { awIcon, awKeys, awTone, hhmm, type AwCategory, type AwWarning } from "../lib/addressWarnings";
import { useFormat } from "../lib/hooks";
import { canManageIncidents } from "../lib/roles";
import type { IncidentDetail } from "../lib/types";
import { ErrorBox, Loading } from "./Feedback";
import { Icon, IconTile, Pill } from "./Icon";

const REVEAL_REASONS = ["call", "name", "team"] as const;

/**
 * Address warnings of an incident (OS8): the marks whose circle holds the incident, the critical ones with this kind
 * of incident first, then the nearest. The room marks them read; the team reads them on its phone with the order.
 * A personal mark gives its owner's need only; the name and phone are shown on request, with a reason, kept and
 * shown to the owner.
 */
export function AddressWarningsPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = canManageIncidents(user?.identity.roles ?? []);
  const cats = useQuery({ queryKey: awKeys.categories, queryFn: ({ signal }) => api.awCategories(signal) });
  const q = useQuery({
    queryKey: awKeys.incident(incident.id),
    queryFn: ({ signal }) => api.awIncident(incident.id, signal),
    refetchInterval: 30_000,
  });
  const ack = useMutation({
    mutationFn: (ids: string[]) => api.awAck(incident.id, ids),
    onSuccess: (data) => qc.setQueryData(awKeys.incident(incident.id), data),
  });
  const byKey = new Map((cats.data ?? []).map((c) => [c.key, c]));
  const items = q.data?.items ?? [];
  const critical = items.filter((w) => w.critical).length;
  return (
    <section
      className={`card aw-panel${critical ? " aw-panel--critical" : ""}`}
      aria-labelledby="sec-address-warnings"
    >
      <div className="aw-panel__head">
        <h2 id="sec-address-warnings">
          <IconTile name="warning" tone="amber" size="sm" /> {t("addressWarnings.panel.title")}
        </h2>
        {q.data && (
          <Pill tone={q.data.unread ? "amber" : "green"}>
            {t("addressWarnings.panel.count", { n: items.length, unread: q.data.unread })}
          </Pill>
        )}
        {critical > 0 && <Pill tone="red">{t("addressWarnings.panel.critical", { n: critical })}</Pill>}
        {canWrite && q.data && q.data.unread > 0 && (
          <button type="button" className="btn btn--small" onClick={() => ack.mutate([])} disabled={ack.isPending}>
            {t("addressWarnings.panel.ackAll")}
          </button>
        )}
      </div>
      {(q.isLoading || cats.isLoading) && <Loading />}
      {q.isError && <ErrorBox error={q.error} onRetry={() => void q.refetch()} />}
      {ack.isError && <ErrorBox error={ack.error} />}
      {q.data && items.length === 0 && <p className="muted">{t("addressWarnings.panel.none")}</p>}
      <ul className="aw-list">
        {items.map((w) => (
          <WarningRow
            key={w.marker_id}
            w={w}
            category={byKey.get(w.category)}
            incidentId={incident.id}
            kind={q.data?.incident_kind ?? incident.category}
            canWrite={canWrite}
            onAck={() => ack.mutate([w.marker_id])}
            busy={ack.isPending}
          />
        ))}
      </ul>
      <p className="muted aw-note">
        <Icon name="lockOpen" size={16} /> {t("addressWarnings.panel.note")}
      </p>
    </section>
  );
}

function WarningRow({
  w,
  category,
  incidentId,
  kind,
  canWrite,
  onAck,
  busy,
}: {
  w: AwWarning;
  category: AwCategory | undefined;
  incidentId: string;
  kind: string;
  canWrite: boolean;
  onAck: () => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const classes = ["aw-item"];
  if (w.critical) classes.push("aw-item--critical");
  if (w.off_hours) classes.push("aw-item--off");
  return (
    <li className={classes.join(" ")}>
      <IconTile name={awIcon(category)} tone={awTone(category)} />
      <div className="aw-item__body">
        <div className="aw-item__title">
          <strong>{category?.name ?? w.category}</strong>
          {w.critical && (
            <Pill tone="red">
              <Icon name="warning" size={14} /> {t("addressWarnings.panel.criticalWith", { kind: t(`category.${kind}`) })}
            </Pill>
          )}
        </div>
        <p className="aw-item__desc" dir="auto">
          {w.description}
        </p>
        <p className="muted aw-item__addr" dir="auto">
          {w.address}
        </p>
        <div className="aw-item__pills">
          <Pill tone="slate">{t("addressWarnings.panel.distance", { m: fmt.number(w.distance_m) })}</Pill>
          <Pill tone="navy">{t(`addressWarnings.source.${w.source}`)}</Pill>
          <Pill tone={w.team_visible ? "teal" : "slate"}>
            {t(w.team_visible ? "addressWarnings.panel.team" : "addressWarnings.panel.roomOnly")}
          </Pill>
          {w.personal && <Pill tone="green">{t("addressWarnings.panel.consent")}</Pill>}
          {w.hours && (
            <Pill tone={w.off_hours ? "slate" : "purple"}>
              {t(w.off_hours ? "addressWarnings.panel.offHours" : "addressWarnings.panel.onHours", {
                from: hhmm(w.hours.start),
                to: hhmm(w.hours.end),
              })}
            </Pill>
          )}
          {w.room_ack_at && (
            <Pill tone="green">
              <Icon name="check" size={14} />{" "}
              {t("addressWarnings.panel.roomRead", { who: w.room_ack_by ?? "", at: fmt.time(w.room_ack_at) })}
            </Pill>
          )}
          {w.team_ack_at && (
            <Pill tone="green">
              <Icon name="check" size={14} />{" "}
              {t("addressWarnings.panel.teamRead", { at: fmt.time(w.team_ack_at) })}
            </Pill>
          )}
        </div>
        {canWrite && (
          <div className="aw-item__acts">
            {!w.room_ack_at && (
              <button type="button" className="btn btn--small btn--primary" onClick={onAck} disabled={busy}>
                {t("addressWarnings.panel.ack")}
              </button>
            )}
            {w.personal && <Reveal incidentId={incidentId} w={w} />}
          </div>
        )}
      </div>
    </li>
  );
}

function Reveal({ incidentId, w }: { incidentId: string; w: AwWarning }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<(typeof REVEAL_REASONS)[number]>("call");
  const reveal = useMutation({
    mutationFn: () => api.awReveal(incidentId, w.marker_id, t(`addressWarnings.reveal.reason.${reason}`)),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: awKeys.incident(incidentId) });
      void qc.invalidateQueries({ queryKey: awKeys.reveals });
    },
  });
  if (reveal.data) {
    return (
      <Pill tone="amber">
        <Icon name="visibility" size={14} /> {reveal.data.name ?? t("addressWarnings.reveal.noName")} ·{" "}
        <bdi dir="ltr">{reveal.data.phone ?? "—"}</bdi>
      </Pill>
    );
  }
  if (!open) {
    return (
      <button type="button" className="btn btn--small" onClick={() => setOpen(true)}>
        {t("addressWarnings.reveal.button")}
      </button>
    );
  }
  return (
    <div className="aw-reveal" role="group" aria-label={t("addressWarnings.reveal.button")}>
      <p className="muted">{t("addressWarnings.reveal.explain")}</p>
      <div className="aw-chips">
        {REVEAL_REASONS.map((r) => (
          <button
            key={r}
            type="button"
            className={`aw-chip${r === reason ? " aw-chip--on" : ""}`}
            aria-pressed={r === reason}
            onClick={() => setReason(r)}
          >
            {t(`addressWarnings.reveal.reason.${r}`)}
          </button>
        ))}
      </div>
      <div className="form-actions">
        <button type="button" className="btn btn--small" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </button>
        <button
          type="button"
          className="btn btn--small btn--primary"
          onClick={() => reveal.mutate()}
          disabled={reveal.isPending}
        >
          {t("addressWarnings.reveal.confirm")}
        </button>
      </div>
      {reveal.isError && <ErrorBox error={reveal.error} />}
    </div>
  );
}
