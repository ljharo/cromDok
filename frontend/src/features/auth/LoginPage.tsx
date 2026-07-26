import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AxiosError } from "axios";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { useLogin } from "@/features/auth/hooks";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { loginRequestSchema, type LoginRequest } from "@/types/auth";
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
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: user } = useCurrentUser();
  const login = useLogin();
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<LoginRequest>({
    resolver: zodResolver(loginRequestSchema),
    defaultValues: { username: "", password: "" },
  });

  // Already authenticated: no reason to be here.
  if (user) {
    return <Navigate to="/" replace />;
  }

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const onSubmit = (values: LoginRequest) => {
    setServerError(null);
    login.mutate(values, {
      onSuccess: () => {
        navigate(from, { replace: true });
      },
      onError: (error) => {
        if (error instanceof AxiosError && error.response?.status === 401) {
          setServerError("Usuario o contraseña incorrectos.");
        } else if (error instanceof AxiosError && error.response?.status === 429) {
          setServerError("Demasiados intentos. Espera un momento y vuelve a intentarlo.");
        } else {
          setServerError("No se pudo iniciar sesión. Inténtalo de nuevo más tarde.");
        }
      },
    });
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
            <CardTitle className="text-xl">Iniciar sesión</CardTitle>
            <CardDescription>Introduce tus credenciales para continuar</CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Usuario</FormLabel>
                      <FormControl>
                        <Input autoComplete="username" autoFocus {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Contraseña</FormLabel>
                      <FormControl>
                        <PasswordInput autoComplete="current-password" {...field} />
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
                <Button type="submit" className="w-full" disabled={login.isPending}>
                  {login.isPending ? "Entrando…" : "Entrar"}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
