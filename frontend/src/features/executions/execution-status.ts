import type { ExecutionStatus } from "@/types/execution";

// Kept apart from components so those files only export components
// (react-refresh/only-export-components).

/** Spanish label shown in the status badge. */
export const EXECUTION_STATUS_LABEL: Record<ExecutionStatus, string> = {
  queued: "En cola",
  running: "En ejecución",
  succeeded: "Éxito",
  failed: "Fallida",
  killed: "Detenida",
  skipped: "Omitida",
};

/**
 * Badge colors per status (spec 9.4): queued grey, running blue,
 * succeeded green, failed red, killed orange, skipped yellow.
 */
export const EXECUTION_STATUS_BADGE_CLASS: Record<ExecutionStatus, string> = {
  queued: "border-transparent bg-slate-500 text-white hover:bg-slate-500/80",
  running: "border-transparent bg-blue-600 text-white hover:bg-blue-600/80",
  succeeded: "border-transparent bg-green-600 text-white hover:bg-green-600/80",
  failed: "border-transparent bg-red-600 text-white hover:bg-red-600/80",
  killed: "border-transparent bg-orange-500 text-white hover:bg-orange-500/80",
  skipped: "border-transparent bg-yellow-500 text-white hover:bg-yellow-500/80",
};

/** Live statuses: polling runs while any execution is queued/running. */
export function isLiveStatus(status: ExecutionStatus): boolean {
  return status === "queued" || status === "running";
}
