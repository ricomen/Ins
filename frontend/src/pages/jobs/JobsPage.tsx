import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, History } from "lucide-react";

import { fetchJobs } from "@/entities/job/api/jobApi";
import type { JobStatus } from "@/entities/job/model/types";
import { JobTable } from "@/widgets/job-table/ui/JobTable";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Select } from "@/shared/ui/select";

const PAGE_SIZE = 20;

const STATUS_OPTIONS: Array<{ value: JobStatus | "all"; label: string }> = [
  { value: "all", label: "Все статусы" },
  { value: "queued", label: "В очереди" },
  { value: "running", label: "В работе" },
  { value: "success", label: "Готово" },
  { value: "partial", label: "Частично" },
  { value: "failed", label: "Ошибка" },
];

export function JobsPage() {
  const [status, setStatus] = useState<JobStatus | "all">("all");
  const [page, setPage] = useState(0);

  const query = useQuery({
    queryKey: ["jobs", { status, page }],
    queryFn: () =>
      fetchJobs({
        status,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    refetchInterval: 5_000,
  });

  const total = query.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <History className="h-5 w-5 text-primary" />
            История задач
          </h1>
          <p className="text-sm text-muted-foreground">
            Всего задач: {total}. Статус обновляется автоматически.
          </p>
        </div>
        <div className="w-full sm:w-56">
          <Select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as JobStatus | "all");
              setPage(0);
            }}
            aria-label="Фильтр по статусу"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">
            {status === "all" ? "Все задачи" : "Отфильтрованные задачи"}
          </CardTitle>
          <span className="text-xs text-muted-foreground">
            Страница {page + 1} из {pages}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <JobTable
            jobs={query.data?.items ?? []}
            isLoading={query.isLoading}
            emptyText="По этому фильтру задач нет"
          />
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 0}
          onClick={() => setPage((value) => Math.max(0, value - 1))}
        >
          <ChevronLeft className="h-4 w-4" />
          Назад
        </Button>
        <span className="text-sm text-muted-foreground">
          {total === 0
            ? "0 задач"
            : `${page * PAGE_SIZE + 1}–${Math.min(
                (page + 1) * PAGE_SIZE,
                total,
              )} из ${total}`}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={page + 1 >= pages}
          onClick={() => setPage((value) => value + 1)}
        >
          Вперёд
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
