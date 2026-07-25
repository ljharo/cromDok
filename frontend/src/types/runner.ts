import { z } from "zod";

// Mirrors cron_dok.domain.entities.runner literals
export const runnerLanguageSchema = z.enum(["python", "bash", "node"]);
export type RunnerLanguage = z.infer<typeof runnerLanguageSchema>;

export const overlapPolicySchema = z.enum(["skip", "queue", "kill_previous"]);
export type OverlapPolicy = z.infer<typeof overlapPolicySchema>;

// Mirrors ResourceLimitsSchema (spec 9.2 defaults)
export const resourceLimitsSchema = z.object({
  memory_mb: z.number().gt(0).default(256),
  cpu_quota: z.number().gt(0).default(1.0),
  pids_limit: z.number().gt(0).default(100),
  network_enabled: z.boolean().default(false),
});
export type ResourceLimits = z.infer<typeof resourceLimitsSchema>;

// Mirrors RunnerResponse
export const runnerSchema = z.object({
  id: z.number().int(),
  project_id: z.number().int(),
  name: z.string(),
  script_content: z.string(),
  language: runnerLanguageSchema,
  cron_expression: z.string(),
  resource_limits: resourceLimitsSchema,
  is_enabled: z.boolean(),
  timeout_seconds: z.number().int(),
  on_overlap: overlapPolicySchema,
});
export type Runner = z.infer<typeof runnerSchema>;

// Mirrors RunnerCreate
export const runnerCreateSchema = z.object({
  project_id: z.number().int(),
  name: z.string().min(1, "El nombre es obligatorio").max(100, "Máximo 100 caracteres"),
  script_content: z.string(),
  language: runnerLanguageSchema,
  cron_expression: z
    .string()
    .min(1, "La expresión cron es obligatoria")
    .max(100, "Máximo 100 caracteres"),
  resource_limits: resourceLimitsSchema.nullable().default(null),
  timeout_seconds: z.number().int().gt(0).default(300),
  on_overlap: overlapPolicySchema.default("skip"),
});
export type RunnerCreate = z.infer<typeof runnerCreateSchema>;

// Mirrors RunnerUpdate (null/undefined fields are left unchanged)
export const runnerUpdateSchema = runnerCreateSchema.partial().omit({ project_id: true });
export type RunnerUpdate = z.infer<typeof runnerUpdateSchema>;
