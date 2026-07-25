import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import type { UserRole } from "@/types/user";

/**
 * Route guard: renders children only with a valid session, otherwise
 * redirects to /login remembering the original destination.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { data: user, isPending, isError } = useCurrentUser();

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando…</p>
      </div>
    );
  }

  if (isError || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}

/**
 * Role guard: on top of RequireAuth, only lets the given role through.
 * Anyone else is sent back to the home page.
 */
export function RequireRole({ role, children }: { role: UserRole; children: ReactNode }) {
  const { data: user, isPending } = useCurrentUser();

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando…</p>
      </div>
    );
  }

  if (!user || user.role !== role) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
