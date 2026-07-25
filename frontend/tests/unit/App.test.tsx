import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "@/App";

describe("App", () => {
  it("renders the CronDok dashboard placeholder", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "CronDok" })).toBeInTheDocument();
  });
});
