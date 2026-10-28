/**
 * Resource requests across gouvernorats (phase 9 §5.4): a lead or participating room (or the central room) asks
 * another gouvernorat for resources; the owning region approves with its own resources (one assignment each) or
 * refuses; the requester may cancel. Dispatching stays with the region that owns the resources.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { errorMessageKey } from "../lib/api";
import { useFormat, useGouvernorats } from "../lib/hooks";
import { opsKeys } from "../lib/opsApi";
import { RESOURCE_KINDS, type ResourceFilters, type ResourceKind } from "../lib/opsTypes";
import { reasonValid } from "../lib/phase9";
import { p9Keys } from "../lib/phase9Api";
import type { ResourceRequest, ResourceRequestBody } from "../lib/phase9Types";
import {
  mayCancelResourceRequest,
  mayDecideResourceRequest,
  mayRequestResources,
} from "../lib/roles";
import { queryKeys } from "../lib/staffApi";
import type { IncidentDetail } from "../lib/types";
import { InlineDialog, ReasonField, useRoomName } from "./Phase9Bits";
import { Stepper } from "./Stepper";

function useRefresh() {
  const qc = useQueryClient();
  return (r: { incident_id: string }) => {
    void qc.invalidateQueries({ queryKey: p9Keys.resourceRequestsAll });
    void qc.invalidateQueries({ queryKey: queryKeys.incident(r.incident_id) });
    void qc.invalidateQueries({ queryKey: opsKeys.resourcesAll });
  };
}

export function RequestStatusTag({ status }: { status: ResourceRequest["status"] }) {
  const { t } = useTranslation();
  return <span className={`tag tag--rr-${status}`}>{t(`resourceRequests.status.${status}`)}</span>;
}

/** Approval form of the owning region: pick its available resources of the requested kind. */
function ApproveForm({ request, onDone }: { request: ResourceRequest; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const id = useId();
  const [picked, setPicked] = useState<string[]>(request.resource_id ? [request.resource_id] : []);
  const [note, setNote] = useState("");
  const kind: ResourceKind | "" = (RESOURCE_KINDS as readonly string[]).includes(request.resource_kind ?? "")
    ? (request.resource_kind as ResourceKind)
    : "";
  const filters: ResourceFilters = { status: "available", kind, gouvernorat_code: request.to_gouvernorat_code };
  const resources = useQuery({
    queryKey: opsKeys.resources(filters),
    queryFn: ({ signal }) => api.resources(filters, { signal }),
  });
  const approve = useMutation({
    mutationFn: () => api.approveResourceRequest(request.id, picked, note.trim()),
    onSuccess: (r) => {
      refresh(r);
      onDone();
    },
  });
  const items = resources.data?.items ?? [];
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        if (picked.length > 0) approve.mutate();
      }}
    >
      <fieldset>
        <legend>{t("resourceRequests.pickResources", { count: request.quantity })}</legend>
        {resources.isPending && <p className="muted">{t("common.loading")}</p>}
        {!resources.isPending && items.length === 0 && <p className="muted">{t("ops.assignment.noResource")}</p>}
        {items.map((r) => (
          <label key={r.id} className="checkbox">
            <input
              type="checkbox"
              checked={picked.includes(r.id)}
              onChange={(e) => setPicked((p) => (e.target.checked ? [...p, r.id] : p.filter((x) => x !== r.id)))}
            />{" "}
            {r.label} · {t(`resources.kind.${r.kind}`)} · {r.unit_name}
          </label>
        ))}
      </fieldset>
      <div className="field">
        <label htmlFor={`${id}-note`}>{t("resourceRequests.note")}</label>
        <textarea id={`${id}-note`} rows={2} maxLength={500} dir="auto" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <button type="submit" className="btn btn--primary" disabled={approve.isPending || picked.length === 0}>
        {t("resourceRequests.approve")}
      </button>
      {approve.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(approve.error))}
        </p>
      )}
    </form>
  );
}

