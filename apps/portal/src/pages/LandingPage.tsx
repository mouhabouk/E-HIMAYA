import { useState, type SubmitEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";
import { ForwardIcon } from "../components/Feedback";
import { SignInButtons } from "../components/Layout";
import { useAuth } from "../context/auth";

export function VerifyCodeForm() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  function submit(e: SubmitEvent) {
    e.preventDefault();
    const v = code.trim().toUpperCase();
    if (v) void navigate(`/verify/${encodeURIComponent(v)}`);
  }
  return (
    <form className="inline-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="verify-code">{t("verify.codeLabel")}</label>
        <input
          id="verify-code"
          className="code"
          dir="ltr"
          placeholder="EHC-26-61-000123"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </div>
      <button type="submit" className="btn btn--primary">
        {t("verify.check")}
      </button>
    </form>
  );
}

/** Public landing: what the portal is, sign in / create an account, and certificate verification. */
export function LandingPage() {
  const { t } = useTranslation();
  const { status } = useAuth();
  return (
    <div className="page landing">
      <section className="card hero">
        <h1>{t("landing.title")}</h1>
        <p className="hero__lead">{t("landing.lead")}</p>
        <ul className="hero__points">
          <li>{t("landing.point1")}</li>
          <li>{t("landing.point2")}</li>
          <li>{t("landing.point3")}</li>
          <li>{t("landing.point4")}</li>
        </ul>
        <div className="actions">
          {status === "signedIn" ? (
            <Link className="btn btn--primary" to="/orgs/mine">
              {t("landing.goToMyOrgs")}
              <ForwardIcon />
            </Link>
          ) : status === "signedOut" ? (
            <SignInButtons primary />
          ) : null}
        </div>
      </section>
      <section className="card">
        <h2>{t("landing.verifyTitle")}</h2>
        <p>{t("landing.verifyBody")}</p>
        <VerifyCodeForm />
      </section>
      <section className="card emergency">
        <h2>{t("landing.emergencyTitle")}</h2>
        <p>{t("landing.emergencyBody")}</p>
        <ul className="emergency__numbers">
          <li>
            <a href="tel:198">198</a> {t("landing.n198")}
          </li>
          <li>
            <a href="tel:190">190</a> {t("landing.n190")}
          </li>
          <li>
            <a href="tel:197">197</a> {t("landing.n197")}
          </li>
          <li>
            <a href="tel:193">193</a> {t("landing.n193")}
          </li>
        </ul>
      </section>
    </div>
  );
}
