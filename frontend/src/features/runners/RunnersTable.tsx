import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { MoreHorizontal, Pencil, Play, Plus, Trash2 } from "lucide-react";

import { useCanWrite } from "@/hooks/useCanWrite";
import {
  useDeleteRunner,
  useRunners,
  useToggleRunner,
  useTriggerRunner,
} from "@/features/runners/hooks";
import { describeCron } from "@/lib/cron";
import type { Runner } from "@/types/runner";
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
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** Runners of one project: schedule, enable/disable toggle and actions. */
export default function RunnersTable({ projectId }: { projectId: number }) {
  const { data: runners, isPending, isError } = useRunners(projectId);
  const canWrite = useCanWrite();
  const navigate = useNavigate();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Runners</h2>
        {canWrite && (
          <Button onClick={() => navigate(`/projects/${projectId}/runners/new`)}>
            <Plus className="mr-2 h-4 w-4" />
            Nuevo runner
          </Button>
        )}
      </div>

      {isPending && <p className="text-muted-foreground">Cargando runners…</p>}
      {isError && <p className="text-destructive">No se pudieron cargar los runners.</p>}
      {runners && runners.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <p className="text-muted-foreground">
            Este proyecto no tiene runners todavía.
            {canWrite && " Crea el primero para programar una tarea."}
          </p>
        </div>
      )}
      {runners && runners.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Lenguaje</TableHead>
              <TableHead>Programación</TableHead>
              {canWrite && <TableHead>Activo</TableHead>}
              {canWrite && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {runners.map((runner) => (
              <RunnerRow key={runner.id} runner={runner} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function RunnerRow({ runner }: { runner: Runner }) {
  const canWrite = useCanWrite();
  const toggleRunner = useToggleRunner(runner.project_id);
  const triggerRunner = useTriggerRunner();

  return (
    <TableRow>
      <TableCell className="font-medium">{runner.name}</TableCell>
      <TableCell>
        <Badge variant="secondary">{runner.language}</Badge>
      </TableCell>
      <TableCell>
        <div className="flex flex-col gap-1">
          <Badge variant="outline" className="w-fit font-mono">
            {runner.cron_expression}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {describeCron(runner.cron_expression)}
          </span>
        </div>
      </TableCell>
      {canWrite && (
        <TableCell>
          <Switch
            checked={runner.is_enabled}
            onCheckedChange={(enable) => toggleRunner.mutate({ runnerId: runner.id, enable })}
            disabled={toggleRunner.isPending}
            aria-label={`Activar o desactivar ${runner.name}`}
          />
        </TableCell>
      )}
      {canWrite && (
        <TableCell>
          <div className="flex items-center gap-1">
            {/* span wrapper keeps the title tooltip on a disabled button. */}
            <span title={runner.is_enabled ? undefined : "Activa el runner para poder ejecutarlo"}>
              <Button
                variant="ghost"
                size="icon"
                disabled={!runner.is_enabled || triggerRunner.isPending}
                onClick={() => triggerRunner.mutate(runner.id)}
                aria-label={`Ejecutar ${runner.name}`}
              >
                <Play className="h-4 w-4" />
              </Button>
            </span>
            <RunnerRowActions runner={runner} />
          </div>
        </TableCell>
      )}
    </TableRow>
  );
}

function RunnerRowActions({ runner }: { runner: Runner }) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteRunner = useDeleteRunner(runner.project_id);
  const navigate = useNavigate();

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Acciones de ${runner.name}`}>
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => navigate(`/projects/${runner.project_id}/runners/${runner.id}/edit`)}
          >
            <Pencil className="mr-2 h-4 w-4" />
            Editar
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

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar runner</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar {runner.name}? Se eliminarán también sus ejecuciones.
              Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={deleteRunner.isPending}
              onClick={() =>
                deleteRunner.mutate(runner.id, { onSuccess: () => setDeleteOpen(false) })
              }
            >
              {deleteRunner.isPending ? "Eliminando…" : "Eliminar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
