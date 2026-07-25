import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Execution, TriggerType } from "@/types/execution";

import { EXECUTION_STATUS_BADGE_CLASS, EXECUTION_STATUS_LABEL } from "./execution-status";
import { formatDuration, formatStartedAt } from "./format";
import { useExecutionsView } from "./hooks";

const TRIGGER_LABEL: Record<TriggerType, string> = {
  scheduled: "Programado",
  manual: "Manual",
};

/**
 * Executions table. With `runnerId` it shows only that runner's executions,
 * with `projectId` only that project's (e.g. the project detail "Ejecuciones"
 * tab); without props, the global view aggregating every runner. Clicking a
 * row opens the log viewer.
 */
export default function ExecutionsTable({
  runnerId,
  projectId,
}: {
  runnerId?: number;
  projectId?: number;
}) {
  const { data, isPending, isError } = useExecutionsView(runnerId, projectId);
  const navigate = useNavigate();

  if (isPending) {
    return <p className="text-muted-foreground">Cargando ejecuciones…</p>;
  }
  if (isError) {
    return <p className="text-destructive">No se pudieron cargar las ejecuciones.</p>;
  }
  if (data.executions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-8 text-center">
        <p className="text-muted-foreground">No hay ejecuciones todavía.</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Runner</TableHead>
          <TableHead>Trigger</TableHead>
          <TableHead>Estado</TableHead>
          <TableHead>Inicio</TableHead>
          <TableHead>Duración</TableHead>
          <TableHead>Exit code</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.executions.map((execution) => (
          <ExecutionRow
            key={execution.id}
            execution={execution}
            runnerName={data.runnerNames[execution.runner_id] ?? `#${execution.runner_id}`}
            onOpen={() => navigate(`/executions/${execution.id}`)}
          />
        ))}
      </TableBody>
    </Table>
  );
}

function ExecutionRow({
  execution,
  runnerName,
  onOpen,
}: {
  execution: Execution;
  runnerName: string;
  onOpen: () => void;
}) {
  return (
    <TableRow
      className="cursor-pointer"
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter") onOpen();
      }}
      tabIndex={0}
      aria-label={`Ejecución ${execution.id} de ${runnerName}`}
    >
      <TableCell className="font-medium">{runnerName}</TableCell>
      <TableCell>{TRIGGER_LABEL[execution.trigger_type]}</TableCell>
      <TableCell>
        <Badge className={EXECUTION_STATUS_BADGE_CLASS[execution.status]}>
          {EXECUTION_STATUS_LABEL[execution.status]}
        </Badge>
      </TableCell>
      <TableCell>{formatStartedAt(execution.started_at)}</TableCell>
      <TableCell>{formatDuration(execution.duration_ms)}</TableCell>
      <TableCell>{execution.exit_code ?? "—"}</TableCell>
    </TableRow>
  );
}
