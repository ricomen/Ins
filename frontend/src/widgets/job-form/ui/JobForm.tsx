import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, Link2, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

import {
  createBatch,
  createJob,
  fetchAppConfig,
} from "@/entities/job/api/jobApi";
import { getErrorMessage } from "@/shared/api/client";
import { Alert, AlertDescription, AlertTitle } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Checkbox } from "@/shared/ui/checkbox";
import { Label } from "@/shared/ui/label";
import { Textarea } from "@/shared/ui/textarea";

const PLACEHOLDER = `https://www.instagram.com/p/...
https://www.instagram.com/reel/...
https://www.instagram.com/natgeo/`;

export function JobForm() {
  const [text, setText] = useState("");
  const [includeStories, setIncludeStories] = useState(true);
  const [includeHighlights, setIncludeHighlights] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const configQuery = useQuery({
    queryKey: ["config"],
    queryFn: fetchAppConfig,
  });
  const config = configQuery.data;

  const mutation = useMutation({
    mutationFn: async (urls: string[]) => {
      if (urls.length === 1) {
        const job = await createJob({
          url: urls[0],
          include_stories: includeStories,
          include_highlights: includeHighlights,
        });
        return { jobs: [job], errors: [] };
      }
      return await createBatch({
        urls,
        include_stories: includeStories,
        include_highlights: includeHighlights,
      });
    },
    onSuccess: async (result) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["stats"] }),
      ]);
      setText("");
      if (result.errors.length > 0) {
        toast.warning(
          `Создано задач: ${result.jobs.length}. Ошибок: ${result.errors.length}`,
        );
      } else {
        toast.success(
          result.jobs.length === 1
            ? "Задача создана"
            : `Создано задач: ${result.jobs.length}`,
        );
      }
      if (result.jobs.length === 1) {
        navigate(`/jobs/${result.jobs[0].id}`);
      }
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const urls = text
    .split(/\s+/)
    .map((value) => value.trim())
    .filter(Boolean);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (urls.length === 0) {
      toast.error("Вставьте хотя бы одну ссылку");
      return;
    }
    if (config && urls.length > config.max_batch_size) {
      toast.error(`Максимум ${config.max_batch_size} ссылок за один раз`);
      return;
    }
    if (includeHighlights && config && !config.highlights_available) {
      toast.error(config.highlights_reason ?? "Highlights недоступны");
      return;
    }
    mutation.mutate(urls);
  };

  return (
    <Card className="animate-fade-in">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-primary" />
          Новая задача
        </CardTitle>
        <CardDescription>
          Одна ссылка или пакет: посты, Reels, карусели, stories и профили.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <Textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={PLACEHOLDER}
            disabled={mutation.isPending}
            aria-label="Ссылки Instagram"
          />

          <div className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3">
            <div className="flex items-start gap-3">
              <Checkbox
                id="include-stories"
                checked={includeStories}
                onCheckedChange={(value) => setIncludeStories(value === true)}
                disabled={mutation.isPending}
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <Label htmlFor="include-stories" className="cursor-pointer">
                  Скачивать stories
                </Label>
                <span className="block text-xs text-muted-foreground">
                  Для профилей — активные stories вместе с последними постами.
                </span>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox
                id="include-highlights"
                checked={includeHighlights}
                onCheckedChange={(value) => setIncludeHighlights(value === true)}
                disabled={
                  mutation.isPending ||
                  (config ? !config.highlights_available : false)
                }
                className="mt-0.5"
              />
              <div className="space-y-0.5">
                <Label
                  htmlFor="include-highlights"
                  className="flex cursor-pointer items-center gap-1.5"
                >
                  Скачивать highlights
                  <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                </Label>
                <span className="block text-xs text-muted-foreground">
                  Работает для профилей и требует сессию Instagram.
                </span>
              </div>
            </div>
          </div>

          {config && !config.highlights_available && (
            <Alert variant="warning">
              <Info className="h-4 w-4" />
              <AlertTitle>Highlights пока недоступны</AlertTitle>
              <AlertDescription>{config.highlights_reason}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              {urls.length > 0
                ? `Ссылок в очереди: ${urls.length}`
                : "Каждая ссылка — отдельная задача"}
            </p>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              {urls.length > 1 ? "Запустить пакет" : "Скачать"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
