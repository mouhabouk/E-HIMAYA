import type { ApiClient } from "./api";
import type { VolunteerDecision, VolunteerStatus } from "./opsTypes";
import type { Page } from "./types";

const enc = encodeURIComponent;
const doctorPath = (id: string) => `/api/v1/staff/doctors/${enc(id)}`;

/** Specialties a doctor can declare (phase C1-a); labels under `doctors.specialty`. */
export const SPECIALTIES = [
  "general_practice",
  "emergency_medicine",
  "anesthesia_icu",
  "cardiology",
  "pulmonology",
  "neurology",
  "pediatrics",
  "obstetrics_gynecology",
  "internal_medicine",
  "endocrinology",
  "nephrology",
  "gastroenterology",
  "allergy_immunology",
  "infectious_diseases",
  "dermatology_burns",
  "orthopedics",
  "general_surgery",
  "psychiatry",
  "toxicology",
  "ophthalmology",
  "ent",
] as const;
export type Specialty = (typeof SPECIALTIES)[number];

export const DOCTOR_KINDS = ["volunteer", "civil_protection"] as const;
export type DoctorKind = (typeof DOCTOR_KINDS)[number];

/** A doctor's registration in the list (no phone, no registration number). */
export interface StaffDoctor {
  id: string;
  full_name: string | null;
  kind: DoctorKind;
  specialties: Specialty[];
  workplace: string;
  gouvernorat_code: number;
  cp_unit: string | null;
  status: VolunteerStatus;
  available: boolean;
  submitted_at: string;
  /** End of the current term on the medical committee; null when not a member. */
  committee_until: string | null;
}

export interface StaffDoctorDetail extends StaffDoctor {
  phone: string | null;
  email: string | null;
  licence_no: string | null;
  cp_staff_no: string | null;
  review_reason: string | null;
  reviews: { decision: string; reason: string | null; at: string }[];
}

export interface DoctorFilters {
  status?: VolunteerStatus | "";
  kind?: DoctorKind | "";
  specialty?: Specialty | "";
  gouvernorat_code?: number | null;
  q?: string;
}

/** The national medical committee (design §11): members, seats, and who can be appointed. */
export interface CommitteeMember extends StaffDoctor {
  committee_since: string;
}

export interface MedicalCommittee {
  members: CommitteeMember[];
  max_members: number;
}

/** Term lengths offered when appointing or renewing (the API accepts 1 to 24 months). */
export const COMMITTEE_TERMS = [6, 12, 24] as const;

export const committeeKeys = {
  all: ["medical-committee"] as const,
  candidates: (q: string) => ["medical-committee", "candidates", q] as const,
};

export const doctorKeys = {
  all: ["doctors"] as const,
  list: (filters: DoctorFilters) => ["doctors", filters] as const,
  one: (id: string) => ["doctor", id] as const,
};

/** Doctors' registrations (phase C1-a, docs/phase-c/design-medical-axis.md §2). */
export function doctorsApi(api: ApiClient) {
  return {
    doctors: (filters: DoctorFilters, opts: { cursor?: string | null; signal?: AbortSignal } = {}) =>
      api.request<Page<StaffDoctor>>("/api/v1/staff/doctors", {
        query: {
          status: filters.status || undefined,
          kind: filters.kind || undefined,
          specialty: filters.specialty || undefined,
          gouvernorat_code: filters.gouvernorat_code ?? undefined,
          q: filters.q?.trim() || undefined,
          limit: 50,
          cursor: opts.cursor ?? undefined,
        },
        signal: opts.signal,
      }),
    /** Opening a doctor's file is written to the audit log (`doctor.view`): fetch it only when shown. */
    doctor: (id: string, signal?: AbortSignal) => api.request<StaffDoctorDetail>(doctorPath(id), { signal }),
    reviewDoctor: (id: string, decision: VolunteerDecision, reason?: string) =>
      api.request<StaffDoctorDetail>(`${doctorPath(id)}/review`, {
        method: "POST",
        body: reason?.trim() ? { decision, reason: reason.trim() } : { decision },
      }),
    medicalCommittee: (signal?: AbortSignal) =>
      api.request<MedicalCommittee>("/api/v1/staff/medical-committee", { signal }),
    committeeCandidates: (q: string, signal?: AbortSignal) =>
      api.request<StaffDoctor[]>("/api/v1/staff/medical-committee/candidates", {
        query: { q: q.trim() || undefined },
        signal,
      }),
    /** Appoints, or renews a member, for `months` from today (audited, e-mailed to the doctor). */
    appointMember: (id: string, months: number, reason?: string) =>
      api.request<MedicalCommittee>(`/api/v1/staff/medical-committee/${enc(id)}`, {
        method: "PUT",
        body: reason?.trim() ? { months, reason: reason.trim() } : { months },
      }),
    revokeMember: (id: string, reason: string) =>
      api.request<MedicalCommittee>(`/api/v1/staff/medical-committee/${enc(id)}/revoke`, {
        method: "POST",
        body: { reason: reason.trim() },
      }),
  };
}
