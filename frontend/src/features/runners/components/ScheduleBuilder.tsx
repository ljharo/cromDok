import { useState } from "react";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  WEEKDAY_LABELS,
  WEEKDAY_ORDER,
  cronToSchedule,
  scheduleToCron,
  type Schedule,
  type WeekDay,
} from "@/lib/cron";

function defaultScheduleFor(type: Schedule["type"]): Schedule {
  switch (type) {
    case "minutes":
      return { type: "minutes", interval: 5 };
    case "hours":
      return { type: "hours", interval: 1 };
    case "daily":
      return { type: "daily", hour: 3, minute: 0 };
    case "weekly":
      return { type: "weekly", days: [1], hour: 3, minute: 0 };
    case "monthly":
      return { type: "monthly", day: 1, hour: 3, minute: 0 };
  }
}

function timeToParts(time: string): { hour: number; minute: number } {
  const [h, m] = time.split(":").map(Number);
  return { hour: h || 0, minute: m || 0 };
}

function partsToTime(hour: number, minute: number): string {
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

const TYPE_LABELS: Record<Schedule["type"], string> = {
  minutes: "Cada N minutos",
  hours: "Cada N horas",
  daily: "Diario",
  weekly: "Semanal",
  monthly: "Mensual",
};

const TYPE_ORDER: Schedule["type"][] = ["minutes", "hours", "daily", "weekly", "monthly"];

interface ScheduleBuilderProps {
  value: string;
  onChange: (value: string) => void;
}

/**
 * Friendly schedule editor: presets for the common cases (every N
 * minutes/hours, daily, weekly on specific days, monthly on a specific day)
 * that generate a cron expression under the hood. "Avanzado" keeps a raw
 * cron input for anything the presets don't cover.
 */
export default function ScheduleBuilder({ value, onChange }: ScheduleBuilderProps) {
  const [mode, setMode] = useState<"simple" | "advanced">(() =>
    cronToSchedule(value) ? "simple" : "advanced",
  );
  const [schedule, setSchedule] = useState<Schedule>(
    () => cronToSchedule(value) ?? defaultScheduleFor("daily"),
  );

  const applySchedule = (next: Schedule) => {
    setSchedule(next);
    onChange(scheduleToCron(next));
  };

  const switchMode = (next: string) => {
    if (next === "simple") {
      const parsed = cronToSchedule(value);
      const resolved = parsed ?? defaultScheduleFor(schedule.type);
      setSchedule(resolved);
      if (!parsed) onChange(scheduleToCron(resolved));
    }
    setMode(next as "simple" | "advanced");
  };

  const toggleDay = (day: WeekDay) => {
    if (schedule.type !== "weekly") return;
    const has = schedule.days.includes(day);
    const nextDays = has ? schedule.days.filter((d) => d !== day) : [...schedule.days, day];
    if (nextDays.length === 0) return; // keep at least one day selected
    applySchedule({ ...schedule, days: nextDays });
  };

  return (
    <Tabs value={mode} onValueChange={switchMode}>
      <TabsList>
        <TabsTrigger value="simple">Simple</TabsTrigger>
        <TabsTrigger value="advanced">Avanzado</TabsTrigger>
      </TabsList>

      <TabsContent value="simple" className="space-y-3 pt-3">
        <Select
          value={schedule.type}
          onValueChange={(next) => applySchedule(defaultScheduleFor(next as Schedule["type"]))}
        >
          <SelectTrigger aria-label="Tipo de frecuencia" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TYPE_ORDER.map((type) => (
              <SelectItem key={type} value={type}>
                {TYPE_LABELS[type]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {schedule.type === "minutes" && (
          <label className="flex items-center gap-2 text-sm">
            Cada
            <Input
              type="number"
              min={1}
              max={59}
              className="w-20"
              aria-label="Minutos"
              value={schedule.interval}
              onChange={(event) =>
                applySchedule({
                  type: "minutes",
                  interval: Math.min(59, Math.max(1, Number(event.target.value) || 1)),
                })
              }
            />
            minutos
          </label>
        )}

        {schedule.type === "hours" && (
          <label className="flex items-center gap-2 text-sm">
            Cada
            <Input
              type="number"
              min={1}
              max={23}
              className="w-20"
              aria-label="Horas"
              value={schedule.interval}
              onChange={(event) =>
                applySchedule({
                  type: "hours",
                  interval: Math.min(23, Math.max(1, Number(event.target.value) || 1)),
                })
              }
            />
            horas
          </label>
        )}

        {schedule.type === "daily" && (
          <label className="flex items-center gap-2 text-sm">
            A las
            <Input
              type="time"
              className="w-32"
              aria-label="Hora"
              value={partsToTime(schedule.hour, schedule.minute)}
              onChange={(event) =>
                applySchedule({ type: "daily", ...timeToParts(event.target.value) })
              }
            />
          </label>
        )}

        {schedule.type === "weekly" && (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1">
              {WEEKDAY_ORDER.map((day) => (
                <button
                  key={day}
                  type="button"
                  aria-pressed={schedule.days.includes(day)}
                  onClick={() => toggleDay(day)}
                  className={cn(
                    "h-8 w-10 rounded-md border text-xs font-medium transition-colors",
                    schedule.days.includes(day)
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-input bg-background hover:bg-accent",
                  )}
                >
                  {WEEKDAY_LABELS[day]}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              A las
              <Input
                type="time"
                className="w-32"
                aria-label="Hora"
                value={partsToTime(schedule.hour, schedule.minute)}
                onChange={(event) =>
                  applySchedule({ ...schedule, ...timeToParts(event.target.value) })
                }
              />
            </label>
          </div>
        )}

        {schedule.type === "monthly" && (
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              Día del mes
              <Input
                type="number"
                min={1}
                max={31}
                className="w-20"
                aria-label="Día del mes"
                value={schedule.day}
                onChange={(event) =>
                  applySchedule({
                    type: "monthly",
                    day: Math.min(31, Math.max(1, Number(event.target.value) || 1)),
                    hour: schedule.hour,
                    minute: schedule.minute,
                  })
                }
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              A las
              <Input
                type="time"
                className="w-32"
                aria-label="Hora"
                value={partsToTime(schedule.hour, schedule.minute)}
                onChange={(event) =>
                  applySchedule({ ...schedule, ...timeToParts(event.target.value) })
                }
              />
            </label>
          </div>
        )}
      </TabsContent>

      <TabsContent value="advanced" className="pt-3">
        <Input
          aria-label="Expresión cron"
          placeholder="*/5 * * * *"
          className="font-mono"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </TabsContent>
    </Tabs>
  );
}
