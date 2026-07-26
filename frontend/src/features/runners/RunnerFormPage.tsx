import { useState } from "react";
import { useForm, type UseFormSetError } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AxiosError } from "axios";
import { z } from "zod";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, TriangleAlert } from "lucide-react";

import { useCreateRunner, useRunner, useUpdateRunner } from "@/features/runners/hooks";
import ScheduleBuilder from "@/features/runners/components/ScheduleBuilder";
import ScriptEditor from "@/features/runners/components/ScriptEditor";
import { describeCron, isValidCron } from "@/lib/cron";
import {
  overlapPolicySchema,
  runnerLanguageSchema,
  type Runner,
  type RunnerCreate,
} from "@/types/runner";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

// Form-level schema: mirrors RunnerCreate plus a client-side cron check
// (the backend stays the ultimate validator; its 422 is mapped back here).
const runnerFormSchema = z.object({
  name: z.string().min(1, "El nombre es obligatorio").max(100, "Máximo 100 caracteres"),
  language: runnerLanguageSchema,
  cron_expression: z
    .string()
    .min(1, "La expresión cron es obligatoria")
    .max(100, "Máximo 100 caracteres")
    .refine(isValidCron, "Expresión cron no válida"),
  script_content: z.string().min(1, "El script es obligatorio"),
  timeout_seconds: z.coerce.number().int("Debe ser un número entero").gt(0, "Debe ser mayor que 0"),
  memory_mb: z.coerce.number().int("Debe ser un número entero").gt(0, "Debe ser mayor que 0"),
  cpu_quota: z.coerce.number().gt(0, "Debe ser mayor que 0"),
  pids_limit: z.coerce.number().int("Debe ser un número entero").gt(0, "Debe ser mayor que 0"),
  network_enabled: z.boolean(),
  on_overlap: overlapPolicySchema,
  dependencies: z.string().max(10_000, "Máximo 10 000 caracteres"),
});

type RunnerFormInput = z.input<typeof runnerFormSchema>;
type RunnerFormValues = z.output<typeof runnerFormSchema>;

const EDITABLE_FIELDS = [
  "name",
  "language",
  "cron_expression",
  "script_content",
  "timeout_seconds",
  "memory_mb",
  "cpu_quota",
  "pids_limit",
  "network_enabled",
  "on_overlap",
  "dependencies",
] as const;

/**
 * Map a backend 422 onto form fields. Two shapes exist (see main.py):
 * FastAPI validation → detail is a list of {loc, msg}; domain errors
 * (invalid cron, bad limits) → detail is a plain string.
 * Returns the fallback message to show when nothing could be mapped.
 */
function mapServerErrors(
  error: unknown,
  setError: UseFormSetError<RunnerFormInput>,
): string | null {
  if (!(error instanceof AxiosError) || error.response?.status !== 422) {
    return "No se pudo guardar el runner. Inténtalo de nuevo más tarde.";
  }
  const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") {
    if (detail.toLowerCase().includes("cron")) {
      setError("cron_expression", { message: detail });
      return null;
    }
    return detail;
  }
  if (Array.isArray(detail)) {
    let mapped = false;
    for (const item of detail as { loc?: unknown[]; msg?: unknown }[]) {
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      const field = String(loc[loc.length - 1] ?? "");
      if ((EDITABLE_FIELDS as readonly string[]).includes(field)) {
        setError(field as (typeof EDITABLE_FIELDS)[number], {
          message: String(item?.msg ?? "Valor no válido"),
        });
        mapped = true;
      }
    }
    return mapped ? null : "El backend rechazó los datos del formulario.";
  }
  return "El backend rechazó los datos del formulario.";
}

const DEFAULT_VALUES: RunnerFormInput = {
  name: "",
  language: "python",
  cron_expression: "0 3 * * *",
  script_content: "",
  timeout_seconds: 300,
  memory_mb: 256,
  cpu_quota: 1.0,
  pids_limit: 100,
  network_enabled: false,
  on_overlap: "skip",
  dependencies: "",
};

function formValuesFrom(runner: Runner): RunnerFormInput {
  return {
    name: runner.name,
    language: runner.language,
    cron_expression: runner.cron_expression,
    script_content: runner.script_content,
    timeout_seconds: runner.timeout_seconds,
    memory_mb: runner.resource_limits.memory_mb,
    cpu_quota: runner.resource_limits.cpu_quota,
    pids_limit: runner.resource_limits.pids_limit,
    network_enabled: runner.resource_limits.network_enabled,
    on_overlap: runner.on_overlap,
    dependencies: runner.dependencies ?? "",
  };
}

