import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/shared/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-6xl font-bold text-primary">404</p>
      <div>
        <h1 className="text-xl font-semibold">Страница не найдена</h1>
        <p className="text-sm text-muted-foreground">
          Возможно, задача была удалена или ссылка неверна.
        </p>
      </div>
      <Button asChild>
        <Link to="/">
          <ArrowLeft className="h-4 w-4" />
          На главную
        </Link>
      </Button>
    </div>
  );
}