function RefuseForm({ request, onDone }: { request: ResourceRequest; onDone: () => void }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const refresh = useRefresh();
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const refuse = useMutation({
    mutationFn: () => api.refuseResourceRequest(request.id, reason.trim()),
    onSuccess: (r) => {
      refresh(r);
      onDone();
    },
  });
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        setTried(true);
        if (reasonValid(reason)) refuse.mutate();
      }}
    >
      <ReasonField label={t("resourceRequests.refuseReason")} value={reason} onChange={setReason} showError={tried} />
      <button type="submit" className="btn" disabled={refuse.isPending}>
        {t("resourceRequests.refuse")}
      </button>
      {refuse.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(refuse.error))}
        </p>
      )}
    </form>
  );
}

/** One request: what, to whom, why, its state and the decisions the user may take. */
export function ResourceRequestItem({
  request,
  commandLevel,
  showIncident = false,
}: {
  request: ResourceRequest;
  commandLevel?: string | null;
  showIncident?: boolean;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const fmt = useFormat();
  const gouvernorats = useGouvernorats();
  const roomName = useRoomName();
  const refresh = useRefresh();
  const [panel, setPanel] = useState<"approve" | "refuse" | null>(null);
  const cancel = useMutation({ mutationFn: () => api.cancelResourceRequest(request.id), onSuccess: refresh });
  const identity = user?.identity;
  const canDecide = identity ? mayDecideResourceRequest(identity, request, commandLevel) : false;
  const canCancel = identity ? mayCancelResourceRequest(identity, request) : false;
  const what = request.resource_kind
    ? t(`resources.kind.${request.resource_kind}`, { defaultValue: request.resource_kind })
    : t("resourceRequests.specificResource");
  return (
    <li className="rr-item">
      <p>
        <RequestStatusTag status={request.status} />{" "}
        <strong>{t("resourceRequests.summary", { quantity: request.quantity, what })}</strong>{" "}
        <span className="muted">
          {t("resourceRequests.fromTo", {
            from: roomName(request.from_room),
            to: gouvernorats.nameOf(request.to_gouvernorat_code) ?? String(request.to_gouvernorat_code),
          })}
        </span>
        {showIncident && (
          <>
            {" · "}
            <Link to={`/incidents/${encodeURIComponent(request.incident_id)}`}>{t("resourceRequests.openIncident")}</Link>
          </>
        )}
      </p>
      <p dir="auto">{request.reason}</p>
      <p className="muted">
        {t("resourceRequests.requestedBy", {
          name: request.requested_by_name ?? t("claim.someone"),
          at: fmt.dateTime(request.requested_at),
        })}
        {request.decided_at &&
          ` · ${t("resourceRequests.decidedBy", {
            name: request.decided_by_name ?? t("claim.someone"),
            at: fmt.dateTime(request.decided_at),
          })}`}
      </p>
      {request.decision_note && (
        <p className="timeline__note" dir="auto">
          {request.decision_note}
        </p>
      )}
      <div className="actions">
        {canDecide && (
          <>
            <button type="button" className="btn btn--primary btn--small" onClick={() => setPanel("approve")}>
              {t("resourceRequests.approve")}
            </button>
            <button type="button" className="btn btn--small" onClick={() => setPanel("refuse")}>
              {t("resourceRequests.refuse")}
            </button>
          </>
        )}
        {canCancel && (
          <button type="button" className="btn btn--small" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
            {t("resourceRequests.cancel")}
          </button>
        )}
      </div>
      {cancel.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(cancel.error))}
        </p>
      )}
      {panel === "approve" && (
        <InlineDialog title={t("resourceRequests.approveTitle")} onClose={() => setPanel(null)}>
          <ApproveForm request={request} onDone={() => setPanel(null)} />
        </InlineDialog>
      )}
      {panel === "refuse" && (
        <InlineDialog title={t("resourceRequests.refuseTitle")} onClose={() => setPanel(null)}>
          <RefuseForm request={request} onDone={() => setPanel(null)} />
        </InlineDialog>
      )}
    </li>
  );
}

