import { LogOut } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "@/app/providers/AuthProvider";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";

const NAV_ITEMS = [
  { to: "/", label: "Обзор", end: true },
  { to: "/jobs", label: "История", end: false },
];

function NavItems({ mobile = false }: { mobile?: boolean }) {
  return (
    <>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              mobile
                ? isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted"
                : isActive
                  ? "bg-white/10 text-white"
                  : "text-slate-400 hover:bg-white/5 hover:text-white",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

export function AppLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-slate-800 bg-slate-950 lg:flex">
        <div className="flex h-16 items-center gap-2 border-b border-white/10 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-fuchsia-500 via-rose-500 to-amber-400 text-sm font-bold text-white">
            I
          </div>
          <div>
            <p className="text-sm font-semibold text-white">Ins</p>
            <p className="text-[11px] text-slate-400">Instagram downloader</p>
          </div>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-4">
          <NavItems />
        </nav>
        <div className="border-t border-white/10 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs text-slate-400">Администратор</span>
            <Badge variant="outline" className="border-white/20 text-slate-300">
              admin
            </Badge>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start text-slate-300 hover:bg-white/10 hover:text-white"
            onClick={handleLogout}
          >
            <LogOut className="h-4 w-4" />
            Выйти
          </Button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b bg-white/85 backdrop-blur">
          <div className="flex h-16 items-center justify-between gap-4 px-4 lg:px-8">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 lg:hidden">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-fuchsia-500 via-rose-500 to-amber-400 text-sm font-bold text-white">
                  I
                </div>
                <span className="font-semibold">Ins</span>
              </div>
              <p className="hidden text-sm text-muted-foreground lg:block">
                Панель управления загрузками
              </p>
              <nav className="flex items-center gap-1 lg:hidden">
                <NavItems mobile />
              </nav>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="lg:hidden"
            >
              <LogOut className="h-4 w-4" />
              Выйти
            </Button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl p-4 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
