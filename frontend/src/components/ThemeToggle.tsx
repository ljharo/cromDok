import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme } from "@/hooks/useTheme";
import type { Theme } from "@/components/theme-context";
import { Button } from "@/components/ui/button";

const CYCLE: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const THEME_LABEL: Record<Theme, string> = {
  light: "claro",
  dark: "oscuro",
  system: "sistema",
};

const THEME_ICON: Record<Theme, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

/** Cyclic theme switch: light → dark → system. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const next = CYCLE[theme];
  const Icon = THEME_ICON[theme];

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`Tema ${THEME_LABEL[theme]}: cambiar a ${THEME_LABEL[next]}`}
      title={`Tema ${THEME_LABEL[theme]}: cambiar a ${THEME_LABEL[next]}`}
      onClick={() => setTheme(next)}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
