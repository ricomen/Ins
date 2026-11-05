import { apiBlob, apiFetch, downloadBlob } from "@/shared/api/client";

import type {
  AppConfig,
  BatchResult,
  Job,
  JobList,
  JobStatus,
  Stats,
} from "../model/types";

export interface JobsQuery {
  status?: JobStatus | "all";
  kind?: string;
  limit?: number;
  offset?: number;
}

export function fetchJobs(query: JobsQuery = {}): Promise<JobList> {
  const params = new URLSearchParams();
  if (query.status && query.status !== "all") params.set("status", query.status);
  if (query.kind) params.set("kind", query.kind);
  params.set("limit", String(query.limit ?? 20));
  params.set("offset", String(query.offset ?? 0));
  return apiFetch<JobList>(`/jobs?${params.toString()}`);
}

export function fetchJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/jobs/${jobId}`);
}

export function createJob(payload: {
  url: string;
  include_stories: boolean;
  include_highlights: boolean;
}): Promise<Job> {
  return apiFetch<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createBatch(payload: {
  urls: string[];
  include_stories: boolean;
  include_highlights: boolean;
}): Promise<BatchResult> {
  return apiFetch<BatchResult>("/jobs/batch", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function retryJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/jobs/${jobId}/retry`, { method: "POST" });
}

export function deleteJob(jobId: string): Promise<void> {
  return apiFetch<void>(`/jobs/${jobId}`, { method: "DELETE" });
}

export function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/stats");
}

export function fetchAppConfig(): Promise<AppConfig> {
  return apiFetch<AppConfig>("/config");
}

export async function downloadJobFile(
  jobId: string,
  fileId: string,
  filename: string,
): Promise<void> {
  const blob = await apiBlob(`/jobs/${jobId}/files/${fileId}`);
  downloadBlob(blob, filename);
}

export async function downloadJobArchive(
  jobId: string,
  shortId: string,
): Promise<void> {
  const blob = await apiBlob(`/jobs/${jobId}/archive`);
  downloadBlob(blob, `ins-${shortId}.zip`);
}
