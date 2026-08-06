import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AxiosError } from "axios";
import { Navigate } from "react-router-dom";

import { useChangePassword } from "@/features/auth/hooks";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { passwordChangeSchema, type PasswordChange } from "@/types/auth";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { PasswordInput } from "@/components/ui/password-input";

/**
 * Self-service password change. The server confines users with
 * `must_change_password` to this flow (every other endpoint answers 403),
 * and the RequireAuth guard redirects them here. On success every session
 * is revoked and the user must log in again with the new password.
 */
export default function ChangePasswordPage() {
  const { data: user } = useCurrentUser();
  const changePassword = useChangePassword();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<PasswordChange>({
    resolver: zodResolver(passwordChangeSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  // Nothing forcing a change and no session pending: back to the app.
  if (user && !user.must_change_password) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = (values: PasswordChange) => {
    setServerError(null);
    changePassword.mutate(
      { current_password: values.current_password, new_password: values.new_password },
      {
        onError: (error) => {
          if (error instanceof AxiosError && error.response?.status === 400) {
            setServerError("La contraseña actual no es correcta.");
          } else if (error instanceof AxiosError && error.response?.status === 422) {
            setServerError("La nueva contraseña es demasiado débil (mínimo 12 caracteres).");
          } else {
            setServerError("No se pudo cambiar la contraseña. Inténtalo de nuevo más tarde.");
          }
        },
      },
    );
  };

  return (
    <main className="bg-login-gradient flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <Logo />
          <p className="text-sm text-muted-foreground">
            Scheduler self-hosted para tus tareas programadas
          </p>
        </div>
        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle className="text-xl">Cambiar contraseña</CardTitle>
            <CardDescription>
              {user?.must_change_password
                ? "Tu contraseña es temporal; debes cambiarla para continuar"
                : "Introduce tu contraseña actual y la nueva"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="current_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Contraseña actual</FormLabel>
                      <FormControl>
                        <PasswordInput autoComplete="current-password" autoFocus {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nueva contraseña</FormLabel>
                      <FormControl>
                        <PasswordInput autoComplete="new-password" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="confirm_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Repite la nueva contraseña</FormLabel>
                      <FormControl>
                        <PasswordInput autoComplete="new-password" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {serverError && (
                  <p role="alert" className="text-sm font-medium text-destructive">
                    {serverError}
                  </p>
                )}
                <Button type="submit" className="w-full" disabled={changePassword.isPending}>
                  {changePassword.isPending ? "Cambiando…" : "Cambiar contraseña"}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
