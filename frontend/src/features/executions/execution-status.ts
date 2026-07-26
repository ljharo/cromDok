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
 * Subtle tinted styles with explicit dark: variants so they read well
 * in both themes.
 */
export const EXECUTION_STATUS_BADGE_CLASS: Record<ExecutionStatus, string> = {
  queued:
    "border-slate-500/30 bg-slate-500/10 text-slate-600 hover:bg-slate-500/20 dark:text-slate-400",
  running:
    "border-blue-500/30 bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 dark:text-blue-400",
  succeeded:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/20 dark:text-emerald-400",
  failed: "border-red-500/30 bg-red-500/10 text-red-600 hover:bg-red-500/20 dark:text-red-400",
  killed:
    "border-orange-500/30 bg-orange-500/10 text-orange-600 hover:bg-orange-500/20 dark:text-orange-400",
  skipped:
    "border-yellow-500/30 bg-yellow-500/10 text-yellow-600 hover:bg-yellow-500/20 dark:text-yellow-400",
};

/** Live statuses: polling runs while any execution is queued/running. */
export function isLiveStatus(status: ExecutionStatus): boolean {
  return status === "queued" || status === "running";
}
