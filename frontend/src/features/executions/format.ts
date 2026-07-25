/** Formatting helpers for the executions views (dates, durations). */

const dateTimeFormatter = new Intl.DateTimeFormat("es-ES", {
  dateStyle: "short",
  timeStyle: "medium",
});

/** Localized date-time or an em dash while the execution has not started. */
export function formatStartedAt(iso: string | null): string {
  return iso ? dateTimeFormatter.format(new Date(iso)) : "—";
}

/** Human duration from milliseconds ("350 ms", "2,5 s", "3 min 4 s"). */
export function formatDuration(durationMs: number | null): string {
  if (durationMs === null) return "—";
  if (durationMs < 1000) return `${durationMs} ms`;
  const seconds = durationMs / 1000;
  if (seconds < 60) {
    return `${seconds.toLocaleString("es-ES", { maximumFractionDigits: 1 })} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} min ${rest} s`;
}
