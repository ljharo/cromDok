import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AxiosError } from "axios";
import { z } from "zod";
import { MoreHorizontal, Plus, RotateCcw, Trash2, Variable } from "lucide-react";

import { useCanWrite } from "@/hooks/useCanWrite";
import {
  useCreateEnvVar,
  useDeleteEnvVar,
  useEnvVars,
  useRotateEnvVar,
} from "@/features/env-vars/hooks";
import { useRunners } from "@/features/runners/hooks";
import {
  envVarCreateSchema,
  envVarRotateSchema,
  type EnvVarRotate,
  type EnvVarSummary,
} from "@/types/env-var";
import { EmptyState } from "@/components/EmptyState";
import { TableSkeleton } from "@/components/TableSkeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// The API never returns values (spec 9.1): the UI always renders the mask.
export const MASKED_VALUE = "••••••••";

const PROJECT_SCOPE = "project";

const createFormSchema = envVarCreateSchema
  .pick({ key: true, value: true })
  .extend({ scope: z.string() });
type CreateFormValues = z.infer<typeof createFormSchema>;

/** Env vars of one project: masked values, create/rotate/delete (spec 9.1). */
export default function EnvVarsTable({ projectId }: { projectId: number }) {
  const { data: envVars, isPending, isError } = useEnvVars(projectId);
  const { data: runners } = useRunners(projectId);
  const canWrite = useCanWrite();
  const [createOpen, setCreateOpen] = useState(false);

  const runnerName = (runnerId: number | null) =>
    runners?.find((runner) => runner.id === runnerId)?.name ?? `#${runnerId}`;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Variables de entorno</h2>
        {canWrite && (
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva variable
          </Button>
        )}
      </div>

      {isPending && <TableSkeleton />}
      {isError && <p className="text-destructive">No se pudieron cargar las variables.</p>}
      {envVars && envVars.length === 0 && (
        <EmptyState icon={Variable} title="Este proyecto no tiene variables de entorno todavía." />
      )}
      {envVars && envVars.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Clave</TableHead>
              <TableHead>Ámbito</TableHead>
              <TableHead>Valor</TableHead>
              {canWrite && <TableHead className="w-16" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {envVars.map((envVar) => (
              <TableRow key={envVar.id}>
                <TableCell className="font-mono font-medium">{envVar.key}</TableCell>
                <TableCell>
                  {envVar.runner_id === null ? (
                    <Badge variant="secondary">Proyecto</Badge>
                  ) : (
                    <Badge variant="outline">{runnerName(envVar.runner_id)}</Badge>
                  )}
                </TableCell>
                <TableCell aria-label={`Valor de ${envVar.key}`}>{MASKED_VALUE}</TableCell>
                {canWrite && (
                  <TableCell>
                    <EnvVarRowActions envVar={envVar} />
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {canWrite && (
        <CreateEnvVarDialog projectId={projectId} open={createOpen} onOpenChange={setCreateOpen} />
      )}
    </div>
  );
}

function CreateEnvVarDialog({
  projectId,
  open,
  onOpenChange,
}: {
  projectId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: runners } = useRunners(projectId);
  const createEnvVar = useCreateEnvVar(projectId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createFormSchema),
    defaultValues: { key: "", value: "", scope: PROJECT_SCOPE },
  });

  const onSubmit = (values: CreateFormValues) => {
    setServerError(null);
    createEnvVar.mutate(
      {
        project_id: projectId,
        key: values.key,
        value: values.value,
        runner_id: values.scope === PROJECT_SCOPE ? null : Number(values.scope),
      },
      {
        onSuccess: () => {
          form.reset();
          onOpenChange(false);
        },
        onError: (error) => {
          // Duplicate key → 409; invalid/blacklisted key → 422 (string detail).
          if (
            error instanceof AxiosError &&
            (error.response?.status === 409 || error.response?.status === 422)
          ) {
            const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
            form.setError("key", {
              message: typeof detail === "string" ? detail : "Clave no válida o duplicada",
            });
          } else {
            setServerError("No se pudo crear la variable. Inténtalo de nuevo más tarde.");
          }
        },
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nueva variable</DialogTitle>
          <DialogDescription>
            El valor se cifra antes de guardarse y nunca vuelve a mostrarse.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="key"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Clave</FormLabel>
                  <FormControl>
                    <Input placeholder="API_TOKEN" className="font-mono" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Valor</FormLabel>
                  <FormControl>
                    <PasswordInput autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="scope"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Ámbito</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger aria-label="Ámbito">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={PROJECT_SCOPE}>Todo el proyecto</SelectItem>
                      {runners?.map((runner) => (
                        <SelectItem key={runner.id} value={String(runner.id)}>
                          Runner: {runner.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            {serverError && (
              <p role="alert" className="text-sm font-medium text-destructive">
                {serverError}
              </p>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={createEnvVar.isPending}>
                {createEnvVar.isPending ? "Creando…" : "Crear variable"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

function EnvVarRowActions({ envVar }: { envVar: EnvVarSummary }) {
  const [rotateOpen, setRotateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteEnvVar = useDeleteEnvVar(envVar.project_id);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Acciones de ${envVar.key}`}>
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setRotateOpen(true)}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Rotar valor
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => setDeleteOpen(true)}
            className="text-destructive focus:text-destructive"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Eliminar
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <RotateEnvVarDialog envVar={envVar} open={rotateOpen} onOpenChange={setRotateOpen} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar variable</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar {envVar.key}? Los runners que la usen dejarán de
              recibirla. Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={deleteEnvVar.isPending}
              onClick={() =>
                deleteEnvVar.mutate(envVar.id, { onSuccess: () => setDeleteOpen(false) })
              }
            >
              {deleteEnvVar.isPending ? "Eliminando…" : "Eliminar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function RotateEnvVarDialog({
  envVar,
  open,
  onOpenChange,
}: {
  envVar: EnvVarSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const rotateEnvVar = useRotateEnvVar(envVar.project_id);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<EnvVarRotate>({
    resolver: zodResolver(envVarRotateSchema),
    defaultValues: { value: "" },
  });

  const onSubmit = (values: EnvVarRotate) => {
    setServerError(null);
    rotateEnvVar.mutate(
      { envVarId: envVar.id, body: values },
      {
        onSuccess: () => {
          form.reset();
          onOpenChange(false);
        },
        onError: () => setServerError("No se pudo rotar la variable."),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rotar {envVar.key}</DialogTitle>
          <DialogDescription>
            Introduce el nuevo valor. El valor actual nunca se muestra.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nuevo valor</FormLabel>
                  <FormControl>
                    <PasswordInput autoComplete="off" {...field} />
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
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={rotateEnvVar.isPending}>
                {rotateEnvVar.isPending ? "Rotando…" : "Rotar valor"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
