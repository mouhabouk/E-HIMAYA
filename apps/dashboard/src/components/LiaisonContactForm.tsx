import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/auth";
import { useServices } from "../context/services";
import { useGouvernorats } from "../lib/hooks";
import {
  LIAISON_CATEGORIES,
  liaisonKeys,
  type ContactBody,
  type LiaisonCategory,
} from "../lib/liaison";
import { ErrorBox } from "./Feedback";

const PHONE = /^[0-9+ ]{3,20}$/;

/**
 * Adds a body and its first official to the contact system (OS20), from the contact system page or from a report
 * when the body is missing. A regional room adds bodies of its gouvernorat; the central room national bodies, or,
 * from a report, a body of the report's gouvernorat that the regional room keeps from then on. `existing`: the bodies
 * the room keeps, to add an official to one of them instead.
 */
export function ContactForm({
  fixedGouvernorat,
  originIncidentId,
  existing = [],
  onSaved,
  onCancel,
}: {
  /** Central room only: the gouvernorat of the new body (null: national). */
  fixedGouvernorat?: number | null;
  originIncidentId?: string;
  existing?: ContactBody[];
  onSaved: (body: ContactBody) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const { api } = useServices();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const qc = useQueryClient();
  const base = useId();
  const central = Boolean(user?.identity.national);
  const own = user?.identity.gouvernoratCode ?? null;
  const [gov, setGov] = useState<number | null>(
    central ? (fixedGouvernorat ?? null) : own,
  );
  const [bodyId, setBodyId] = useState("");
  const [category, setCategory] = useState<LiaisonCategory>("regional");
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [address, setAddress] = useState("");
  const [publicPhone, setPublicPhone] = useState("");
  const [person, setPerson] = useState("");
  const [role, setRole] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [duty, setDuty] = useState("");
  const editable = existing.filter((b) => b.editable);
  const save = useMutation({
    mutationFn: async (): Promise<ContactBody> => {
      const official = person.trim()
        ? {
            name: person.trim(),
            role: role.trim() || null,
            phones: [phone.trim()],
            email: email.trim() || null,
            duty: duty.trim() || null,
          }
        : null;
      if (bodyId) {
        const target = editable.find((b) => b.id === bodyId);
        if (!official || !target) throw new Error("validation_error");
        const added = await api.liaisonAddOfficial(bodyId, official);
        return { ...target, officials: [added] };
      }
      return api.liaisonCreateBody({
        gouvernorat_code: central ? gov : own,
        category,
        name: name.trim(),
        domain: domain.trim() || null,
        address: address.trim() || null,
        public_phone: publicPhone.trim() || null,
        officials: official ? [official] : [],
        origin_incident_id: originIncidentId ?? null,
      });
    },
    onSuccess: (b) => {
      void qc.invalidateQueries({ queryKey: liaisonKeys.all });
      onSaved(b);
    },
  });
  const phoneOk = person.trim()
    ? PHONE.test(phone.trim())
    : !phone.trim() || PHONE.test(phone.trim());
  const valid = bodyId
    ? person.trim().length >= 2 && PHONE.test(phone.trim())
    : name.trim().length >= 2 &&
      phoneOk &&
      (!publicPhone.trim() || PHONE.test(publicPhone.trim()));
  const keeper = central
    ? gov === null
      ? t("liaison.form.keeperCentral")
      : t("liaison.form.keeperRegional", {
          gov: gouvernorats.nameOf(gov) ?? "",
        })
    : t("liaison.form.keeperRegional", { gov: gouvernorats.nameOf(own) ?? "" });
  return (
    <form
      className="liaison-form"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) save.mutate();
      }}
    >
      <h4>{t("liaison.form.title")}</h4>
      <div className="liaison-form__grid">
        {editable.length > 0 && (
          <div className="field">
            <label htmlFor={`${base}-body`}>{t("liaison.form.body")}</label>
            <select
              id={`${base}-body`}
              value={bodyId}
              onChange={(e) => setBodyId(e.target.value)}
            >
              <option value="">{t("liaison.form.newBody")}</option>
              {editable.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {!bodyId && (
          <>
            {central && (
              <div className="field">
                <label htmlFor={`${base}-gov`}>
                  {t("liaison.form.gouvernorat")}
                </label>
                <select
                  id={`${base}-gov`}
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
              </div>
            )}
            <div className="field">
              <label htmlFor={`${base}-name`}>
                {t("liaison.form.name")} <span className="required">*</span>
              </label>
              <input
                id={`${base}-name`}
                value={name}
                maxLength={160}
                onChange={(e) => setName(e.target.value)}
                dir="auto"
              />
            </div>
            <div className="field">
              <label htmlFor={`${base}-cat`}>
                {t("liaison.form.category")}
              </label>
              <select
                id={`${base}-cat`}
                value={category}
                onChange={(e) => setCategory(e.target.value as LiaisonCategory)}
              >
                {LIAISON_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`liaison.category.${c}`)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor={`${base}-dom`}>{t("liaison.form.domain")}</label>
              <input
                id={`${base}-dom`}
                value={domain}
                maxLength={160}
                onChange={(e) => setDomain(e.target.value)}
                dir="auto"
              />
            </div>
            <div className="field">
              <label htmlFor={`${base}-addr`}>
                {t("liaison.form.address")}
              </label>
              <input
                id={`${base}-addr`}
                value={address}
                maxLength={200}
                onChange={(e) => setAddress(e.target.value)}
                dir="auto"
              />
            </div>
            <div className="field">
              <label htmlFor={`${base}-pub`}>
                {t("liaison.form.publicPhone")}
              </label>
              <input
                id={`${base}-pub`}
                className="mono"
                dir="ltr"
                inputMode="tel"
                value={publicPhone}
                maxLength={20}
                onChange={(e) => setPublicPhone(e.target.value)}
              />
            </div>
          </>
        )}
        <div className="field">
          <label htmlFor={`${base}-person`}>
            {t("liaison.form.person")}{" "}
            {bodyId && <span className="required">*</span>}
          </label>
          <input
            id={`${base}-person`}
            value={person}
            maxLength={120}
            onChange={(e) => setPerson(e.target.value)}
            dir="auto"
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-role`}>{t("liaison.form.role")}</label>
          <input
            id={`${base}-role`}
            value={role}
            maxLength={120}
            onChange={(e) => setRole(e.target.value)}
            dir="auto"
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-phone`}>
            {t("liaison.form.phone")}{" "}
            {(bodyId || person.trim()) && <span className="required">*</span>}
          </label>
          <input
            id={`${base}-phone`}
            className="mono"
            dir="ltr"
            inputMode="tel"
            value={phone}
            maxLength={20}
            aria-invalid={!phoneOk}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-mail`}>{t("liaison.form.email")}</label>
          <input
            id={`${base}-mail`}
            type="email"
            dir="ltr"
            value={email}
            maxLength={200}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={`${base}-duty`}>{t("liaison.form.duty")}</label>
          <input
            id={`${base}-duty`}
            value={duty}
            maxLength={120}
            onChange={(e) => setDuty(e.target.value)}
            dir="auto"
          />
        </div>
      </div>
      <p className="muted liaison-form__note">{keeper}</p>
      {save.isError && <ErrorBox error={save.error} />}
      <div className="actions">
        <button type="button" className="btn" onClick={onCancel}>
          {t("common.cancel")}
        </button>
        <button
          type="submit"
          className="btn btn--primary"
          disabled={!valid || save.isPending}
        >
          {t("liaison.form.save")}
        </button>
      </div>
    </form>
  );
}
