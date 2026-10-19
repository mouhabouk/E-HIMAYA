/** Types mirroring docs/api/phase-2-contract.md (sections 3 and 5). */

export const REPORT_STATUSES = ["received", "in_progress", "intervened", "ongoing", "closed", "rejected"] as const;
export type ReportStatus = (typeof REPORT_STATUSES)[number];

export const CATEGORIES = [
  "sos",
  "fire",
  "flood",
  "traffic_accident",
  "drowning",
  "landslide",
  "chemical_leak",
  "medical",
  "other",
] as const;
export type Category = (typeof CATEGORIES)[number];

export type ReporterKind = "citizen" | "anonymous";
export type MediaKind = "image" | "video" | "audio";
export type MediaStatus = "uploading" | "verifying" | "stored" | "rejected";
export type TextLang = "ar" | "fr" | "en";

export interface GeoPoint {
  lat: number;
  lon: number;
  accuracy_m?: number | null;
}

export interface Media {
  id: string;
  kind: MediaKind;
  bytes: number | null;
  sha256: string;
  status: MediaStatus;
  /** MIME type declared at upload (e.g. video/mp4). */
  content_type?: string | null;
  created_at?: string;
  /** Pre-signed URL (10 minutes), only in StaffReportDetail and only when status is "stored". */
  url?: string | null;
}

export interface StaffReport {
  id: string;
  tracking_code: string;
  client_uuid?: string;
  category: Category;
  status: ReportStatus;
  text: string | null;
  lang: TextLang | null;
  location: GeoPoint;
  gouvernorat_code: number | null;
  delegation_id: number | null;
  created_at: string;
  received_at: string;
  updated_at: string;
  reporter_kind: ReporterKind;
  media_count: number;
  media?: Media[];
}

export interface HistoryEntry {
  status: ReportStatus;
  at: string;
  /** Who made the change (staff subject/username, or the system). */
  actor?: string | null;
  note?: string | null;
}

export type Reporter =
  | { kind: "citizen"; first_name: string | null; last_name: string | null; phone: string | null }
  | { kind: "anonymous" };

export interface StaffReportDetail extends StaffReport {
  history: HistoryEntry[];
  media: Media[];
  reporter: Reporter;
  /** Statuses reachable from the current one, computed by the server (authoritative). */
  allowed_transitions?: ReportStatus[];
}

export interface Page<T> {
  items: T[];
  next_cursor: string | null;
}

export interface Kpis {
  since: string;
  total: number;
  by_status: Partial<Record<ReportStatus, number>>;
  by_category: Partial<Record<Category, number>>;
  by_gouvernorat: { code: number | null; count: number }[];
  avg_first_response_s: number | null;
}

export interface Gouvernorat {
  code: number;
  iso_code: string;
  name: string;
  name_ar: string;
  name_fr: string;
  delegation_count: number;
}

export interface Me {
  subject: string;
  realm: string;
  roles: string[];
  gouvernorat_code: number | null;
  is_staff: boolean;
}

export function isReportStatus(v: unknown): v is ReportStatus {
  return typeof v === "string" && (REPORT_STATUSES as readonly string[]).includes(v);
}

export function isCategory(v: unknown): v is Category {
  return typeof v === "string" && (CATEGORIES as readonly string[]).includes(v);
}
