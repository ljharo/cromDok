import { LogOut } from "lucide-react";
import { NavLink, Outlet, Link } from "react-router-dom";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useLogout } from "@/features/auth/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/projects", label: "Proyectos" },
  { to: "/executions", label: "Ejecuciones" },
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
      <aside className="flex w-56 flex-col border-r bg-muted/40">
        <div className="border-b px-6 py-4">
          <Link to="/" className="text-lg font-bold tracking-tight">
            CronDok
          </Link>
        </div>
        <nav className="flex flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
          {user?.role === "admin" && (
            <>
              <NavLink
                to="/users"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                    isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                  )
                }
              >
                Usuarios
              </NavLink>
              <NavLink
                to="/api-keys"
                className={({ isActive }) =>
                  cn(
                    "rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                    isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground",
                  )
                }
              >
                API Keys
              </NavLink>
            </>
          )}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b px-6 py-3">
          <div />
          <div className="flex items-center gap-3">
            {user && (
              <>
                <span className="text-sm font-medium">{user.username}</span>
                <Badge variant="secondary">{user.role}</Badge>
              </>
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
            className="border-b border-amber-300 bg-amber-50 px-6 py-2 text-sm text-amber-900"
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
