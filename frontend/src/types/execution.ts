import { z } from "zod";

// Mirrors cron_dok.domain.entities.execution literals
export const executionStatusSchema = z.enum([
  "queued",
  "running",
  "succeeded",
  "failed",
  "skipped",
  "killed",
]);
export type ExecutionStatus = z.infer<typeof executionStatusSchema>;

export const triggerTypeSchema = z.enum(["scheduled", "manual"]);
export type TriggerType = z.infer<typeof triggerTypeSchema>;

// Mirrors ExecutionResponse (logs are served separately, spec 6.4)
export const executionSchema = z.object({
  id: z.number().int(),
  runner_id: z.number().int(),
  status: executionStatusSchema,
  trigger_type: triggerTypeSchema,
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  exit_code: z.number().int().nullable(),
  duration_ms: z.number().int().nullable(),
  log_path: z.string().nullable(),
});
export type Execution = z.infer<typeof executionSchema>;

// Mirrors LogChunkResponse (incremental log read)
export const logChunkSchema = z.object({
  chunk: z.string(),
  offset: z.number().int(),
});
export type LogChunk = z.infer<typeof logChunkSchema>;
