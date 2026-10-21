import type { ApiClient } from "./api";
import type {
  Certificate,
  CreatedInvitation,
  Equipment,
  EquipmentInput,
  Gouvernorat,
  Hazmat,
  HazmatInput,
  Invitation,
  InvitationPreview,
  MapFeature,
  MapFeatureInput,
  Member,
  MyOrg,
  NewReport,
  DocumentKind,
  DocumentVersion,
  OrgCard,
  OrgDocument,
  OrgReport,
  OrgRole,
  Organization,
  Page,
  PublicCertificate,
  Report,
  TeamMember,
  TeamMemberInput,
  TextLang,
} from "./types";

const enc = encodeURIComponent;
const orgPath = (id: string) => `/api/v1/orgs/${enc(id)}`;

/** The three safety registers share the same CRUD shape (§3, §4, §5). */
export type RegisterName = "team" | "hazmat" | "equipment" | "features";
export interface RegisterTypes {
  team: { item: TeamMember; input: TeamMemberInput };
  hazmat: { item: Hazmat; input: HazmatInput };
  equipment: { item: Equipment; input: EquipmentInput };
  features: { item: MapFeature; input: MapFeatureInput };
}

/** Typed calls for docs/api/phase-4-contract.md (portal side) and the phase 2 calls the portal needs. */
export function portalApi(api: ApiClient) {
  return {
    // §1 institutions
    myOrgs: (signal?: AbortSignal) => api.request<MyOrg[]>("/api/v1/orgs/mine", { signal }),
    org: (id: string, signal?: AbortSignal) => api.request<Organization>(orgPath(id), { signal }),
    createOrg: (card: OrgCard) => api.request<Organization>("/api/v1/orgs", { method: "POST", body: card }),
    updateOrg: (id: string, card: OrgCard, version: number) =>
      api.request<Organization>(orgPath(id), { method: "PUT", body: { ...card, version } }),
    resubmit: (id: string) => api.request<Organization>(`${orgPath(id)}/resubmit`, { method: "POST" }),

    // §2 members and invitations
    members: (id: string, signal?: AbortSignal) => api.request<Member[]>(`${orgPath(id)}/members`, { signal }),
    setMemberRole: (id: string, userId: string, role: OrgRole) =>
      api.request<Member>(`${orgPath(id)}/members/${enc(userId)}`, { method: "PUT", body: { role } }),
    removeMember: (id: string, userId: string) =>
      api.request<undefined>(`${orgPath(id)}/members/${enc(userId)}`, { method: "DELETE" }),
    invitations: (id: string, signal?: AbortSignal) =>
      api.request<Invitation[]>(`${orgPath(id)}/invitations`, { signal }),
    invite: (id: string, email: string, role: OrgRole) =>
      api.request<CreatedInvitation>(`${orgPath(id)}/invitations`, { method: "POST", body: { email, role } }),
    revokeInvitation: (id: string, invitationId: string) =>
      api.request<undefined>(`${orgPath(id)}/invitations/${enc(invitationId)}`, { method: "DELETE" }),
    invitation: (token: string, signal?: AbortSignal) =>
      api.request<InvitationPreview>(`/api/v1/invitations/${enc(token)}`, { signal }),
    acceptInvitation: (token: string) =>
      api.request<{ org_id: string; role: OrgRole }>(`/api/v1/invitations/${enc(token)}/accept`, { method: "POST" }),

    // §3–§5 registers
    list: <R extends RegisterName>(id: string, register: R, signal?: AbortSignal) =>
      api.request<RegisterTypes[R]["item"][]>(`${orgPath(id)}/${register}`, { signal }),
    create: <R extends RegisterName>(id: string, register: R, input: RegisterTypes[R]["input"]) =>
      api.request<RegisterTypes[R]["item"]>(`${orgPath(id)}/${register}`, { method: "POST", body: input }),
    update: <R extends RegisterName>(id: string, register: R, itemId: string, input: RegisterTypes[R]["input"]) =>
      api.request<RegisterTypes[R]["item"]>(`${orgPath(id)}/${register}/${enc(itemId)}`, { method: "PUT", body: input }),
    remove: (id: string, register: RegisterName, itemId: string) =>
      api.request<undefined>(`${orgPath(id)}/${register}/${enc(itemId)}`, { method: "DELETE" }),

    // §6 documents
    documents: (id: string, signal?: AbortSignal) => api.request<OrgDocument[]>(`${orgPath(id)}/documents`, { signal }),
    createDocument: (id: string, kind: DocumentKind, title: string) =>
      api.request<OrgDocument>(`${orgPath(id)}/documents`, { method: "POST", body: { kind, title } }),
    renameDocument: (id: string, docId: string, title: string) =>
      api.request<OrgDocument>(`${orgPath(id)}/documents/${enc(docId)}`, { method: "PUT", body: { title } }),
    deleteDocument: (id: string, docId: string) =>
      api.request<undefined>(`${orgPath(id)}/documents/${enc(docId)}`, { method: "DELETE" }),
    versions: (id: string, docId: string, signal?: AbortSignal) =>
      api.request<DocumentVersion[]>(`${orgPath(id)}/documents/${enc(docId)}/versions`, { signal }),
    downloadUrl: (id: string, docId: string, version: number) =>
      api.request<{ url: string }>(`${orgPath(id)}/documents/${enc(docId)}/versions/${version}/download`),

    // §7 certificates
    certificates: (id: string, signal?: AbortSignal) =>
      api.request<Certificate[]>(`${orgPath(id)}/certificates`, { signal }),
    generateCertificate: (id: string) => api.request<Certificate>(`${orgPath(id)}/certificate`, { method: "POST" }),
    certificatePdf: (id: string, certId: string) =>
      api.request<{ url: string }>(`${orgPath(id)}/certificates/${enc(certId)}/pdf`),
    submitCertificate: (id: string, certId: string) =>
      api.request<Certificate>(`${orgPath(id)}/certificates/${enc(certId)}/submit`, { method: "POST" }),
    publicCertificate: (code: string, signal?: AbortSignal) =>
      api.request<PublicCertificate>(`/api/v1/public/certificates/${enc(code)}`, { signal, anonymous: true }),

    certificateKey: (signal?: AbortSignal) =>
      api.request<{ algorithm: string; public_key: string | null; signed_message: string; key_id?: string | null }>(
        "/api/v1/public/certificate-key",
        { signal, anonymous: true },
      ),

    // §8 reports on behalf of the institution, phase 2 §2 consent
    orgReports: (id: string, cursor?: string | null, signal?: AbortSignal) =>
      api.request<Page<OrgReport>>(`${orgPath(id)}/reports`, { query: { limit: 50, cursor }, signal }),
    createReport: (report: NewReport) => api.request<Report>("/api/v1/reports", { method: "POST", body: report }),
    charter: (signal?: AbortSignal) => api.request<{ version: string }>("/api/v1/charter", { signal }),
    acceptCharter: (version: string, locale: TextLang) =>
      api.request<{ charter_version: string; accepted_at: string }>("/api/v1/consents", {
        method: "POST",
        body: { charter_version: version, locale, platform: "web" },
      }),

    // geo reference (public)
    gouvernorats: (signal?: AbortSignal) =>
      api.request<Gouvernorat[]>("/api/v1/geo/gouvernorats", { query: { lang: "ar" }, signal, anonymous: true }),
  };
}

export type PortalApi = ReturnType<typeof portalApi>;

export const queryKeys = {
  myOrgs: ["orgs", "mine"] as const,
  org: (id: string) => ["org", id] as const,
  register: (id: string, register: RegisterName) => ["org", id, register] as const,
  members: (id: string) => ["org", id, "members"] as const,
  invitations: (id: string) => ["org", id, "invitations"] as const,
  documents: (id: string) => ["org", id, "documents"] as const,
  versions: (id: string, docId: string) => ["org", id, "documents", docId, "versions"] as const,
  certificates: (id: string) => ["org", id, "certificates"] as const,
  reports: (id: string) => ["org", id, "reports"] as const,
  invitation: (token: string) => ["invitation", token] as const,
  publicCertificate: (code: string) => ["public-certificate", code] as const,
  certificateKey: ["certificate-key"] as const,
  gouvernorats: ["gouvernorats"] as const,
};
