import { createContext } from "react";

// Kept apart from theme-provider.tsx so that file only exports components
// (react-refresh/only-export-components).

export type Theme = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "crondok-theme";

export interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
