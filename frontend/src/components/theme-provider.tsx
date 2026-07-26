import { useEffect, useState, type ReactNode } from "react";

import { ThemeContext, THEME_STORAGE_KEY, type Theme } from "./theme-context";

const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

function getInitialTheme(): Theme {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

/**
 * Applies the `.dark` class on <html> according to the chosen theme.
 * With "system" it follows `prefers-color-scheme` live; the choice is
 * persisted in localStorage (`crondok-theme`).
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme);

  useEffect(() => {
    const root = document.documentElement;
    const media = window.matchMedia(DARK_MEDIA_QUERY);

    const apply = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      root.classList.toggle("dark", resolved === "dark");
    };

    apply();
    if (theme !== "system") {
      return;
    }
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);

  const setTheme = (next: Theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, next);
    setThemeState(next);
  };

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
