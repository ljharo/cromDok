import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { useProject } from "@/features/projects/hooks";
import RunnersTable from "@/features/runners/RunnersTable";
import EnvVarsTable from "@/features/env-vars/EnvVarsTable";
import ExecutionsTable from "@/features/executions/ExecutionsTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

/** Project detail: runners, env vars and executions in tabs. */
export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = Number(params.projectId);
  const { data: project, isPending, isError } = useProject(projectId);

  if (isPending) {
    return <p className="text-muted-foreground">Cargando proyecto…</p>;
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
        <h1 className="text-2xl font-bold tracking-tight">{project.name}</h1>
        {project.description && <p className="text-muted-foreground">{project.description}</p>}
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
