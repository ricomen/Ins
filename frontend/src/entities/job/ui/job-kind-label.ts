import type { JobKind } from "@/entities/job/model/types";

const KIND_LABELS: Record<JobKind, string> = {
  post: "Публикация",
  profile: "Профиль",
  stories: "Stories",
  highlights: "Highlights",
};

export function jobKindLabel(kind: JobKind): string {
  return KIND_LABELS[kind] ?? kind;
}
