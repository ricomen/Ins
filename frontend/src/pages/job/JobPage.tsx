import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArrowLeft,
  Clock3,
  FileImage,
  FileVideo,
  Loader2,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { fetchJob } from "@/entities/job/api/jobApi";
import { jobKindLabel } from "@/entities/job/ui/job-kind-label";
import { JobProgress } from "@/entities/job/ui/job-progress";
import { StatusBadge } from "@/entities/job/ui/status-badge";
import { useJobActions } from "@/features/job-actions/model/useJobActions";
import { formatBytes, formatDate } from "@/shared/lib/utils";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Separator } from "@/shared/ui/separator";
import { Skeleton } from "@/shared/ui/skeleton";

export function JobPage() {
  const { id } = useParams<{ id: string }>();
  const jobId = id ?? "";
  const navigate = useNavigate();
  const { retry, remove, downloadFile, downloadArchive } = useJobActions();

  const query = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => fetchJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (current) => {
      const data = current.state.data;
      return data && (data.status === "queued" || data.status === "running")
        ? 2_000
        : false;
    },
  });

  if (query.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/jobs">
            <ArrowLeft className="h-4 w-4" />
            К истории
          </Link>
        </Button>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Не удалось загрузить задачу</AlertTitle>
          <AlertDescription>
            {query.error instanceof Error
              ? query.error.message
              : "Задача не найдена"}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const job = query.data;
  const files = [...job.files].sort((a, b) => a.position - b.position);
  const title = job.author ? `@${job.author}` : job.title ?? job.id.slice(0, 8);
  const sourceUrl = job.normalized_url ?? job.url;
  const canRetry = job.status === "failed" || job.status === "partial";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Button variant="ghost" size="sm" asChild className="-ml-2">
            <Link to="/jobs">
              <ArrowLeft className="h-4 w-4" />
              К истории
            </Link>
          </Button>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={job.status} />
            <span className="text-sm text-muted-foreground">
              {jobKindLabel(job.kind)}
            </span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="block max-w-2xl truncate text-sm text-primary hover:underline"
          >
            {sourceUrl}
          </a>
        </div>

        <div className="flex flex-wrap gap-2">
          {files.length > 0 && (
            <Button onClick={() => downloadArchive(job)}>
              <Archive className="h-4 w-4" />
              Скачать ZIP
            </Button>
          )}
          {canRetry && (
            <Button
              variant="outline"
              onClick={() => retry.mutate(job.id)}
              disabled={retry.isPending}
            >
              {retry.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Повторить
            </Button>
          )}
          <Button
            variant="outline"
            className="text-rose-600 hover:text-rose-700"
            disabled={remove.isPending}
            onClick={() => {
              if (window.confirm("Удалить задачу и все файлы?")) {
                remove.mutate(job.id, {
                  onSuccess: () => navigate("/jobs"),
                });
              }
            }}
          >
            <Trash2 className="h-4 w-4" />
            Удалить
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Прогресс</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <JobProgress
              progress={job.progress}
              downloaded={job.downloaded_items}
              total={job.total_items}
            />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Файлов" value={String(job.total_items)} />
              <Metric label="Скачано" value={String(job.downloaded_items)} />
              <Metric label="Прогресс" value={`${job.progress}%`} />
              <Metric
                label="Размер"
                value={formatBytes(
                  files.reduce((sum, file) => sum + file.size, 0),
                )}
              />
            </div>
            {job.caption && (
              <>
                <Separator />
                <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                  {job.caption}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Детали</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Detail label="Тип" value={jobKindLabel(job.kind)} />
            <Detail label="Создана" value={formatDate(job.created_at)} />
            <Detail label="Запущена" value={formatDate(job.started_at)} />
            <Detail label="Завершена" value={formatDate(job.finished_at)} />
            {job.kind === "profile" && (
              <>
                <Detail
                  label="Stories"
                  value={
                    job.options.include_stories === false ? "нет" : "да"
                  }
                />
                <Detail
                  label="Highlights"
                  value={
                    job.options.include_highlights === true ? "да" : "нет"
                  }
                />
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {job.error && (
        <Alert variant={job.status === "failed" ? "destructive" : "warning"}>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {job.status === "failed" ? "Задача завершилась ошибкой" : "Замечания"}
          </AlertTitle>
          <AlertDescription>{job.error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Файлы</CardTitle>
          <span className="text-xs text-muted-foreground">
            {files.length > 0
              ? `${files.length} файлов`
              : job.status === "running"
                ? "Скачивание..."
                : "Пока нет файлов"}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {files.length === 0 ? (
            <div className="flex min-h-32 items-center justify-center p-6 text-sm text-muted-foreground">
              {job.status === "queued" || job.status === "running" ? (
                <span className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4" />
                  Файлы появятся после скачивания
                </span>
              ) : (
                "В этой задаче нет скачанных файлов"
              )}
            </div>
          ) : (
            <ul className="divide-y">
              {files.map((file) => {
                const Icon = file.kind === "video" ? FileVideo : FileImage;
                return (
                  <li
                    key={file.id}
                    className="flex flex-wrap items-center gap-3 p-4"
                  >
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">
                        {file.filename}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatBytes(file.size)}
                        {file.content_type ? ` · ${file.content_type}` : ""}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => downloadFile(job, file)}
                    >
                      Скачать
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  );
}
