import ExecutionsTable from "./ExecutionsTable";

export default function ExecutionsPage() {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Ejecuciones</h1>
        <p className="text-muted-foreground">
          Últimas ejecuciones de todos los runners, de más reciente a más antigua.
        </p>
      </div>
      <ExecutionsTable />
    </div>
  );
}