export default function RunnerFormPage() {
  const params = useParams<{ projectId: string; runnerId: string }>();
  const projectId = Number(params.projectId);
  const runnerId = params.runnerId !== undefined ? Number(params.runnerId) : null;
  const isEdit = runnerId !== null;
  const navigate = useNavigate();

  const runnerQuery = useRunner(runnerId ?? 0, isEdit);
  const createRunner = useCreateRunner(projectId);
  const updateRunner = useUpdateRunner(projectId);
  const [serverError, setServerError] = useState<string | null>(null);

  const form = useForm<RunnerFormInput, unknown, RunnerFormValues>({
    resolver: zodResolver(runnerFormSchema),
    defaultValues: DEFAULT_VALUES,
    // `values` re-syncs the form once the runner being edited arrives.
    values: isEdit && runnerQuery.data ? formValuesFrom(runnerQuery.data) : DEFAULT_VALUES,
  });

  const cronValue = form.watch("cron_expression");
  const languageValue = form.watch("language");
  const networkEnabled = form.watch("network_enabled");
  const isPending = createRunner.isPending || updateRunner.isPending;

  if (isEdit && runnerQuery.isPending) {
    return <p className="text-muted-foreground">Cargando runner…</p>;
  }
  if (isEdit && (runnerQuery.isError || !runnerQuery.data)) {
    return (
      <div className="space-y-2">
        <p className="text-destructive">No se pudo cargar el runner.</p>
        <Link to={`/projects/${projectId}`} className="text-sm underline">
          Volver al proyecto
        </Link>
      </div>
    );
  }

  const onSubmit = (values: RunnerFormValues) => {
    setServerError(null);
    const resource_limits = {
      memory_mb: values.memory_mb,
      cpu_quota: values.cpu_quota,
      pids_limit: values.pids_limit,
      network_enabled: values.network_enabled,
    };
    const fields = {
      name: values.name,
      language: values.language,
      cron_expression: values.cron_expression,
      script_content: values.script_content,
      timeout_seconds: values.timeout_seconds,
      on_overlap: values.on_overlap,
      resource_limits,
      dependencies: values.dependencies.trim() === "" ? null : values.dependencies,
    };
    const options = {
      onSuccess: () => navigate(`/projects/${projectId}`),
      onError: (error: unknown) => setServerError(mapServerErrors(error, form.setError)),
    };
    if (isEdit) {
      updateRunner.mutate({ runnerId, body: fields }, options);
    } else {
      const body: RunnerCreate = { project_id: projectId, ...fields };
      createRunner.mutate(body, options);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <div className="space-y-1">
        <Link
          to={`/projects/${projectId}`}
          className="inline-flex items-center text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Volver al proyecto
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">
          {isEdit ? "Editar runner" : "Nuevo runner"}
        </h1>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre</FormLabel>
                  <FormControl>
                    <Input placeholder="Backup diario" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="language"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Lenguaje</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger aria-label="Lenguaje">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="python">Python</SelectItem>
                      <SelectItem value="bash">Bash</SelectItem>
                      <SelectItem value="node">Node.js</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <FormField
            control={form.control}
            name="cron_expression"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Programación</FormLabel>
                <FormControl>
                  <ScheduleBuilder value={field.value} onChange={field.onChange} />
                </FormControl>
                {cronValue && isValidCron(cronValue) && (
                  <FormDescription>{describeCron(cronValue)}</FormDescription>
                )}
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="script_content"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Script</FormLabel>
                <FormControl>
                  <ScriptEditor
                    value={field.value}
                    language={languageValue}
                    onChange={field.onChange}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {languageValue !== "bash" && (
            <FormField
              control={form.control}
              name="dependencies"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Dependencias</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={4}
                      className="font-mono text-sm"
                      placeholder={
                        languageValue === "python"
                          ? "requests==2.31.0\npsycopg2-binary"
                          : "pg@8.11.0\nlodash"
                      }
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    Una por línea (
                    {languageValue === "python"
                      ? "formato requirements.txt"
                      : "nombre o nombre@versión"}
                    ). Se instalan una vez y se reusan mientras no cambien — necesitas "Acceso a
                    red" activado para instalarlas.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              control={form.control}
              name="timeout_seconds"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Timeout (segundos)</FormLabel>
                  <FormControl>
                    <Input type="number" min={1} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="on_overlap"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Si hay solapamiento</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger aria-label="Si hay solapamiento">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="skip">Saltar (skip)</SelectItem>
                      <SelectItem value="queue">Encolar (queue)</SelectItem>
                      <SelectItem value="kill_previous">
                        Matar la anterior (kill_previous)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          <fieldset className="space-y-4 rounded-lg border p-4">
            <legend className="px-1 text-sm font-medium">Límites de recursos</legend>
            <div className="grid gap-4 sm:grid-cols-3">
              <FormField
                control={form.control}
                name="memory_mb"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Memoria (MB)</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="cpu_quota"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>CPUs</FormLabel>
                    <FormControl>
                      <Input type="number" min={0.1} step={0.1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="pids_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Límite de PIDs</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="network_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between gap-4 space-y-0">
                  <div className="space-y-1">
                    <FormLabel>Acceso a red</FormLabel>
                    <FormDescription>
                      El contenedor podrá acceder a la red durante la ejecución.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      aria-label="Acceso a red"
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            {networkEnabled && (
              <p className="flex items-start gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                Aviso de seguridad: con la red activada, el script puede descargar código externo o
                exfiltrar datos durante la ejecución. Actívala solo si la tarea lo necesita.
              </p>
            )}
          </fieldset>

          {serverError && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {serverError}
            </p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={isPending}>
              {isPending ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear runner"}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate(`/projects/${projectId}`)}
            >
              Cancelar
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
