// covers: phase N (docs/phase-n/design-n.md §2): the committees replace the governor and the minister everywhere,
// except the heading of their main window, which names who chairs them.
import { useTranslation } from "react-i18next";
import type { StaffIdentity } from "../auth/identity";
import { useAuth } from "../context/auth";
import { useGouvernorats } from "../lib/hooks";

const REGIONAL = new Set(["governor", "local_committee"]);
const NATIONAL = new Set(["minister", "central_committee"]);

/** "regional" for the governorate's committee, "national" for the national one, null for every other account. */
export function committeeOf(identity: Pick<StaffIdentity, "roles" | "national">): "regional" | "national" | null {
  if (identity.roles.some((r) => NATIONAL.has(r))) return "national";
  if (identity.roles.some((r) => REGIONAL.has(r))) return identity.national ? "national" : "regional";
  return null;
}

/** «اللجنة الجهوية برئاسة السيد والي نابل» or «اللجنة الوطنية برئاسة السيد وزير الداخلية», under the page title. */
export function CommitteeHeading() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const gouvernorats = useGouvernorats();
  const identity = user?.identity;
  const which = identity ? committeeOf(identity) : null;
  if (!identity || !which) return null;
  const text =
    which === "national"
      ? t("committeeHeading.national")
      : t("committeeHeading.regional", { name: gouvernorats.nameOf(identity.gouvernoratCode) ?? "" });
  return <p className="committee-heading">{text}</p>;
}
