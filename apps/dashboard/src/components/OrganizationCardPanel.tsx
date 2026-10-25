import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useFormat } from "../lib/hooks";
import type { OrganizationCard } from "../lib/types";
import { classificationText, featureKindLabel, hazmatQuantity, InlineIcon, KindFieldsList, orgKindLabel } from "./OrgBits";

/**
 * "Institution card" of a report made on behalf of an institution (phase 4 §9): what responders need on the
 * way — capacity, the safety representative to call, and the hazardous materials stored on site.
 */
export function OrganizationCardPanel({ card }: { card: OrganizationCard }) {
  const { t } = useTranslation();
  const fmt = useFormat();
  const rep = card.representative;
  const repName = rep?.full_name ?? t("common.notAvailable");
  return (
    <section className="card org-card" aria-labelledby="sec-org-card">
      <h2 id="sec-org-card">{t("orgs.card.title")}</h2>
      <p className="org-card__name">
        <Link to={`/orgs/${encodeURIComponent(card.id)}`} dir="auto">
          {card.name}
        </Link>{" "}
        <span className="tag">{orgKindLabel(t, card.kind)}</span>
      </p>
      <dl className="fields">
        <dt>{t("orgs.card.capacity")}</dt>
        <dd className="org-card__capacity">{card.capacity === null ? t("common.notAvailable") : fmt.number(card.capacity)}</dd>
        <dt>{t("orgs.card.classification")}</dt>
        <dd>{classificationText(t, fmt, card.classification)}</dd>
        <dt>{t("orgs.card.address")}</dt>
        <dd dir="auto">{card.address ?? t("common.notAvailable")}</dd>
        <dt>{t("orgs.card.representative")}</dt>
        <dd>
          {rep ? (
            <>
              <span dir="auto">{repName}</span>
              {rep.phone && (
                <>
                  {" "}
                  <a
                    className="btn btn--small btn--call"
                    href={`tel:${rep.phone}`}
                    aria-label={t("orgs.card.call", { name: repName, phone: rep.phone })}
                  >
                    <span dir="ltr">{rep.phone}</span>
                  </a>
                </>
              )}
            </>
          ) : (
            <span className="muted">{t("orgs.card.noRepresentative")}</span>
          )}
        </dd>
      </dl>

      {card.kind_fields && Object.keys(card.kind_fields).length > 0 && (
        <>
          <h3 className="subhead">{t("orgs.kindExtra.kindFieldsTitle")}</h3>
          <KindFieldsList kind={card.kind} values={card.kind_fields} />
        </>
      )}

      {card.hazmat.length === 0 ? (
        <p className="muted">{t("orgs.card.noHazmat")}</p>
      ) : (
        <div className="hazard" role="group" aria-labelledby="org-card-hazmat">
          <h3 id="org-card-hazmat" className="hazard__title">
            <InlineIcon kind="org_hazmat" size={18} />
            {t("orgs.card.hazmatTitle")}
          </h3>
          <p className="hazard__note">{t("orgs.card.hazmatWarning")}</p>
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">{t("orgs.card.hazmatTitle")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("orgs.detail.hazmatName")}</th>
                  <th scope="col">{t("orgs.detail.unNumber")}</th>
                  <th scope="col">{t("orgs.detail.hazardClass")}</th>
                  <th scope="col" className="num">
                    {t("orgs.detail.quantity")}
                  </th>
                  <th scope="col">{t("orgs.detail.storage")}</th>
                </tr>
              </thead>
              <tbody>
                {card.hazmat.map((h, i) => (
                  <tr key={`${h.name}-${i}`}>
                    <th scope="row" dir="auto">
                      {h.name}
                    </th>
                    <td className="code" dir="ltr">
                      {h.un_number ? `UN ${h.un_number}` : "—"}
                    </td>
                    <td dir="ltr">{h.hazard_class ?? "—"}</td>
                    <td className="num">{hazmatQuantity(t, fmt, h)}</td>
                    <td dir="auto">{h.storage_location ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {card.features.length > 0 && (
        <>
          <h3 className="subhead">{t("orgs.card.features")}</h3>
          <ul className="feature-list">
            {card.features.map((f) => (
              <li key={f.id}>
                {featureKindLabel(t, f.kind)}
                {f.label && <span dir="auto"> — {f.label}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      <p>
        <Link to={`/orgs/${encodeURIComponent(card.id)}`}>{t("orgs.card.open")}</Link>
      </p>
    </section>
  );
}
