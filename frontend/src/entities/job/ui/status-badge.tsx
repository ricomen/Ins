import { Badge } from "@/shared/ui/badge";
import type { JobStatus } from "@/entities/job/model/types";

const STATUS: Record<
  JobStatus,
  { label: string; variant: "secondary" | "info" | "success" | "warning" | "destructive" }
> = {
  queued: { label: "В очереди", variant: "secondary" },
  running: { label: "В работе", variant: "info" },
  success: { label: "Готово", variant: "success" },
  partial: { label: "Частично", variant: "warning" },
  failed: { label: "Ошибка", variant: "destructive" },
};

export function StatusBadge({ status }: { status: JobStatus }) {
  const item = STATUS[status] ?? STATUS.failed;
  return <Badge variant={item.variant}>{item.label}</Badge>;
}
