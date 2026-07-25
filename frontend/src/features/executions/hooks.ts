import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { executionsApi, projectsApi, runnersApi } from "@/api/endpoints";
import type { Execution } from "@/types/execution";

import { isLiveStatus } from "./execution-status";

export const EXECUTIONS_QUERY_KEY = ["executions"] as const;
export const EXECUTIONS_POLL_INTERVAL_MS = 3000;
export const LOG_POLL_INTERVAL_MS = 3000;

// The backend paginates per-runner executions oldest first (default limit 50);
// the views show the most recent page, client-sorted by id (sequential, so id
// desc = most recent).
const RUNNER_EXECUTIONS_PAGE_SIZE = 50;

export interface ExecutionsView {
  executions: Execution[];
  /** Runner id → name, for the "Runner" column. */
  runnerNames: Record<number, string>;
}

export function executionsViewQueryKey(runnerId?: number, projectId?: number) {
  return [...EXECUTIONS_QUERY_KEY, runnerId ?? "all", projectId ?? "all"] as const;
}

function sortByRecency(executions: Execution[]): Execution[] {
  return [...executions].sort((a, b) => b.id - a.id);
}

/**
 * Executions for the table. The backend has no global executions endpoint
 * (only GET /runners/{id}/executions), so the global view aggregates here:
 * projects → runners of each project → last page of executions per runner.
 */
export function useExecutionsView(runnerId?: number, projectId?: number) {
  return useQuery({
    queryKey: executionsViewQueryKey(runnerId, projectId),
    queryFn: async (): Promise<ExecutionsView> => {
      if (runnerId !== undefined) {
        const [runner, executions] = await Promise.all([
          runnersApi.get(runnerId),
          executionsApi.list(runnerId, { limit: RUNNER_EXECUTIONS_PAGE_SIZE }),
        ]);
        return {
          executions: sortByRecency(executions),
          runnerNames: { [runner.id]: runner.name },
        };
      }
      const runners =
        projectId !== undefined
          ? await runnersApi.list(projectId)
          : (
              await Promise.all((await projectsApi.list()).map((p) => runnersApi.list(p.id)))
            ).flat();
      const executionsPerRunner = await Promise.all(
        runners.map((r) => executionsApi.list(r.id, { limit: RUNNER_EXECUTIONS_PAGE_SIZE })),
      );
      return {
        executions: sortByRecency(executionsPerRunner.flat()),
        runnerNames: Object.fromEntries(runners.map((r) => [r.id, r.name])),
      };
    },
    // Poll only while something is queued/running; stop when every execution
    // has reached a terminal state.
    refetchInterval: (query) =>
      query.state.data?.executions.some((e) => isLiveStatus(e.status))
        ? EXECUTIONS_POLL_INTERVAL_MS
        : false,
  });
}

/** One execution's metadata, polling while it is queued/running. */
export function useExecution(executionId: number) {
  return useQuery({
    queryKey: [...EXECUTIONS_QUERY_KEY, "detail", executionId] as const,
    queryFn: () => executionsApi.get(executionId),
    refetchInterval: (query) =>
      query.state.data && isLiveStatus(query.state.data.status)
        ? EXECUTIONS_POLL_INTERVAL_MS
        : false,
  });
}

/**
 * Incremental log reader (spec 6.4): keeps the offset between polls and
 * appends each new chunk — never a full refetch. While `live` is true it
 * polls; when `live` flips to false the effect re-runs once for a final
 * fetch and then stops.
 */
export function useExecutionLogs(executionId: number, live: boolean) {
  const [text, setText] = useState("");
  const [isError, setIsError] = useState(false);
  const offsetRef = useRef(0);

  // Reset when switching to another execution.
  useEffect(() => {
    offsetRef.current = 0;
    setText("");
    setIsError(false);
  }, [executionId]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const { chunk, offset } = await executionsApi.logs(executionId, offsetRef.current);
        if (cancelled) return;
        if (chunk) setText((prev) => prev + chunk);
        offsetRef.current = offset;
      } catch {
        if (!cancelled) setIsError(true);
      }
    };

    void poll();
    if (!live) return;
    const intervalId = setInterval(() => void poll(), LOG_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [executionId, live]);

  return { text, isError };
}
