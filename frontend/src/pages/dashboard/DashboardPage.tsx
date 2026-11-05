import { useQuery } from "@tanstack/react-query";
import { ArrowRight, CheckCircle2, Film, Images, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { fetchJobs, fetchStats } from "@/entities/job/api/jobApi";
import { JobTable } from "@/widgets/job-table/ui/JobTable";
import { JobForm } from "@/widgets/job-form/ui/JobForm";
import { StatsCards } from "@/widgets/stats-cards/ui/StatsCards";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";

const FEATURES = [
  { icon: Images, text: "Посты и карусели — все файлы" },
  { icon: Film, text: "Reels и видео — MP4" },
  { icon: UserRound, text: "Профили — 12 последних постов + stories" },
  { icon: CheckCircle2, text: "Highlights — при настроенной сессии" },
];

export function DashboardPage() {
  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 5_000,
  });
  const jobsQuery = useQuery({
    queryKey: ["jobs", { limit: 8 }],
    queryFn: () => fetchJobs({ limit: 8 }),
    refetchInterval: 5_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Обзор</h1>
        <p className="text-sm text-muted-foreground">
          Вставьте ссылку, поставьте задачу в очередь и скачайте файлы или ZIP.
        </p>
      </div>

      <StatsCards
        stats={statsQuery.data}
        isLoading={statsQuery.isLoading}
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <JobForm />
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Что можно скачать</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3">
              {FEATURES.map((feature) => (
                <li key={feature.text} className="flex items-start gap-2.5">
                  <feature.icon className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span className="text-sm text-muted-foreground">
                    {feature.text}
                  </span>
                </li>
              ))}
            </ul>
            <div className="rounded-lg border bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
              Очередь последовательная: один IP, пауза 3–5 секунд между
              запросами. Файлы хранятся 24 часа, затем удаляются автоматически.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Последние задачи</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/jobs">
              Вся история
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <JobTable
            jobs={jobsQuery.data?.items ?? []}
            isLoading={jobsQuery.isLoading}
            emptyText="Задач пока нет"
          />
        </CardContent>
      </Card>
    </div>
  );
}
