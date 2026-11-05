import { ExternalLink, RefreshCw, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { Job } from "@/entities/job/model/types";
import { jobKindLabel } from "@/entities/job/ui/job-kind-label";
import { JobProgress } from "@/entities/job/ui/job-progress";
import { StatusBadge } from "@/entities/job/ui/status-badge";
import { useJobActions } from "@/features/job-actions/model/useJobActions";
import { formatDate } from "@/shared/lib/utils";
import { Button } from "@/shared/ui/button";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

interface JobTableProps {
  jobs: Job[];
  isLoading?: boolean;
  emptyText?: string;
}

export function JobTable({
  jobs,
  isLoading = false,
  emptyText = "Задач пока нет",
}: JobTableProps) {
  const { retry, remove } = useJobActions();

  if (isLoading) {
    return (
      <div className="space-y-2 p-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="flex min-h-40 flex-col items-center justify-center gap-2 p-8 text-center">
        <p className="text-sm font-medium">{emptyText}</p>
        <p className="text-xs text-muted-foreground">
          Вставьте ссылку в форму выше, чтобы создать первую задачу.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Задача</TableHead>
          <TableHead className="hidden md:table-cell">Тип</TableHead>
          <TableHead>Статус</TableHead>
          <TableHead className="hidden min-w-36 lg:table-cell">Прогресс</TableHead>
          <TableHead className="hidden xl:table-cell">Создана</TableHead>
          <TableHead className="w-28 text-right">Действия</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => {
          const title =
            job.author ? `@${job.author}` : job.title ?? job.normalized_url ?? job.url;
          return (
            <TableRow key={job.id}>
              <TableCell className="max-w-[280px]">
                <Link
                  to={`/jobs/${job.id}`}
                  className="block truncate font-medium hover:text-primary"
                >
                  {title}
                </Link>
                <span className="block truncate text-xs text-muted-foreground">
                  {job.normalized_url ?? job.url}
                </span>
                {job.error && (
                  <span
                    className="mt-1 block truncate text-xs text-rose-600"
                    title={job.error}
                  >
                    {job.error}
                  </span>
                )}
              </TableCell>
              <TableCell className="hidden md:table-cell">
                <span className="text-sm text-muted-foreground">
                  {jobKindLabel(job.kind)}
                </span>
              </TableCell>
              <TableCell>
                <StatusBadge status={job.status} />
              </TableCell>
              <TableCell className="hidden lg:table-cell">
                <JobProgress
                  progress={job.progress}
                  downloaded={job.downloaded_items}
                  total={job.total_items}
                />
              </TableCell>
              <TableCell className="hidden whitespace-nowrap text-sm text-muted-foreground xl:table-cell">
                {formatDate(job.created_at)}
              </TableCell>
              <TableCell>
                <div className="flex items-center justify-end gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    asChild
                    title="Открыть задачу"
                  >
                    <Link to={`/jobs/${job.id}`}>
                      <ExternalLink className="h-4 w-4" />
                    </Link>
                  </Button>
                  {(job.status === "failed" || job.status === "partial") && (
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Повторить"
                      disabled={retry.isPending && retry.variables === job.id}
                      onClick={() => retry.mutate(job.id)}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    title="Удалить"
                    disabled={remove.isPending && remove.variables === job.id}
                    onClick={() => {
                      if (window.confirm("Удалить задачу и все файлы?")) {
                        remove.mutate(job.id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-rose-600" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
