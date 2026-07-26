import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { useProject } from "@/features/projects/hooks";
import RunnersTable from "@/features/runners/RunnersTable";
import EnvVarsTable from "@/features/env-vars/EnvVarsTable";
import ExecutionsTable from "@/features/executions/ExecutionsTable";
import { PageHeader } from "@/components/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/** Project detail: runners, env vars and executions in tabs. */
export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Number(params.projectId);
  const { data: project, isPending, isError } = useProject(projectId);

  if (isPending) {
    return (
      <div className="space-y-3" role="status" aria-label="Cargando">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="space-y-2">
        <p className="text-destructive">No se pudo cargar el proyecto.</p>
        <Link to="/projects" className="text-sm underline">
          Volver a proyectos
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <Link
          to="/projects"
          className="inline-flex items-center text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Proyectos
        </Link>
        <PageHeader title={project.name} description={project.description || undefined} />
      </div>

      <Tabs defaultValue="runners">
        <TabsList>
          <TabsTrigger value="runners">Runners</TabsTrigger>
          <TabsTrigger value="variables">Variables</TabsTrigger>
          <TabsTrigger value="executions">Ejecuciones</TabsTrigger>
        </TabsList>
        <TabsContent value="runners">
          <RunnersTable projectId={project.id} />
        </TabsContent>
        <TabsContent value="variables">
          <EnvVarsTable projectId={project.id} />
        </TabsContent>
        <TabsContent value="executions">
          <ExecutionsTable projectId={project.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
