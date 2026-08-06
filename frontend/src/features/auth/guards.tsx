import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import type { UserRole } from "@/types/user";

function FullScreenLoading() {
  return (
    <div
      className="flex min-h-screen items-center justify-center"
      role="status"
      aria-label="Cargando"
    >
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

/**
 * Route guard: renders children only with a valid session, otherwise
 * redirects to /login remembering the original destination. A user with a
 * pending password change is confined to /change-password (the server also
 * answers 403 to everything else).
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const location = useLocation();
  const { data: user, isPending, isError } = useCurrentUser();

  if (isPending) {
    return <FullScreenLoading />;
  }

  if (isError || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
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
    return <FullScreenLoading />;
  }

  if (!user || user.role !== role) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