function NewRequestForm({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const refresh = useRefresh();
  const id = useId();
  const own = user?.identity.gouvernoratCode ?? null;
  const [to, setTo] = useState("");
  const [kind, setKind] = useState<ResourceKind | "">("");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState("");
  const [tried, setTried] = useState(false);
  const [sent, setSent] = useState(false);
  const create = useMutation({
    mutationFn: (b: ResourceRequestBody) => api.createResourceRequest(incident.id, b),
    onSuccess: (r) => {
      refresh(r);
      setTo("");
      setKind("");
      setQuantity(1);
      setReason("");
      setTried(false);
      setSent(true);
    },
  });
  const valid = to !== "" && kind !== "" && Number.isInteger(quantity) && quantity >= 1 && quantity <= 50 && reasonValid(reason);
  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    setTried(true);
    setSent(false);
    if (!valid) return;
    create.mutate({ to_gouvernorat_code: Number(to), resource_id: null, resource_kind: kind, quantity, reason: reason.trim() });
  };
  return (
    <form noValidate onSubmit={submit} className="rr-form">
      <h3>{t("resourceRequests.newTitle")}</h3>
      <div className="field">
        <label htmlFor={`${id}-to`}>{t("resourceRequests.to")}</label>
        <select id={`${id}-to`} value={to} onChange={(e) => setTo(e.target.value)} aria-invalid={tried && !to ? true : undefined}>
          <option value="">{t("referral.choose")}</option>
          {gouvernorats.list
            .filter((g) => g.code !== own)
            .map((g) => (
              <option key={g.code} value={g.code}>
                {gouvernorats.nameOf(g.code)}
              </option>
            ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={`${id}-kind`}>{t("resourceRequests.kind")}</label>
        <select
          id={`${id}-kind`}
          value={kind}
          onChange={(e) => setKind(e.target.value as ResourceKind | "")}
          aria-invalid={tried && !kind ? true : undefined}
        >
          <option value="">{t("referral.choose")}</option>
          {RESOURCE_KINDS.map((k) => (
            <option key={k} value={k}>
              {t(`resources.kind.${k}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="field field--number">
        <label htmlFor={`${id}-qty`}>{t("resourceRequests.quantity")}</label>
        <Stepper id={`${id}-qty`} min={1} max={50} value={quantity} label={t("resourceRequests.quantity")} onChange={setQuantity} />
      </div>
      <ReasonField label={t("resourceRequests.reason")} value={reason} onChange={setReason} showError={tried} />
      <button type="submit" className="btn btn--primary" disabled={create.isPending}>
        {t("resourceRequests.submit")}
      </button>
      <div role="status" aria-live="polite">
        {sent && <p className="alert alert--ok">{t("resourceRequests.sent")}</p>}
      </div>
      {create.isError && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(create.error))}
        </p>
      )}
    </form>
  );
}

/** Requests of an incident, with the form to ask another gouvernorat. */
export function ResourceRequestsPanel({ incident }: { incident: IncidentDetail }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const requests = incident.resource_requests ?? [];
  const canCreate = user ? mayRequestResources(user.identity, incident) && incident.status === "open" : false;
  return (
    <section className="card" aria-labelledby="sec-rr">
      <h2 id="sec-rr">{t("resourceRequests.title")}</h2>
      {user?.identity.national && <p className="muted">{t("resourceRequests.centralNotice")}</p>}
      {requests.length === 0 ? (
        <p className="muted">{t("resourceRequests.none")}</p>
      ) : (
        <ul className="rr-list">
          {requests.map((r) => (
            <ResourceRequestItem key={r.id} request={r} commandLevel={incident.command_level ?? null} />
          ))}
        </ul>
      )}
      {canCreate && <NewRequestForm incident={incident} />}
    </section>
  );
}
