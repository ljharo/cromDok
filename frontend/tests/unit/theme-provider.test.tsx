import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/ThemeToggle";
import { THEME_STORAGE_KEY } from "@/components/theme-context";

type ChangeListener = () => void;

/** matchMedia mock with a mutable `matches` and working change listeners. */
function mockMatchMedia(initialDark: boolean) {
  let matches = initialDark;
  const listeners = new Set<ChangeListener>();

  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation(
      (query: string): MediaQueryList =>
        ({
          get matches() {
            return matches;
          },
          media: query,
          onchange: null,
          addListener: () => {},
          removeListener: () => {},
          addEventListener: (_type: string, listener: ChangeListener) => {
            listeners.add(listener);
          },
          removeEventListener: (_type: string, listener: ChangeListener) => {
            listeners.delete(listener);
          },
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    ),
  });

  return {
    setSystemDark(value: boolean) {
      matches = value;
      listeners.forEach((listener) => listener());
    },
  };
}

const html = document.documentElement;

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    html.classList.remove("dark");
  });

  it("aplica .dark cuando el sistema prefiere oscuro (tema system)", () => {
    mockMatchMedia(true);
    render(<ThemeProvider>app</ThemeProvider>);
    expect(html.classList.contains("dark")).toBe(true);
  });

  it("no aplica .dark cuando el sistema prefiere claro", () => {
    mockMatchMedia(false);
    render(<ThemeProvider>app</ThemeProvider>);
    expect(html.classList.contains("dark")).toBe(false);
  });

  it("sigue en vivo los cambios de prefers-color-scheme en modo system", () => {
    const media = mockMatchMedia(true);
    render(<ThemeProvider>app</ThemeProvider>);
    expect(html.classList.contains("dark")).toBe(true);

    act(() => media.setSystemDark(false));
    expect(html.classList.contains("dark")).toBe(false);
  });

  it("la preferencia guardada en localStorage tiene prioridad sobre el sistema", () => {
    mockMatchMedia(true);
    localStorage.setItem(THEME_STORAGE_KEY, "light");
    render(<ThemeProvider>app</ThemeProvider>);
    expect(html.classList.contains("dark")).toBe(false);
  });
});

describe("ThemeToggle", () => {
  beforeEach(() => {
    localStorage.clear();
    html.classList.remove("dark");
  });

  it("cicla system → light → dark, aplica la clase y persiste", () => {
    mockMatchMedia(false);
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    // system → light
    fireEvent.click(screen.getByRole("button", { name: /Tema sistema/ }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(html.classList.contains("dark")).toBe(false);

    // light → dark
    fireEvent.click(screen.getByRole("button", { name: /Tema claro/ }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(html.classList.contains("dark")).toBe(true);

    // dark → system (con sistema claro, se quita .dark)
    fireEvent.click(screen.getByRole("button", { name: /Tema oscuro/ }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("system");
    expect(html.classList.contains("dark")).toBe(false);
  });
});
