import { PageHeader } from "@/components/PageHeader";

import ExecutionsTable from "./ExecutionsTable";

export default function ExecutionsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Ejecuciones"
        description="Últimas ejecuciones de todos los runners, de más reciente a más antigua."
      />
      <ExecutionsTable />
    </div>
  );
}
