import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router-dom";
import { FolderPlus, MoreHorizontal, Pencil, Trash2 } from "lucide-react";

import { useCanWrite } from "@/hooks/useCanWrite";
import {
  useCreateProject,
  useDeleteProject,
  useProjects,
  useUpdateProject,
} from "@/features/projects/hooks";
import { useRunners } from "@/features/runners/hooks";
import { projectCreateSchema, type Project, type ProjectCreate } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

/** Project dashboard: card grid with create/edit/delete (operator+). */
export default function ProjectsPage() {
  const { data: projects, isPending, isError } = useProjects();
  const canWrite = useCanWrite();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Proyectos</h1>
          <p className="text-muted-foreground">Agrupaciones de runners y sus variables.</p>
        </div>
        {canWrite && <CreateProjectDialog />}
      </div>

      {isPending && <p className="text-muted-foreground">Cargando proyectos…</p>}
      {isError && <p className="text-destructive">No se pudieron cargar los proyectos.</p>}
      {projects && projects.length === 0 && (
        <div className="rounded-lg border border-dashed p-8 text-center">
          <p className="text-muted-foreground">
            No hay proyectos todavía.{canWrite && " Crea el primero para empezar."}
          </p>
        </div>
      )}
      {projects && projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project }: { project: Project }) {
  const canWrite = useCanWrite();
  const { data: runners } = useRunners(project.id);
  const runnerCount = runners?.length;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div className="space-y-1.5">
          <CardTitle className="text-lg">
            <Link to={`/projects/${project.id}`} className="hover:underline">
              {project.name}
            </Link>
          </CardTitle>
          <CardDescription>{project.description || "Sin descripción"}</CardDescription>
        </div>
        {canWrite && <ProjectCardActions project={project} />}
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          {runnerCount === undefined
            ? "Cargando runners…"
            : runnerCount === 1
              ? "1 runner"
              : `${runnerCount} runners`}
        </p>
      </CardContent>
    </Card>
  );
}

function ProjectCardActions({ project }: { project: Project }) {
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const deleteProject = useDeleteProject();

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label={`Acciones de ${project.name}`}>
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setEditOpen(true)}>
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

      <ProjectFormDialog project={project} open={editOpen} onOpenChange={setEditOpen} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eliminar proyecto</DialogTitle>
            <DialogDescription>
              ¿Seguro que quieres eliminar {project.name}? Se eliminarán en cascada todos sus
              runners, sus ejecuciones y sus variables de entorno. Esta acción no se puede deshacer.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={deleteProject.isPending}
              onClick={() =>
                deleteProject.mutate(project.id, { onSuccess: () => setDeleteOpen(false) })
              }
            >
              {deleteProject.isPending ? "Eliminando…" : "Eliminar"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CreateProjectDialog() {
  const [open, setOpen] = useState(false);

  return (
    <ProjectFormDialog
      open={open}
      onOpenChange={setOpen}
      trigger={
        <DialogTrigger asChild>
          <Button>
            <FolderPlus className="mr-2 h-4 w-4" />
            Nuevo proyecto
          </Button>
        </DialogTrigger>
      }
    />
  );
}

/** Shared create/edit form. Without `project` it creates; with it, it edits. */
function ProjectFormDialog({
  project,
  open,
  onOpenChange,
  trigger,
}: {
  project?: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger?: ReactNode;
}) {
  const createProject = useCreateProject();
  const updateProject = useUpdateProject();
  const isEdit = project !== undefined;

  const form = useForm<ProjectCreate>({
    resolver: zodResolver(projectCreateSchema),
    defaultValues: {
      name: project?.name ?? "",
      description: project?.description ?? "",
    },
  });

  const onSubmit = (values: ProjectCreate) => {
    if (isEdit) {
      updateProject.mutate(
        { projectId: project.id, body: values },
        { onSuccess: () => onOpenChange(false) },
      );
    } else {
      createProject.mutate(values, {
        onSuccess: () => {
          onOpenChange(false);
          form.reset();
        },
      });
    }
  };

  const isPending = createProject.isPending || updateProject.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Editar proyecto" : "Nuevo proyecto"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? `Modifica los datos de ${project.name}.`
              : "Un proyecto agrupa runners, variables de entorno y ejecuciones."}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Descripción</FormLabel>
                  <FormControl>
                    <Input autoComplete="off" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Guardando…" : isEdit ? "Guardar" : "Crear proyecto"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
