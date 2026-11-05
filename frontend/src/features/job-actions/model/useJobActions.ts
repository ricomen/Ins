import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  deleteJob,
  downloadJobArchive,
  downloadJobFile,
  retryJob,
} from "@/entities/job/api/jobApi";
import type { Job, JobFile } from "@/entities/job/model/types";
import { getErrorMessage } from "@/shared/api/client";

export function useJobActions() {
  const queryClient = useQueryClient();

  const invalidate = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      queryClient.invalidateQueries({ queryKey: ["stats"] }),
      queryClient.invalidateQueries({ queryKey: ["job"] }),
    ]);
  }, [queryClient]);

  const retry = useMutation({
    mutationFn: retryJob,
    onSuccess: async (job) => {
      toast.success("Задача снова поставлена в очередь");
      await invalidate();
      queryClient.setQueryData(["job", job.id], job);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: deleteJob,
    onSuccess: async () => {
      toast.success("Задача и файлы удалены");
      await invalidate();
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const downloadFile = useCallback(
    async (job: Job, file: JobFile) => {
      try {
        await downloadJobFile(job.id, file.id, file.filename);
        toast.success("Файл скачан");
      } catch (error) {
        toast.error(getErrorMessage(error));
      }
    },
    [],
  );

  const downloadArchive = useCallback(async (job: Job) => {
    try {
      await downloadJobArchive(job.id, job.id.slice(0, 8));
      toast.success("ZIP-архив скачан");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }, []);

  return { retry, remove, downloadFile, downloadArchive };
}
