import { createBrowserRouter, Navigate } from "react-router-dom";

import Layout from "@/components/Layout";
import LoginPage from "@/features/auth/LoginPage";
import { RequireAuth, RequireRole } from "@/features/auth/guards";
import ProjectsPage from "@/features/projects/ProjectsPage";
import ProjectDetailPage from "@/features/projects/ProjectDetailPage";
import RunnerFormPage from "@/features/runners/RunnerFormPage";
import ExecutionsPage from "@/features/executions/ExecutionsPage";
import ExecutionDetailPage from "@/features/executions/ExecutionDetailPage";
import UsersPage from "@/features/users/UsersPage";
import ApiKeysPage from "@/features/api-keys/ApiKeysPage";

export const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/",
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/projects" replace /> },
      { path: "projects", element: <ProjectsPage /> },
      { path: "projects/:projectId", element: <ProjectDetailPage /> },
      { path: "projects/:projectId/runners/new", element: <RunnerFormPage /> },
      { path: "projects/:projectId/runners/:runnerId/edit", element: <RunnerFormPage /> },
      { path: "executions", element: <ExecutionsPage /> },
      { path: "executions/:executionId", element: <ExecutionDetailPage /> },
      {
        path: "users",
        element: (
          <RequireRole role="admin">
            <UsersPage />
          </RequireRole>
        ),
      },
      {
        path: "api-keys",
        element: (
          <RequireRole role="admin">
            <ApiKeysPage />
          </RequireRole>
        ),
      },
    ],
  },
]);
