import { Activity, FolderKanban, KeyRound, LogOut, Users } from "lucide-react";
import { NavLink, Outlet, Link } from "react-router-dom";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useLogout } from "@/features/auth/hooks";
import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const GENERAL_ITEMS = [
  { to: "/projects", label: "Proyectos", icon: FolderKanban },
  { to: "/executions", label: "Ejecuciones", icon: Activity },
] as const;

const ADMIN_ITEMS = [
  { to: "/users", label: "Usuarios", icon: Users },
  { to: "/api-keys", label: "API Keys", icon: KeyRound },
] as const;

/**
 * App shell: sidebar navigation + header with the current user and logout.
 * The "Usuarios" and "API Keys" entries are admin-only (RBAC, spec 9.4.1/9.4.2).
 */
export default function Layout() {
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r bg-card/50">
        <div className="border-b px-5 py-4">
          <Link to="/" aria-label="CronDok — inicio">
            <Logo />
          </Link>
        </div>
        <nav className="flex flex-1 flex-col gap-6 p-3">
          <NavSection label="General" items={GENERAL_ITEMS} />
          {user?.role === "admin" && <NavSection label="Administración" items={ADMIN_ITEMS} />}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b px-6">
          <div />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {user && (
              <div className="flex items-center gap-2 border-l pl-3">
                <span className="text-sm font-medium">{user.username}</span>
                <Badge variant="secondary">{user.role}</Badge>
              </div>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Cerrar sesión
            </Button>
          </div>
        </header>

        {user?.must_change_password && (
          <div
            role="alert"
            className="border-b border-amber-500/30 bg-amber-500/10 px-6 py-2 text-sm text-amber-800 dark:text-amber-400"
          >
            Tu contraseña es temporal y debes cambiarla.
            {user.role === "admin" && (
              <>
                {" "}
                Restablécela desde la sección{" "}
                <Link to="/users" className="underline">
                  Usuarios
                </Link>
                .
              </>
            )}
          </div>
        )}

        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function NavSection({
  label,
  items,
}: {
  label: string;
  items: ReadonlyArray<{ to: string; label: string; icon: typeof FolderKanban }>;
}) {
  return (
    <div className="space-y-1">
      <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )
          }
        >
          <item.icon className="h-4 w-4" />
          {item.label}
        </NavLink>
      ))}
    </div>
  );
}
