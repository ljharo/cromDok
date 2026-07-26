import { Timer } from "lucide-react";

import { cn } from "@/lib/utils";

/** CronDok brand: timer mark + wordmark. */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary/15 text-primary">
        <Timer className="h-4 w-4" />
      </span>
      <span className="text-lg font-semibold tracking-tight">CronDok</span>
    </span>
  );
}
