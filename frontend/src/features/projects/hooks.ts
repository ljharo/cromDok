import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { projectsApi } from "@/api/endpoints";
import type { ProjectCreate, ProjectUpdate } from "@/types/project";

export const PROJECTS_QUERY_KEY = ["projects"] as const;

export function useProjects() {
  return useQuery({
    queryKey: PROJECTS_QUERY_KEY,
    queryFn: projectsApi.list,
  });
}

export function useProject(projectId: number) {
  return useQuery({
    queryKey: [...PROJECTS_QUERY_KEY, projectId] as const,
    queryFn: () => projectsApi.get(projectId),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ProjectCreate) => projectsApi.create(body),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      toast.success(`Proyecto ${project.name} creado`);
    },
    onError: () => {
      toast.error("No se pudo crear el proyecto");
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, body }: { projectId: number; body: ProjectUpdate }) =>
      projectsApi.update(projectId, body),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      toast.success(`Proyecto ${project.name} actualizado`);
    },
    onError: () => {
      toast.error("No se pudo actualizar el proyecto");
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: number) => projectsApi.remove(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      toast.success("Proyecto eliminado");
    },
    onError: () => {
      toast.error("No se pudo eliminar el proyecto");
    },
  });
}
