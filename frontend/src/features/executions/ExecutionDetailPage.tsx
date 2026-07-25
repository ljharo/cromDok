import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

import {
  EXECUTION_STATUS_BADGE_CLASS,
  EXECUTION_STATUS_LABEL,
  isLiveStatus,
} from "./execution-status";
import { formatDuration, formatStartedAt } from "./format";
import { useExecution, useExecutionLogs } from "./hooks";

/** Execution detail: metadata plus the incremental live log viewer. */
export default function ExecutionDetailPage() {
  const { executionId } = useParams();
  const id = Number(executionId);
  const { data: execution, isPending, isError } = useExecution(id);
  const live = execution ? isLiveStatus(execution.status) : false;
  const logs = useExecutionLogs(id, live);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const container = logContainerRef.current;
    if (autoScroll && container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [logs.text, autoScroll]);

  if (isPending) {
    return <p className="text-muted-foreground">Cargando ejecución…</p>;
  }
  if (isError || !execution) {
    return <p className="text-destructive">No se pudo cargar la ejecución.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild aria-label="Volver a ejecuciones">
          <Link to="/executions">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">Ejecución #{execution.id}</h1>
        <Badge className={EXECUTION_STATUS_BADGE_CLASS[execution.status]}>
          {EXECUTION_STATUS_LABEL[execution.status]}
        </Badge>
        {execution.status === "running" && (
          <Badge className="border-transparent bg-blue-600 text-white">EN VIVO</Badge>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">Runner</dt>
          <dd className="font-medium">#{execution.runner_id}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Trigger</dt>
          <dd className="font-medium">
            {execution.trigger_type === "scheduled" ? "Programado" : "Manual"}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Inicio</dt>
          <dd className="font-medium">{formatStartedAt(execution.started_at)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Duración</dt>
          <dd className="font-medium">{formatDuration(execution.duration_ms)}</dd>
        </div>
      </dl>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Logs</h2>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            Auto-scroll
            <Switch
              checked={autoScroll}
              onCheckedChange={setAutoScroll}
              aria-label="Auto-scroll de logs"
            />
          </label>
        </div>
        {logs.isError && <p className="text-destructive">No se pudieron cargar los logs.</p>}
        <pre
          ref={logContainerRef}
          data-testid="log-viewer"
          className="h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-4 font-mono text-sm text-slate-50"
        >
          {logs.text || "Sin logs todavía."}
        </pre>
      </div>
    </div>
  );
}
