import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useId, useMemo, useState, type ReactNode, type SyntheticEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { ErrorBox, Loading } from "../components/Feedback";
import { LazyPolygonDrawMap } from "../components/LazyPolygonMap";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { directionOf } from "../i18n";
import { errorMessageKey, isApiError } from "../lib/api";
import { useFormat, useGouvernorats, useLanguage } from "../lib/hooks";
import { initialBoundsFor } from "../lib/mapStyle";
import {
  BODY_MAX,
  emptyForm,
  formFromMessage,
  smsPreview,
  TITLE_MAX,
  toMessageBody,
  validateForm,
  type FormErrors,
  type MessageForm,
} from "../lib/messageForm";
import { opsKeys } from "../lib/opsApi";
import {
  ALERT_CATEGORIES,
  AUDIENCES,
  CHANNELS,
  HAZARDS,
  SEVERITIES,
  TIP_LANGUAGES,
  TOPICS,
  type Message,
  type MessageKind,
  type UserLookup,
} from "../lib/opsTypes";
import { addVertex, MAX_VERTICES, undoVertex, verticesBounds } from "../lib/polygon";
import { canDraftMessage, canPublishMessage } from "../lib/roles";
import { MessageKindTag, MessageStatusTag, StatsText, TargetText } from "./NotificationsPage";

const LANGS = TIP_LANGUAGES;
const LANG_DIR = { ar: "rtl", fr: "ltr", en: "ltr" } as const;

function FieldError({ id, error }: { id: string; error: string | undefined }) {
  const { t } = useTranslation();
  if (!error) return null;
  return (
    <p id={`${id}-error`} className="field__error">
      {t(`notify.validation.${error}`)}
    </p>
  );
}

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      <FieldError id={id} error={error} />
    </div>
  );
}

