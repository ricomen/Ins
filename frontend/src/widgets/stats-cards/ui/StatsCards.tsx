import { Clock3, Layers3, Loader2, CheckCircle2, CircleAlert, CircleX } from "lucide-react";

import type { Stats } from "@/entities/job/model/types";
import { Skeleton } from "@/shared/ui/skeleton";

const ITEMS: Array<{
  key: keyof Stats;
  label: string;
  icon: typeof Layers3;
  className: string;
}> = [
  { key: "total", label: "Всего", icon: Layers3, className: "text-slate-600" },
  { key: "queued", label: "В очереди", icon: Clock3, className: "text-slate-500" },
  { key: "running", label: "В работе", icon: Loader2, className: "text-blue-600" },
  { key: "success", label: "Готово", icon: CheckCircle2, className: "text-emerald-600" },
  { key: "partial", label: "Частично", icon: CircleAlert, className: "text-amber-600" },
  { key: "failed", label: "Ошибки", icon: CircleX, className: "text-rose-600" },
];

export function StatsCards({
  stats,
  isLoading,
}: {
  stats?: Stats;
  isLoading: boolean;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
      {ITEMS.map((item) => (
        <div
          key={item.key}
          className="rounded-xl border bg-card p-4 shadow-sm"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {item.label}
            </span>
            <item.icon className={`h-4 w-4 ${item.className}`} />
          </div>
          {isLoading || !stats ? (
            <Skeleton className="mt-3 h-7 w-12" />
          ) : (
            <p className="mt-2 text-2xl font-semibold tabular-nums">
              {stats[item.key]}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
