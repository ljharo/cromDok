import { createBrowserRouter } from "react-router-dom";
import DashboardPlaceholder from "@/components/DashboardPlaceholder";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <DashboardPlaceholder />,
  },
]);