/** Area of an alert: gouvernorats (none = national) or a polygon drawn on the map. */
function AreaEditor({
  form,
  setForm,
  errors,
  disabled,
}: {
  form: MessageForm;
  setForm: (patch: Partial<MessageForm>) => void;
  errors: FormErrors;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const { mapStyleUrl } = useServices();
  const { user } = useAuth();
  const lang = useLanguage();
  const fmt = useFormat();
  const base = useId();
  const [drawing, setDrawing] = useState(form.vertices.length === 0);
  const [bounds] = useState(
    () => verticesBounds(form.vertices) ?? initialBoundsFor(user?.identity.gouvernoratCode ?? null),
  );
  return (
    <fieldset className="area-editor" disabled={disabled}>
      <legend>{t("notify.area.legend")}</legend>
      <div className="segmented">
        {(["gouvernorats", "polygon"] as const).map((mode) => (
          <label key={mode} className="segmented__item">
            <input
              type="radio"
              name={`${base}-mode`}
              checked={form.areaMode === mode}
              onChange={() => setForm({ areaMode: mode })}
            />
            <span>{t(`notify.area.mode.${mode}`)}</span>
          </label>
        ))}
      </div>
      {form.areaMode === "gouvernorats" ? (
        <GouvernoratTargets form={form} setForm={setForm} />
      ) : (
        <div className="area-draw">
          <p className="muted" id={`${base}-help`}>
            {t("notify.area.drawHelp", { max: MAX_VERTICES })}
          </p>
          <Suspense fallback={<Loading />}>
            <LazyPolygonDrawMap
              className="map map--draw"
              vertices={form.vertices}
              onAddVertex={
                drawing && !disabled ? (lon, lat) => setForm({ vertices: addVertex(form.vertices, lon, lat) }) : undefined
              }
              bounds={bounds}
              ariaLabel={t("notify.area.mapLabel")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
            />
          </Suspense>
          <p role="status" aria-live="polite">
            {t("notify.area.points", { count: fmt.number(form.vertices.length) })}
            {!drawing && ` · ${t("notify.area.closed")}`}
          </p>
          <div className="actions">
            {drawing ? (
              <button
                type="button"
                className="btn"
                disabled={form.vertices.length < 3}
                onClick={() => setDrawing(false)}
              >
                {t("notify.area.finish")}
              </button>
            ) : (
              <button type="button" className="btn" onClick={() => setDrawing(true)}>
                {t("notify.area.resume")}
              </button>
            )}
            <button
              type="button"
              className="btn btn--ghost"
              disabled={form.vertices.length === 0}
              onClick={() => setForm({ vertices: undoVertex(form.vertices) })}
            >
              {t("notify.area.undo")}
            </button>
            <button
              type="button"
              className="btn btn--ghost"
              disabled={form.vertices.length === 0}
              onClick={() => {
                setForm({ vertices: [] });
                setDrawing(true);
              }}
            >
              {t("notify.area.clear")}
            </button>
          </div>
          {errors.polygon && (
            <p className="field__error" role="alert">
              {t(`notify.validation.${errors.polygon}`, { max: MAX_VERTICES })}
            </p>
          )}
        </div>
      )}
    </fieldset>
  );
}

function GouvernoratTargets({ form, setForm }: { form: MessageForm; setForm: (patch: Partial<MessageForm>) => void }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  if (!user?.identity.national) {
    // A regional author targets its own gouvernorat (§7: `403 out_of_scope` otherwise).
    return <p className="muted">{t("notify.area.own", { name: gouvernorats.nameOf(user?.identity.gouvernoratCode) ?? "—" })}</p>;
  }
  const toggle = (code: number, on: boolean) =>
    setForm({
      gouvernorats: on ? [...form.gouvernorats, code].sort((a, b) => a - b) : form.gouvernorats.filter((c) => c !== code),
    });
  return (
    <fieldset className="chips">
      <legend>{t("notify.area.gouvernorats")}</legend>
      <p className="muted">{t("notify.area.emptyIsNational")}</p>
      {gouvernorats.list.map((g) => (
        <label key={g.code} className="chip-toggle">
          <input
            type="checkbox"
            checked={form.gouvernorats.includes(g.code)}
            onChange={(e) => toggle(g.code, e.target.checked)}
          />
          <span>{gouvernorats.nameOf(g.code)}</span>
        </label>
      ))}
    </fieldset>
  );
}

// Enough to catch a typo before asking the API; the API validates the address fully.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Target of a message to one user: find the account by its exact e-mail (masked result, audited by the API),
 * or paste its id directly. The id field stays the source of truth sent with the message.
 */
function UserTarget({
  userId,
  setUserId,
  error,
}: {
  userId: string;
  setUserId: (id: string) => void;
  error: string | undefined;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const base = useId();
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState(false);
  const [found, setFound] = useState<UserLookup | null>(null);
  const lookup = useMutation({
    mutationFn: (address: string) => api.lookupUser(address),
    onSuccess: (account) => {
      setFound(account);
      setUserId(account.user_id);
    },
  });
  const search = () => {
    const address = email.trim();
    const valid = EMAIL.test(address);
    setEmailError(!valid);
    if (valid) lookup.mutate(address);
  };
  // A pasted or edited id no longer matches the account that was found.
  const shown = found && found.user_id === userId.trim() ? found : null;
  const reachable = shown ? CHANNELS.filter((c) => shown.channels[c]) : [];
  const emailId = `${base}-email`;
  const idId = `${base}-id`;
  return (
    <div className="user-target">
      <div className={`field${emailError || lookup.isError ? " field--invalid" : ""}`}>
        <label htmlFor={emailId}>{t("notify.userLookup.email")}</label>
        <div className="input-with-button">
          <input
            id={emailId}
            type="email"
            dir="ltr"
            autoComplete="off"
            value={email}
            aria-invalid={emailError || lookup.isError ? true : undefined}
            aria-describedby={`${base}-email-help${emailError || lookup.isError ? ` ${base}-email-error` : ""}`}
            onChange={(e) => {
              setEmail(e.target.value);
              setEmailError(false);
              lookup.reset();
            }}
            onKeyDown={(e) => {
              // Enter searches here instead of submitting the whole message form.
              if (e.key === "Enter") {
                e.preventDefault();
                search();
              }
            }}
          />
          <button type="button" className="btn" disabled={lookup.isPending || !email.trim()} onClick={search}>
            {lookup.isPending ? t("notify.userLookup.searching") : t("notify.userLookup.search")}
          </button>
        </div>
        <p id={`${base}-email-help`} className="muted">
          {t("notify.userLookup.help")}
        </p>
        {(emailError || lookup.isError) && (
          <p id={`${base}-email-error`} className="field__error" role="alert">
            {emailError ? t("notify.userLookup.invalidEmail") : t(errorMessageKey(lookup.error))}
          </p>
        )}
      </div>
      {shown && (
        <div className="card user-target__found" role="status" aria-label={t("notify.userLookup.found")}>
          <p>
            <strong>{t("notify.userLookup.found")}</strong> · <span dir="auto">{shown.display_name ?? t("notify.userLookup.noName")}</span>{" "}
            · <span dir="ltr">{shown.email}</span>
          </p>
          <p className="muted">
            {reachable.length > 0
              ? t("notify.userLookup.channels", {
                  list: reachable.map((c) => t(`notify.channel.${c}`)).join(t("common.listSeparator")),
                })
              : t("notify.userLookup.noChannel")}
          </p>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setFound(null);
              setUserId("");
              setEmail("");
              lookup.reset();
            }}
          >
            {t("notify.userLookup.clear")}
          </button>
        </div>
      )}
      <p className="muted">{t("notify.userLookup.orId")}</p>
      <Field id={idId} label={t("notify.fields.userId")} error={error}>
        <input
          id={idId}
          type="text"
          dir="ltr"
          value={userId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${idId}-error` : undefined}
          onChange={(e) => setUserId(e.target.value)}
        />
      </Field>
    </div>
  );
}

function Composer({ message, kind }: { message: Message | null; kind: MessageKind }) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const fmt = useFormat();
  const base = useId();
  const roles = user?.identity.roles ?? [];
  const regional = user && !user.identity.national ? user.identity.gouvernoratCode : null;
  const [form, setFormState] = useState<MessageForm>(() => {
    if (message) return formFromMessage(message);
    const empty = emptyForm(kind);
    return regional !== null ? { ...empty, gouvernorats: [regional] } : empty;
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [confirm, setConfirm] = useState<"publish" | "delete" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const setForm = (patch: Partial<MessageForm>) => {
    setFormState((f) => ({ ...f, ...patch }));
    setConfirm(null);
    setNotice(null);
  };

  const canEdit = canDraftMessage(roles, kind);
  const canPublish = canPublishMessage(roles, kind);
  const baseline = useMemo(() => (message ? JSON.stringify(toMessageBody(formFromMessage(message))) : null), [message]);
  const dirty = baseline === null || JSON.stringify(toMessageBody(form)) !== baseline;

  const audience = useQuery({
    queryKey: message ? opsKeys.audience(message.id, message.version) : ["message-audience", "none"],
    enabled: message !== null,
    queryFn: ({ signal }) => {
      if (!message) throw new Error("no message");
      return api.messageAudience(message.id, signal);
    },
  });

  const remember = (m: Message) => {
    qc.setQueryData(opsKeys.message(m.id), m);
    void qc.invalidateQueries({ queryKey: opsKeys.messagesAll });
  };

  const save = useMutation({
    mutationFn: () =>
      message ? api.updateMessage(message.id, toMessageBody(form, message.version)) : api.createMessage(toMessageBody(form)),
    onSuccess: (m) => {
      remember(m);
      setNotice(t("notify.saved"));
      if (!message) void navigate(`/notifications/${encodeURIComponent(m.id)}`, { replace: true });
    },
    onError: (error) => {
      if (isApiError(error) && error.code === "version_conflict" && message) {
        void qc.invalidateQueries({ queryKey: opsKeys.message(message.id) });
      }
    },
  });
  const publish = useMutation({
    mutationFn: (id: string) => api.publishMessage(id),
    onSuccess: (m) => {
      remember(m);
      if (m.kind === "alert") void qc.invalidateQueries({ queryKey: opsKeys.activeAlerts });
      setConfirm(null);
      setNotice(t("notify.publishedOk"));
    },
    onError: () => setConfirm(null),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteMessage(id),
    onSuccess: (_r, id) => {
      qc.removeQueries({ queryKey: opsKeys.message(id) });
      void qc.invalidateQueries({ queryKey: opsKeys.messagesAll });
      void navigate("/notifications");
    },
    onError: () => setConfirm(null),
  });
  const busy = save.isPending || publish.isPending || remove.isPending;
  const error = save.error ?? publish.error ?? remove.error;

  const submit = (e: SyntheticEvent) => {
    e.preventDefault();
    const next = validateForm(form);
    setErrors(next);
    publish.reset();
    if (Object.keys(next).length > 0) return;
    save.mutate();
  };

  const id = (name: string) => `${base}-${name}`;
  const describedBy = (name: keyof FormErrors) => (errors[name] ? `${id(name)}-error` : undefined);
  const selectField = (
    name: "topic" | "audience" | "severity" | "category" | "hazard",
    values: readonly string[],
    labelKey: string,
    optional = false,
  ) => (
    <Field id={id(name)} label={t(`notify.fields.${name}`)} error={errors[name as keyof FormErrors]}>
      <select
        id={id(name)}
        value={form[name]}
        aria-invalid={errors[name as keyof FormErrors] ? true : undefined}
        aria-describedby={describedBy(name as keyof FormErrors)}
        onChange={(e) => setForm({ [name]: e.target.value })}
      >
        <option value="">{optional ? t("notify.fields.none") : t("notify.fields.choose")}</option>
        {values.map((v) => (
          <option key={v} value={v}>
            {t(`${labelKey}.${v}`)}
          </option>
        ))}
      </select>
    </Field>
  );

  return (
    <form className="composer" onSubmit={submit} noValidate>
      <fieldset disabled={busy || !canEdit} className="composer__fields">
        <legend className="visually-hidden">{t(`notify.kind.${kind}`)}</legend>
        <div className="composer__langs">
          {LANGS.map((l) => (
            <div key={l} className="composer__lang" lang={l}>
              <Field
                id={id(`title-${l}`)}
                label={t(`notify.fields.title.${l}`)}
                error={l === "ar" ? errors.titleAr : undefined}
              >
                <input
                  id={id(`title-${l}`)}
                  type="text"
                  dir={LANG_DIR[l]}
                  maxLength={TITLE_MAX}
                  value={form.title[l]}
                  aria-invalid={l === "ar" && errors.titleAr ? true : undefined}
                  aria-describedby={l === "ar" ? describedBy("titleAr") : undefined}
                  onChange={(e) => setForm({ title: { ...form.title, [l]: e.target.value } })}
                />
              </Field>
              <Field id={id(`body-${l}`)} label={t(`notify.fields.body.${l}`)} error={l === "ar" ? errors.bodyAr : undefined}>
                <textarea
                  id={id(`body-${l}`)}
                  dir={LANG_DIR[l]}
                  rows={4}
                  maxLength={BODY_MAX}
                  value={form.body[l]}
                  aria-invalid={l === "ar" && errors.bodyAr ? true : undefined}
                  aria-describedby={l === "ar" ? describedBy("bodyAr") : undefined}
                  onChange={(e) => setForm({ body: { ...form.body, [l]: e.target.value } })}
                />
              </Field>
              <p className="muted" lang={undefined}>
                {t("notify.counter", { n: form.body[l].length, max: BODY_MAX })}
              </p>
            </div>
          ))}
        </div>
        <p className="muted">{t("notify.fallbackHint")}</p>

        {kind === "info" ? (
          <div className="fields-row">
            {selectField("topic", TOPICS, "notify.topic")}
            {selectField("audience", AUDIENCES, "notify.audience")}
          </div>
        ) : (
          <div className="fields-row">
            {selectField("severity", SEVERITIES, "notify.severity")}
            {selectField("category", ALERT_CATEGORIES, "notify.category")}
            {selectField("hazard", HAZARDS, "notify.hazard", true)}
            <Field id={id("expires")} label={t("notify.fields.expiresAt")} error={errors.expiresAt}>
              <input
                id={id("expires")}
                type="datetime-local"
                dir="ltr"
                value={form.expiresAt}
                aria-invalid={errors.expiresAt ? true : undefined}
                aria-describedby={describedBy("expiresAt")}
                onChange={(e) => setForm({ expiresAt: e.target.value })}
              />
            </Field>
          </div>
        )}

        {kind === "info" && form.audience === "user" && (
          <UserTarget userId={form.userId} setUserId={(userId) => setForm({ userId })} error={errors.userId} />
        )}

        {kind === "alert" ? (
          <AreaEditor form={form} setForm={setForm} errors={errors} disabled={busy || !canEdit} />
        ) : (
          form.audience !== "user" && <GouvernoratTargets form={form} setForm={setForm} />
        )}

        <fieldset className="chips">
          <legend>{t("notify.fields.channels")}</legend>
          {CHANNELS.map((c) => (
            <label key={c} className="chip-toggle">
              <input
                type="checkbox"
                checked={form.channels.includes(c)}
                onChange={(e) =>
                  setForm({ channels: e.target.checked ? [...form.channels, c] : form.channels.filter((x) => x !== c) })
                }
              />
              <span>{t(`notify.channel.${c}`)}</span>
            </label>
          ))}
        </fieldset>
        {errors.channels && (
          <p className="field__error" role="alert">
            {t(`notify.validation.${errors.channels}`)}
          </p>
        )}
        {form.channels.includes("sms") && (
          <div className="sms-preview">
            <p className="muted">{t("notify.smsPreview")}</p>
            <p dir="rtl" lang="ar" className="code">
              {smsPreview(form.title.ar, form.body.ar)}
            </p>
          </div>
        )}
      </fieldset>

      {message && (
        <section className="card audience" aria-labelledby={id("audience")}>
          <h2 id={id("audience")}>{t("notify.audienceTitle")}</h2>
          {audience.isPending && <Loading />}
          {audience.isError && <ErrorBox error={audience.error} onRetry={() => void audience.refetch()} />}
          {audience.data && (
            <p>
              {t("notify.audienceLine", {
                push: fmt.number(audience.data.push),
                sms: fmt.number(audience.data.sms),
                email: fmt.number(audience.data.email),
              })}
            </p>
          )}
          {dirty && <p className="muted">{t("notify.audienceStale")}</p>}
        </section>
      )}

      {confirm === "publish" && message && (
        <div className={`alert ${kind === "alert" ? "alert--error" : "alert--warn"}`} role="alert">
          <p>
            {t(kind === "alert" ? "notify.confirmPublishAlert" : "notify.confirmPublishInfo", {
              push: fmt.number(audience.data?.push ?? 0),
              sms: fmt.number(audience.data?.sms ?? 0),
              email: fmt.number(audience.data?.email ?? 0),
            })}
          </p>
          <div className="actions">
            <button type="button" className="btn btn--primary" disabled={busy} onClick={() => publish.mutate(message.id)}>
              {t("notify.confirmPublish")}
            </button>
            <button type="button" className="btn" onClick={() => setConfirm(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}
      {confirm === "delete" && message && (
        <div className="alert alert--warn" role="alert">
          <p>{t("notify.confirmDeleteText")}</p>
          <div className="actions">
            <button type="button" className="btn btn--primary" disabled={busy} onClick={() => remove.mutate(message.id)}>
              {t("notify.confirmDelete")}
            </button>
            <button type="button" className="btn" onClick={() => setConfirm(null)}>
              {t("common.cancel")}
            </button>
          </div>
        </div>
      )}

      {canEdit && (
        <div className="actions">
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {save.isPending ? t("notify.saving") : t("notify.saveDraft")}
          </button>
          {message && canPublish && (
            <button
              type="button"
              className="btn"
              disabled={busy || dirty || !audience.data}
              onClick={() => {
                const next = validateForm(form);
                setErrors(next);
                if (Object.keys(next).length === 0) setConfirm("publish");
              }}
            >
              {t(kind === "alert" ? "notify.publishAlert" : "notify.publishInfo")}
            </button>
          )}
          {message && (
            <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => setConfirm("delete")}>
              {t("notify.deleteDraft")}
            </button>
          )}
        </div>
      )}
      {message && dirty && canPublish && <p className="muted">{t("notify.saveBeforePublish")}</p>}
      {message && !canPublish && <p className="muted">{t("notify.publishByEditor")}</p>}
      {Object.keys(errors).length > 0 && (
        <p className="alert alert--error" role="alert">
          {t("notify.validation.summary")}
        </p>
      )}
      <div role="status" aria-live="polite">
        {notice && <p className="alert alert--ok">{notice}</p>}
      </div>
      {error && (
        <p className="alert alert--error" role="alert">
          {t(errorMessageKey(error))}
        </p>
      )}
    </form>
  );
}

/** A message no longer editable: what was sent, to whom, and its delivery per channel; a published one can be cancelled. */
function SentMessage({ message }: { message: Message }) {
  const { t } = useTranslation();
  const { api, mapStyleUrl } = useServices();
  const { user } = useAuth();
  const qc = useQueryClient();
  const fmt = useFormat();
  const lang = useLanguage();
  const gouvernorats = useGouvernorats();
  const [confirming, setConfirming] = useState(false);
  const canCancel = message.status === "published" && canPublishMessage(user?.identity.roles ?? [], message.kind);
  const cancel = useMutation({
    mutationFn: () => api.cancelMessage(message.id),
    onSuccess: (m) => {
      qc.setQueryData(opsKeys.message(m.id), m);
      void qc.invalidateQueries({ queryKey: opsKeys.messagesAll });
      void qc.invalidateQueries({ queryKey: opsKeys.activeAlerts });
      setConfirming(false);
    },
    onError: () => setConfirming(false),
  });
  const vertices = useMemo(
    () => (message.area.polygon?.coordinates[0] ?? []).slice(0, -1).map(([lon, lat]) => [lon, lat] as [number, number]),
    [message.area.polygon],
  );
  const bounds = verticesBounds(vertices);
  return (
    <div className="sent-message">
      <div className="detail__grid">
        <section className="card" aria-labelledby="sec-content">
          <h2 id="sec-content">{t("notify.content")}</h2>
          {LANGS.filter((l) => message.title[l] || message.body[l]).map((l) => (
            <div key={l} lang={l} dir={LANG_DIR[l]} className="sent-message__lang">
              <h3>{message.title[l]}</h3>
              <p>{message.body[l]}</p>
            </div>
          ))}
        </section>
        <section className="card" aria-labelledby="sec-sending">
          <h2 id="sec-sending">{t("notify.sending")}</h2>
          <dl className="fields">
            <dt>{t("notify.columns.target")}</dt>
            <dd>
              <TargetText message={message} />
            </dd>
            {message.kind === "info" && message.topic && (
              <>
                <dt>{t("notify.fields.topic")}</dt>
                <dd>{t(`notify.topic.${message.topic}`)}</dd>
              </>
            )}
            {message.kind === "alert" && (
              <>
                <dt>{t("notify.fields.category")}</dt>
                <dd>
                  {message.category ? t(`notify.category.${message.category}`) : "—"}
                  {message.hazard && ` · ${t(`notify.hazard.${message.hazard}`)}`}
                </dd>
                <dt>{t("notify.fields.expiresAt")}</dt>
                <dd>{message.expires_at ? fmt.dateTime(message.expires_at) : "—"}</dd>
              </>
            )}
            <dt>{t("notify.createdBy")}</dt>
            <dd>
              {message.created_by ?? "—"} · {fmt.dateTime(message.created_at)}
            </dd>
            {message.published_at && (
              <>
                <dt>{t("notify.publishedBy")}</dt>
                <dd>
                  {message.published_by ?? "—"} · {fmt.dateTime(message.published_at)}
                </dd>
              </>
            )}
            {message.cancelled_at && (
              <>
                <dt>{t("notify.cancelledAt")}</dt>
                <dd>{fmt.dateTime(message.cancelled_at)}</dd>
              </>
            )}
            {message.area.gouvernorat_codes.length > 0 && (
              <>
                <dt>{t("notify.area.gouvernorats")}</dt>
                <dd>{message.area.gouvernorat_codes.map((c) => gouvernorats.nameOf(c)).join(t("common.listSeparator"))}</dd>
              </>
            )}
          </dl>
        </section>
      </div>
      {bounds && (
        <section className="card" aria-labelledby="sec-area">
          <h2 id="sec-area">{t("notify.area.legend")}</h2>
          <Suspense fallback={<Loading />}>
            <LazyPolygonDrawMap
              className="map map--draw"
              vertices={vertices}
              bounds={bounds}
              ariaLabel={t("notify.area.mapLabel")}
              styleUrl={mapStyleUrl}
              dir={directionOf(lang)}
            />
          </Suspense>
        </section>
      )}
      <section className="card" aria-labelledby="sec-delivery">
        <h2 id="sec-delivery">{t("notify.delivery")}</h2>
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">{t("notify.delivery")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("notify.fields.channels")}</th>
                <th scope="col">{t("notify.columns.status")}</th>
                <th scope="col">{t("notify.sent")}</th>
                <th scope="col">{t("notify.failed")}</th>
              </tr>
            </thead>
            <tbody>
              {CHANNELS.filter((c) => message.channels.includes(c)).map((c) => {
                const s = message.stats[c];
                return (
                  <tr key={c}>
                    <th scope="row">{t(`notify.channel.${c}`)}</th>
                    <td>{s ? t(`notify.dispatch.${s.status}`, { defaultValue: s.status }) : "—"}</td>
                    <td>{s ? fmt.number(s.sent) : "—"}</td>
                    <td>{s ? fmt.number(s.failed) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted">{t("notify.deliveryLive")}</p>
      </section>
      {canCancel && (
        <section className="card" aria-labelledby="sec-cancel">
          <h2 id="sec-cancel">{t(message.kind === "alert" ? "notify.cancelAlert" : "notify.cancelInfo")}</h2>
          <p className="muted">{t(message.kind === "alert" ? "notify.cancelAlertHelp" : "notify.cancelInfoHelp")}</p>
          {confirming ? (
            <div className="alert alert--warn" role="alert">
              <p>{t("notify.confirmCancelText")}</p>
              <div className="actions">
                <button type="button" className="btn btn--primary" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
                  {t("notify.confirmCancel")}
                </button>
                <button type="button" className="btn" onClick={() => setConfirming(false)}>
                  {t("common.cancel")}
                </button>
              </div>
            </div>
          ) : (
            <button type="button" className="btn" onClick={() => setConfirming(true)}>
              {t(message.kind === "alert" ? "notify.cancelAlert" : "notify.cancelInfo")}
            </button>
          )}
          {cancel.isError && (
            <p className="alert alert--error" role="alert">
              {t(errorMessageKey(cancel.error))}
            </p>
          )}
        </section>
      )}
    </div>
  );
}

/** FR-C-17 / FR-C-18: compose, estimate, publish or cancel one notification or alert. */
export function NotificationEditorPage() {
  const { id } = useParams();
  const [search] = useSearchParams();
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const roles = user?.identity.roles ?? [];
  const query = useQuery({
    queryKey: id ? opsKeys.message(id) : ["message", "new"],
    enabled: Boolean(id),
    queryFn: ({ signal }) => {
      if (!id) throw new Error("no id");
      return api.message(id, signal);
    },
    retry: (count, error) => !(isApiError(error) && [403, 404].includes(error.status)) && count < 2,
  });

  const requested = search.get("kind");
  const newKind: MessageKind =
    requested === "info" || requested === "alert"
      ? requested
      : canDraftMessage(roles, "alert")
        ? "alert"
        : "info";

  const back = (
    <p>
      <Link to="/notifications">{t("notify.back")}</Link>
    </p>
  );

  if (!id) {
    if (!canDraftMessage(roles, newKind)) {
      return (
        <div className="page">
          {back}
          <p className="alert alert--error" role="alert">
            {t("errors.insufficient_role")}
          </p>
        </div>
      );
    }
    return (
      <div className="page">
        {back}
        <div className="page__head">
          <h1>{t(newKind === "alert" ? "notify.newAlert" : "notify.newInfo")}</h1>
        </div>
        <Composer key="new" message={null} kind={newKind} />
      </div>
    );
  }

  if (query.isPending) return <Loading />;
  if (query.isError)
    return (
      <div className="page">
        {back}
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  const message = query.data;
  return (
    <div className="page">
      {back}
      <div className="page__head">
        <h1 dir="auto">{message.title.ar}</h1>
        <MessageKindTag message={message} />
        <MessageStatusTag status={message.status} />
      </div>
      {message.status === "draft" ? (
        <Composer key={message.id} message={message} kind={message.kind} />
      ) : (
        <>
          <p className="muted">
            <StatsText message={message} />
          </p>
          <SentMessage message={message} />
        </>
      )}
    </div>
  );
}
