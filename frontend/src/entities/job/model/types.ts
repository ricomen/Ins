export type JobStatus = "queued" | "running" | "success" | "partial" | "failed";

export type JobKind = "post" | "profile" | "stories" | "highlights";

export interface JobFile {
  id: string;
  filename: string;
  size: number;
  content_type: string | null;
  kind: string;
  position: number;
}

export interface Job {
  id: string;
  url: string;
  normalized_url: string | null;
  kind: JobKind;
  status: JobStatus;
  progress: number;
  total_items: number;
  downloaded_items: number;
  author: string | null;
  caption: string | null;
  title: string | null;
  error: string | null;
  options: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  files: JobFile[];
}

export interface JobList {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
}

export interface Stats {
  total: number;
  queued: number;
  running: number;
  success: number;
  partial: number;
  failed: number;
}

export interface AppConfig {
  highlights_available: boolean;
  highlights_reason: string | null;
  max_batch_size: number;
  job_ttl_hours: number;
}

export interface BatchResult {
  jobs: Job[];
  errors: { url: string; error: string }[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
