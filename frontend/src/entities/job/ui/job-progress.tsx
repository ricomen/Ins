import { Progress } from "@/shared/ui/progress";
import { cn } from "@/shared/lib/utils";

interface JobProgressProps {
  progress: number;
  downloaded: number;
  total: number;
  className?: string;
}

export function JobProgress({
  progress,
  downloaded,
  total,
  className,
}: JobProgressProps) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <Progress value={progress} />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{progress}%</span>
        <span>
          {downloaded} / {total || "—"}
        </span>
      </div>
    </div>
  );
}
